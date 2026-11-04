"""Unit tests for the read-only guard, query loader and identifier normalisation.

These need no database connection. The read-only guard is safety-critical -- it is the
mechanism that keeps this workbench from modifying the source Pathways database -- so it
is tested directly.
"""

from __future__ import annotations

import pandas as pd
import pytest

from pathways_analysis.config import ConfigurationError
from pathways_analysis.db import (
    QueryLibrary,
    ReadOnlyViolationError,
    assert_read_only,
    load_query_file,
    normalise_id,
)


class TestAssertReadOnly:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1",
            "select PathwayID from dbo.tblPathways",
            "WITH x AS (SELECT 1 AS a) SELECT a FROM x",
        ],
    )
    def test_select_statements_pass(self, sql):
        assert_read_only(sql)

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO dbo.tblPathways (PathwayID) VALUES ('X')",
            "UPDATE dbo.tblPathways SET IsArchived = 1",
            "DELETE FROM dbo.tblTriageLogic",
            "DROP TABLE dbo.tblPathways",
            "TRUNCATE TABLE dbo.tblPathways",
            "CREATE TABLE t (a int)",
            "ALTER TABLE dbo.tblPathways ADD x int",
            "EXEC sp_who",
            "MERGE dbo.tblPathways AS t USING s ON 1=1",
            "GRANT SELECT ON dbo.tblPathways TO public",
            "BACKUP DATABASE TriageDB TO DISK='x'",
            "DBCC CHECKDB",
        ],
    )
    def test_mutating_statements_are_rejected(self, sql):
        with pytest.raises(ReadOnlyViolationError):
            assert_read_only(sql)

    def test_mutation_hidden_after_a_select_is_still_rejected(self):
        with pytest.raises(ReadOnlyViolationError):
            assert_read_only("SELECT 1; DROP TABLE dbo.tblPathways")

    def test_forbidden_keyword_inside_a_comment_is_ignored(self):
        # Comments routinely describe what a query does NOT do; prose must not trip the
        # guard, and the query must still be recognised as a SELECT.
        sql = """
        -- This query does not INSERT, UPDATE or DELETE anything.
        /* It will never DROP a table either. */
        SELECT PathwayID FROM dbo.tblPathways
        """
        assert_read_only(sql)

    def test_keyword_as_part_of_a_longer_word_is_allowed(self):
        # 'Created' contains 'CREATE' as a substring but not as a word.
        assert_read_only("SELECT Created, LastModified FROM dbo.tblPathways")

    def test_non_select_start_is_rejected(self):
        with pytest.raises(ReadOnlyViolationError, match="must start with SELECT or WITH"):
            assert_read_only("PRINT 'hello'")

    def test_error_names_the_query(self):
        with pytest.raises(ReadOnlyViolationError, match="my_query"):
            assert_read_only("DELETE FROM x", query_name="my_query")


class TestLoadQueryFile:
    def test_splits_named_blocks(self, tmp_path):
        path = tmp_path / "q.sql"
        path.write_text(
            "-- file level docs\n"
            "-- name: first\n"
            "SELECT 1 AS a;\n"
            "-- name: second\n"
            "SELECT 2 AS b;\n",
            encoding="utf-8",
        )
        blocks = load_query_file(path)
        assert set(blocks) == {"first", "second"}
        assert "SELECT 1 AS a" in blocks["first"]
        # File-level prose above the first marker is not part of any query.
        assert "file level docs" not in blocks["first"]

    def test_duplicate_name_in_one_file_raises(self, tmp_path):
        path = tmp_path / "q.sql"
        path.write_text(
            "-- name: dup\nSELECT 1;\n-- name: dup\nSELECT 2;\n", encoding="utf-8"
        )
        with pytest.raises(ConfigurationError, match="Duplicate query name"):
            load_query_file(path)

    def test_file_with_no_markers_raises(self, tmp_path):
        path = tmp_path / "q.sql"
        path.write_text("SELECT 1;\n", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="no '-- name:"):
            load_query_file(path)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ConfigurationError, match="SQL file not found"):
            load_query_file(tmp_path / "absent.sql")


class TestQueryLibrary:
    def test_loads_across_files_and_rejects_cross_file_duplicates(self, tmp_path):
        (tmp_path / "01_a.sql").write_text("-- name: alpha\nSELECT 1;\n", encoding="utf-8")
        (tmp_path / "02_b.sql").write_text("-- name: beta\nSELECT 2;\n", encoding="utf-8")
        library = QueryLibrary(tmp_path)
        assert library.names == ("alpha", "beta")

        (tmp_path / "03_c.sql").write_text("-- name: alpha\nSELECT 3;\n", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="defined in both"):
            QueryLibrary(tmp_path).load()

    def test_mutating_query_in_a_file_aborts_loading(self, tmp_path):
        (tmp_path / "bad.sql").write_text(
            "-- name: naughty\nDELETE FROM dbo.tblPathways;\n", encoding="utf-8"
        )
        with pytest.raises(ReadOnlyViolationError):
            QueryLibrary(tmp_path).load()

    def test_unknown_query_lists_available_names(self, tmp_path):
        (tmp_path / "a.sql").write_text("-- name: alpha\nSELECT 1;\n", encoding="utf-8")
        library = QueryLibrary(tmp_path)
        with pytest.raises(ConfigurationError, match="Available: alpha"):
            library.get("missing")

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(ConfigurationError, match="SQL directory not found"):
            QueryLibrary(tmp_path / "nope").load()


class TestNormaliseId:
    def test_upper_cases_and_strips(self):
        result = normalise_id(pd.Series(["Tx100001", " tx100002 ", "TX100003"]))
        assert list(result) == ["TX100001", "TX100002", "TX100003"]

    def test_nulls_are_preserved(self):
        result = normalise_id(pd.Series(["Tx1", None]))
        assert result.iloc[0] == "TX1"
        assert pd.isna(result.iloc[1])

    def test_makes_mixed_case_joins_succeed(self):
        # This is the real failure mode the function exists to prevent: tblTriageLogic
        # stores TX... while tblTxQuestions stores Tx..., so a raw merge loses rows.
        logic = pd.DataFrame({"question_id": ["TX100001", "Tx100001"]})
        catalogue = pd.DataFrame({"question_id": ["Tx100001"], "control_type": [1]})

        raw = logic.merge(catalogue, on="question_id", how="left")
        assert raw["control_type"].isna().sum() == 1  # a row was silently lost

        logic["key"] = normalise_id(logic["question_id"])
        catalogue["key"] = normalise_id(catalogue["question_id"])
        normalised = logic.merge(catalogue, on="key", how="left", suffixes=("", "_cat"))
        assert normalised["control_type"].notna().all()
