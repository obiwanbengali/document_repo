"""Read-only database access for the Pathways structural analysis workbench.

Design rules enforced here:

* All SQL lives in ``sql/*.sql`` and is loaded by name. No analysis SQL is built by
  string concatenation.
* Every statement is checked against a deny-list before execution, so a DDL/DML
  statement cannot reach the source database even by accident.
* Parameters are always bound via SQLAlchemy ``text()`` parameters, never interpolated.
* Connection failure raises immediately with the (credential-free) target described.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Final, Mapping

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .config import ConfigurationError, DatabaseSettings, Paths

LOGGER: Final = logging.getLogger(__name__)

#: Marker introducing a named query inside a .sql file, e.g. "-- name: inventory".
_QUERY_NAME_PATTERN: Final = re.compile(r"^\s*--\s*name:\s*(?P<name>[A-Za-z0-9_]+)\s*$")

#: Statement keywords that must never appear in a query issued by this package.
#: The source database is treated as immutable evidence, so mutation is a bug, not a
#: permission question.
_FORBIDDEN_KEYWORDS: Final[tuple[str, ...]] = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "DROP", "CREATE", "ALTER",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "BACKUP", "RESTORE", "BULK", "SHUTDOWN",
    "RECONFIGURE", "DBCC",
)


class ReadOnlyViolationError(RuntimeError):
    """Raised when a query would modify the source database."""


class DatabaseConnectionError(RuntimeError):
    """Raised when the database is unreachable or rejects the credentials."""


def _strip_sql_comments(sql: str) -> str:
    """Remove line and block comments so keyword checks cannot be hidden in prose.

    Without this, the word "CREATE" inside an explanatory comment would trip the
    read-only guard, and conversely a mutation could be smuggled past a naive check.
    """
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_line = re.sub(r"--[^\n]*", " ", without_block)
    return without_line


def assert_read_only(sql: str, *, query_name: str = "<inline>") -> None:
    """Verify that a statement only reads.

    Args:
        sql: The SQL text to check.
        query_name: Name used in the error message.

    Raises:
        ReadOnlyViolationError: If a forbidden keyword appears as a whole word outside
            of comments, or if the statement does not start with SELECT/WITH.
    """
    body = _strip_sql_comments(sql)
    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", body, flags=re.IGNORECASE):
            raise ReadOnlyViolationError(
                f"Query {query_name!r} contains forbidden keyword {keyword!r}. "
                "This package must never modify the source database."
            )
    first_token = body.strip().split(None, 1)[0].upper() if body.strip() else ""
    if first_token not in {"SELECT", "WITH"}:
        raise ReadOnlyViolationError(
            f"Query {query_name!r} must start with SELECT or WITH, got {first_token!r}."
        )


def load_query_file(path: Path) -> dict[str, str]:
    """Split a ``.sql`` file into its named query blocks.

    Blocks are introduced by a ``-- name: <identifier>`` line. Leading text before the
    first marker is treated as file-level documentation and discarded.

    Args:
        path: Path to the ``.sql`` file.

    Returns:
        Mapping of query name to SQL text.

    Raises:
        ConfigurationError: If the file is missing, defines no named block, or defines
            the same name twice.
    """
    if not path.is_file():
        raise ConfigurationError(f"SQL file not found: {path}")

    blocks: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            blocks[current] = "\n".join(buffer).strip()

    for line in path.read_text(encoding="utf-8").splitlines():
        match = _QUERY_NAME_PATTERN.match(line)
        if match:
            flush()
            current = match.group("name")
            if current in blocks:
                raise ConfigurationError(
                    f"Duplicate query name {current!r} in {path.name}."
                )
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()

    if not blocks:
        raise ConfigurationError(
            f"{path.name} defines no '-- name: <identifier>' query blocks."
        )
    return blocks


class QueryLibrary:
    """Lazily-loaded collection of the named queries in ``sql/``."""

    def __init__(self, sql_dir: Path) -> None:
        self._sql_dir = sql_dir
        self._queries: dict[str, str] = {}
        self._source: dict[str, str] = {}
        self._loaded = False

    def load(self) -> None:
        """Load and validate every query in the SQL directory.

        Raises:
            ConfigurationError: If the directory is missing, or a query name collides
                across files.
            ReadOnlyViolationError: If any query would modify the database.
        """
        if self._loaded:
            return
        if not self._sql_dir.is_dir():
            raise ConfigurationError(f"SQL directory not found: {self._sql_dir}")

        for sql_file in sorted(self._sql_dir.glob("*.sql")):
            for name, sql in load_query_file(sql_file).items():
                if name in self._queries:
                    raise ConfigurationError(
                        f"Query name {name!r} defined in both "
                        f"{self._source[name]} and {sql_file.name}."
                    )
                assert_read_only(sql, query_name=f"{sql_file.name}:{name}")
                self._queries[name] = sql
                self._source[name] = sql_file.name
        self._loaded = True
        LOGGER.info(
            "Loaded %d read-only queries from %d SQL files.",
            len(self._queries),
            len({v for v in self._source.values()}),
        )

    def get(self, name: str) -> str:
        """Return the SQL text for a named query."""
        self.load()
        try:
            return self._queries[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._queries))
            raise ConfigurationError(
                f"Unknown query {name!r}. Available: {available}"
            ) from exc

    @property
    def names(self) -> tuple[str, ...]:
        self.load()
        return tuple(sorted(self._queries))


class PathwaysDatabase:
    """Read-only accessor for the Pathways SQL Server database."""

    def __init__(self, settings: DatabaseSettings, paths: Paths | None = None) -> None:
        self._settings = settings
        self._paths = paths or Paths.discover()
        self._engine: Engine | None = None
        self.queries = QueryLibrary(self._paths.sql_dir)

    @property
    def settings(self) -> DatabaseSettings:
        return self._settings

    @property
    def engine(self) -> Engine:
        """Return the lazily-created SQLAlchemy engine."""
        if self._engine is None:
            self._engine = create_engine(
                self._settings.sqlalchemy_url(),
                pool_pre_ping=True,
                connect_args={"timeout": self._settings.query_timeout_seconds},
            )
        return self._engine

    def validate_connectivity(self) -> dict[str, Any]:
        """Confirm the database is reachable and report what we connected to.

        Returns:
            Mapping with the server version, database name and server-side UTC time.

        Raises:
            DatabaseConnectionError: On any connection or authentication failure. The
                message names the target without exposing the password.
        """
        probe = text(
            "SELECT @@VERSION AS server_version, "
            "DB_NAME() AS database_name, "
            "SYSUTCDATETIME() AS server_utc_time"
        )
        try:
            with self.engine.connect() as connection:
                row = connection.execute(probe).mappings().one()
        except SQLAlchemyError as exc:
            raise DatabaseConnectionError(
                f"Cannot connect to SQL Server at {self._settings.describe()}. "
                f"Underlying error: {exc.__class__.__name__}: {exc}"
            ) from exc

        info = {
            "server_version": str(row["server_version"]).splitlines()[0].strip(),
            "database_name": row["database_name"],
            "server_utc_time": row["server_utc_time"],
        }
        LOGGER.info("Connected to %s", self._settings.describe())
        LOGGER.info("Server: %s", info["server_version"])
        return info

    def read_query(
        self,
        name: str,
        params: Mapping[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Execute a named query from ``sql/`` and return the result.

        Args:
            name: Query name declared by a ``-- name:`` marker.
            params: Bound parameters. Values are always bound, never interpolated.

        Returns:
            The result as a DataFrame.

        Raises:
            DatabaseConnectionError: If the query cannot be executed.
        """
        sql = self.queries.get(name)
        statement = text(sql)
        started = time.perf_counter()
        try:
            with self.engine.connect() as connection:
                frame = pd.read_sql_query(statement, connection, params=dict(params or {}))
        except SQLAlchemyError as exc:
            raise DatabaseConnectionError(
                f"Query {name!r} failed against {self._settings.describe()}. "
                f"Underlying error: {exc.__class__.__name__}: {exc}"
            ) from exc
        elapsed = time.perf_counter() - started
        LOGGER.info("Query %-38s %8d rows  %6.2fs", name, len(frame), elapsed)
        return frame

    def dispose(self) -> None:
        """Release pooled connections."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None


def normalise_id(series: pd.Series) -> pd.Series:
    """Normalise an identifier column to a case-stable join key.

    TriageDB uses a case-insensitive collation, and ``tblTriageLogic`` stores the same
    logical identifier with inconsistent prefix case (``TX100001`` in 113,585 rows and
    ``Tx100001`` in 6,668 rows, for one example). pandas joins are case-sensitive, so
    joining on the raw column silently drops the majority of triage logic rows.

    Upper-casing was verified collision-free for PathwayID, QuestionID,
    (QuestionID, AnswerNumber) and DispositionCode before being adopted.

    Args:
        series: Identifier column.

    Returns:
        The column upper-cased and stripped, with nulls preserved.
    """
    return series.astype("string").str.strip().str.upper()
