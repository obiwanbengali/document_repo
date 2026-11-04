"""Configuration for the Pathways structural analysis workbench.

Database credentials are read from environment variables only. Nothing in this module
holds a default credential, and no credential is ever written to a log line or an
output file.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from sqlalchemy.engine import URL

LOGGER: Final = logging.getLogger(__name__)

#: Environment variables that must be present before a connection is attempted.
REQUIRED_ENV_VARS: Final[tuple[str, ...]] = (
    "PATHWAYS_DB_HOST",
    "PATHWAYS_DB_PORT",
    "PATHWAYS_DB_NAME",
    "PATHWAYS_DB_USER",
    "PATHWAYS_DB_PASSWORD",
)

DEFAULT_ODBC_DRIVER: Final = "ODBC Driver 18 for SQL Server"


class ConfigurationError(RuntimeError):
    """Raised when configuration is missing or unusable.

    Raised eagerly and loudly: an analysis run against a partially configured
    database would silently produce a misleading evidence base.
    """


@dataclass(frozen=True)
class DatabaseSettings:
    """Read-only SQL Server connection settings.

    Attributes:
        host: Hostname or IP of the SQL Server instance.
        port: TCP port.
        database: Database name.
        user: Login name.
        password: Login password. Never logged or exported.
        driver: ODBC driver name as registered with the local driver manager.
        encrypt: Value for the ODBC ``Encrypt`` keyword.
        trust_server_certificate: Whether to accept a self-signed server certificate.
            Required for the local Docker SQL Server, which uses a self-signed cert.
        login_timeout_seconds: ODBC login timeout.
        query_timeout_seconds: Per-statement timeout. 0 disables the timeout.
    """

    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    driver: str = DEFAULT_ODBC_DRIVER
    encrypt: str = "yes"
    trust_server_certificate: bool = True
    login_timeout_seconds: int = 30
    query_timeout_seconds: int = 600

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        """Build settings from environment variables.

        Returns:
            Populated settings.

        Raises:
            ConfigurationError: If a required variable is missing/blank, or if the
                port is not an integer.
        """
        missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name, "").strip()]
        if missing:
            raise ConfigurationError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". Copy .env.example to .env and populate it, then re-run."
            )

        raw_port = os.environ["PATHWAYS_DB_PORT"].strip()
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ConfigurationError(
                f"PATHWAYS_DB_PORT must be an integer, got {raw_port!r}."
            ) from exc

        return cls(
            host=os.environ["PATHWAYS_DB_HOST"].strip(),
            port=port,
            database=os.environ["PATHWAYS_DB_NAME"].strip(),
            user=os.environ["PATHWAYS_DB_USER"].strip(),
            password=os.environ["PATHWAYS_DB_PASSWORD"],
            driver=os.environ.get("PATHWAYS_DB_DRIVER", DEFAULT_ODBC_DRIVER).strip(),
            encrypt=os.environ.get("PATHWAYS_DB_ENCRYPT", "yes").strip(),
            trust_server_certificate=_env_flag("PATHWAYS_DB_TRUST_SERVER_CERT", True),
            login_timeout_seconds=int(os.environ.get("PATHWAYS_DB_LOGIN_TIMEOUT", "30")),
            query_timeout_seconds=int(os.environ.get("PATHWAYS_DB_QUERY_TIMEOUT", "600")),
        )

    def sqlalchemy_url(self) -> URL:
        """Return the SQLAlchemy URL for this connection.

        ``URL.create`` is used rather than string formatting so that passwords
        containing URL-significant characters (``!``, ``@``, ``;``) are escaped by
        SQLAlchemy instead of corrupting the connection string.
        """
        return URL.create(
            "mssql+pyodbc",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
            query={
                "driver": self.driver,
                "Encrypt": self.encrypt,
                "TrustServerCertificate": "yes" if self.trust_server_certificate else "no",
                "LoginTimeout": str(self.login_timeout_seconds),
                # ApplicationIntent advertises this client as read-only. It is a hint,
                # not a guarantee; the actual read-only guarantee comes from this
                # codebase issuing no DDL/DML (see db.assert_read_only).
                "ApplicationIntent": "ReadOnly",
            },
        )

    def describe(self) -> str:
        """Return a human-readable connection description with no credentials."""
        return f"{self.user}@{self.host}:{self.port}/{self.database} via {self.driver!r}"


@dataclass(frozen=True)
class Paths:
    """Filesystem layout for inputs and generated artefacts."""

    project_root: Path

    @classmethod
    def discover(cls) -> "Paths":
        """Locate the project root.

        Honours ``PATHWAYS_PROJECT_ROOT`` when set; otherwise resolves it relative to
        this file (``src/pathways_analysis/config.py`` -> project root), which keeps the
        runner working regardless of the current working directory.
        """
        override = os.environ.get("PATHWAYS_PROJECT_ROOT", "").strip()
        if override:
            return cls(project_root=Path(override).expanduser().resolve())
        return cls(project_root=Path(__file__).resolve().parents[2])

    @property
    def sql_dir(self) -> Path:
        return self.project_root / "sql"

    @property
    def data_processed(self) -> Path:
        return self.project_root / "data" / "processed"

    @property
    def outputs(self) -> Path:
        return self.project_root / "outputs"

    @property
    def tables(self) -> Path:
        return self.outputs / "tables"

    @property
    def charts(self) -> Path:
        return self.outputs / "charts"

    @property
    def config_dir(self) -> Path:
        return self.project_root / "config"

    # Phase 2 writes to its own subtree so that a Phase 2 run can never overwrite a
    # Phase 1 artefact. The two phases are separate evidence bases and are reviewed
    # separately.
    @property
    def phase2(self) -> Path:
        return self.outputs / "phase2"

    @property
    def phase2_tables(self) -> Path:
        return self.phase2 / "tables"

    @property
    def phase2_charts(self) -> Path:
        return self.phase2 / "charts"

    @property
    def phase2_graphs(self) -> Path:
        return self.phase2 / "graphs"

    @property
    def phase2_reports(self) -> Path:
        return self.phase2 / "reports"

    # The static presentation layer. `reports/` holds hand-written HTML/CSS/JS that is
    # tracked; `reports/data/` holds generated JSON that is not, because it carries
    # derived Pathways content.
    @property
    def phase3(self) -> Path:
        return self.outputs / "phase3"

    @property
    def phase3_tables(self) -> Path:
        return self.phase3 / "tables"

    @property
    def phase3_charts(self) -> Path:
        return self.phase3 / "charts"

    @property
    def phase3_reports(self) -> Path:
        return self.phase3 / "reports"

    @property
    def reports(self) -> Path:
        return self.project_root / "reports"

    @property
    def reports_data(self) -> Path:
        return self.reports / "data"

    def ensure_directories(self) -> None:
        """Create every Phase 1 output directory. Safe to call repeatedly."""
        for path in (self.data_processed, self.tables, self.charts):
            path.mkdir(parents=True, exist_ok=True)

    def ensure_phase2_directories(self) -> None:
        """Create every Phase 2 output directory. Safe to call repeatedly."""
        for path in (
            self.data_processed,
            self.phase2,
            self.phase2_tables,
            self.phase2_charts,
            self.phase2_graphs,
            self.phase2_reports,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def ensure_phase3_directories(self) -> None:
        """Create every Phase 3 output directory. Safe to call repeatedly."""
        for path in (
            self.phase3,
            self.phase3_tables,
            self.phase3_charts,
            self.phase3_reports,
        ):
            path.mkdir(parents=True, exist_ok=True)


def _env_flag(name: str, default: bool) -> bool:
    """Interpret an environment variable as a boolean flag."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_dotenv_if_present(paths: Paths | None = None) -> Path | None:
    """Load ``.env`` from the project root if python-dotenv is installed.

    Existing environment variables win, so an explicitly exported credential is never
    silently overridden by a stale ``.env``.

    Returns:
        The path loaded, or None if there was nothing to load.
    """
    paths = paths or Paths.discover()
    env_file = paths.project_root / ".env"
    if not env_file.is_file():
        return None
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - optional dependency
        LOGGER.warning(
            "%s exists but python-dotenv is not installed; relying on the exported "
            "environment instead.",
            env_file,
        )
        return None
    load_dotenv(env_file, override=False)
    return env_file
