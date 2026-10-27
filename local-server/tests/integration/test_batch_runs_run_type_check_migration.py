"""
Integration tests for migration eae4e30702d2 (restore batch_runs run_type CHECK).

Tests verify, against real file-based SQLite databases migrated with Alembic:
- A fresh database at this revision carries the named check_valid_run_type constraint
  (8de28edb4953 drops it again; see test_change_proposals_migration.py)
- Valid run types insert; unknown run types fail the CHECK
- A database carrying the old narrow ('import', 'extraction') constraint is
  upgraded to the full constraint with its batch_runs rows and child rows intact
- Downgrade followed by upgrade round-trips without losing rows
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "../../adapters/persistence/sqlite/alembic.ini"
)
REVISION = "eae4e30702d2"
PREVIOUS_REVISION = "5acc1ebd83f7"

NARROW_BATCH_RUNS_DDL = """
    CREATE TABLE batch_runs (
        id VARCHAR(36) NOT NULL,
        created_at DATETIME NOT NULL,
        created_by VARCHAR(36),
        status VARCHAR(20) NOT NULL,
        affected_entity_ids JSON NOT NULL,
        run_type VARCHAR(20) NOT NULL,
        batch_id VARCHAR(36),
        PRIMARY KEY (id),
        CONSTRAINT check_valid_run_type CHECK (run_type IN ('import', 'extraction')),
        CONSTRAINT fk_batch_runs_batch_id FOREIGN KEY(batch_id) REFERENCES batches (id) ON DELETE CASCADE
    )
"""


def _alembic_config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _batch_runs_ddl(db_path: str) -> str:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='batch_runs'"
        ).fetchone()[0]


def _batch_runs_indexes(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='batch_runs' "
            "AND name NOT LIKE 'sqlite_autoindex%'"
        ).fetchall()
    return {row[0] for row in rows}


def _insert_batch_run(conn: sqlite3.Connection, run_id: str, run_type: str) -> None:
    conn.execute(
        "INSERT INTO batch_runs (id, created_at, status, affected_entity_ids, run_type) "
        "VALUES (?, ?, 'pending', '[]', ?)",
        (run_id, datetime.now(timezone.utc).isoformat(), run_type),
    )


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "local.db")


class TestFreshDatabase:
    """A database migrated from scratch to this revision enforces the run_type CHECK."""

    def test_named_constraint_and_indexes_present(self, db_path):
        upgrade(_alembic_config(db_path), REVISION)

        ddl = _batch_runs_ddl(db_path)
        assert "CONSTRAINT check_valid_run_type CHECK" in ddl
        assert "'schema_extraction'" in ddl
        assert "'individual_extraction'" in ddl
        assert "CONSTRAINT fk_batch_runs_batch_id FOREIGN KEY(batch_id)" in ddl
        assert _batch_runs_indexes(db_path) == {
            "idx_run_type_status",
            "ix_batch_runs_created_at",
            "ix_batch_runs_status",
            "ix_batch_runs_run_type",
            "ix_batch_runs_batch_id",
        }

    def test_schema_extraction_run_type_accepted(self, db_path):
        upgrade(_alembic_config(db_path), REVISION)

        with sqlite3.connect(db_path) as conn:
            _insert_batch_run(conn, "run-1", "schema_extraction")
            count = conn.execute("SELECT COUNT(*) FROM batch_runs").fetchone()[0]
        assert count == 1

    def test_unknown_run_type_rejected(self, db_path):
        upgrade(_alembic_config(db_path), REVISION)

        with sqlite3.connect(db_path) as conn:
            with pytest.raises(sqlite3.IntegrityError, match="check_valid_run_type"):
                _insert_batch_run(conn, "run-1", "bogus")


class TestNarrowConstraintDatabase:
    """A database carrying the old narrow named constraint is brought up to the model."""

    @pytest.fixture
    def narrow_db(self, db_path):
        """Database at the previous head whose batch_runs has the narrow constraint and rows."""
        upgrade(_alembic_config(db_path), PREVIOUS_REVISION)
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE batch_runs")
            conn.execute(NARROW_BATCH_RUNS_DDL)
            _insert_batch_run(conn, "import-run", "import")
            _insert_batch_run(conn, "extraction-run", "extraction")
            conn.execute(
                "INSERT INTO import_runs (id, format, source_hash, scope_type, "
                "scope_include_descendants, resolutions) "
                "VALUES ('import-run', 'skos', 'abc', 'whole_graph', 0, '{}')"
            )
            with pytest.raises(sqlite3.IntegrityError):
                _insert_batch_run(conn, "rejected", "schema_extraction")
        return db_path

    def test_upgrade_widens_constraint_and_preserves_rows(self, narrow_db):
        upgrade(_alembic_config(narrow_db), REVISION)

        ddl = _batch_runs_ddl(narrow_db)
        assert "'schema_node_connection_refinement'" in ddl
        assert "VARCHAR(50)" in ddl
        with sqlite3.connect(narrow_db) as conn:
            rows = conn.execute("SELECT id, run_type FROM batch_runs ORDER BY id").fetchall()
            assert rows == [("extraction-run", "extraction"), ("import-run", "import")]
            assert conn.execute("SELECT id FROM import_runs").fetchall() == [("import-run",)]
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

            _insert_batch_run(conn, "schema-run", "schema_extraction")
            with pytest.raises(sqlite3.IntegrityError, match="check_valid_run_type"):
                _insert_batch_run(conn, "bogus-run", "bogus")

    def test_downgrade_then_upgrade_round_trips_rows(self, narrow_db):
        config = _alembic_config(narrow_db)
        upgrade(config, REVISION)
        with sqlite3.connect(narrow_db) as conn:
            _insert_batch_run(conn, "schema-run", "schema_extraction")

        downgrade(config, PREVIOUS_REVISION)
        assert "check_valid_run_type" not in _batch_runs_ddl(narrow_db)

        upgrade(config, REVISION)
        assert "CONSTRAINT check_valid_run_type CHECK" in _batch_runs_ddl(narrow_db)
        with sqlite3.connect(narrow_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM batch_runs").fetchone()[0]
        assert count == 3


class TestInvalidExistingRows:
    """Rows that would violate the constraint make the upgrade fail rather than vanish."""

    def test_upgrade_fails_loudly_on_unknown_run_type(self, db_path):
        config = _alembic_config(db_path)
        upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(db_path) as conn:
            _insert_batch_run(conn, "bad-run", "legacy_type")

        with pytest.raises(RuntimeError, match="legacy_type"):
            upgrade(config, REVISION)
        with sqlite3.connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM batch_runs").fetchone()[0] == 1
