"""Integration tests for scripts/run_migrations.py: it migrates the databases the config names."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

LOCAL_SERVER_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = LOCAL_SERVER_ROOT / "scripts" / "run_migrations.py"

sys.path.insert(0, str(LOCAL_SERVER_ROOT / "scripts"))
import run_migrations  # noqa: E402


def write_config(path: Path, local_db: str, operations_db: str) -> Path:
    path.write_text(
        json.dumps({"database": {"local_db_path": local_db, "operations_db_path": operations_db}})
    )
    return path


def migrated(db_path: Path) -> bool:
    """Whether the file is a database Alembic has put a revision in."""
    if not db_path.exists():
        return False
    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        return "alembic_version" in tables and bool(
            connection.execute("SELECT version_num FROM alembic_version").fetchall()
        )


def run_script(cwd: Path, config: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CONFIG_PATH": str(config)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


class TestRunFromAnotherDirectory:
    """Run from a directory that is not local-server, the config's databases are the ones touched."""

    def test_all_upgrade_head_migrates_the_configured_databases_and_nothing_else(self, tmp_path):
        data = tmp_path / "data"
        data.mkdir()
        elsewhere = tmp_path / "somewhere-else"
        elsewhere.mkdir()
        config = write_config(
            tmp_path / "config.json", str(data / "mine.db"), str(data / "mine-ops.db")
        )
        stray = [LOCAL_SERVER_ROOT / "local.db", LOCAL_SERVER_ROOT / "operations.db"]
        stray_before = {p: p.stat().st_mtime_ns if p.exists() else None for p in stray}

        result = run_script(elsewhere, config, "all", "upgrade", "head")

        assert result.returncode == 0, result.stderr
        assert migrated(data / "mine.db")
        assert migrated(data / "mine-ops.db")
        # Nothing was created in the directory it ran from, or touched in local-server
        assert list(elsewhere.iterdir()) == []
        assert {p: p.stat().st_mtime_ns if p.exists() else None for p in stray} == stray_before
        assert str(data / "mine.db") in result.stdout
        assert str(data / "mine-ops.db") in result.stdout

    def test_an_explicit_url_overrides_the_config_for_that_database(self, tmp_path):
        configured = tmp_path / "configured.db"
        explicit = tmp_path / "explicit.db"
        config = write_config(tmp_path / "config.json", str(configured), str(tmp_path / "ops.db"))

        result = run_script(
            tmp_path, config, "local", "upgrade", "head", "--local-db-url", f"sqlite:///{explicit}"
        )

        assert result.returncode == 0, result.stderr
        assert migrated(explicit)
        assert not configured.exists()


class TestConfigDatabaseUrls:
    """The URLs come from the config the app loads, absolute whatever the working directory."""

    def test_relative_paths_are_relative_to_local_server_not_the_working_directory(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        config = write_config(tmp_path / "config.json", "./data/local.db", "ops/operations.db")
        base = tmp_path / "server"

        local_url, operations_url = run_migrations.config_database_urls(str(config), base_dir=base)

        assert local_url == f"sqlite:///{base / 'data' / 'local.db'}"
        assert operations_url == f"sqlite:///{base / 'ops' / 'operations.db'}"

    def test_config_path_comes_from_the_environment(self, tmp_path, monkeypatch):
        config = write_config(
            tmp_path / "other.json", str(tmp_path / "a.db"), str(tmp_path / "b.db")
        )
        monkeypatch.setenv("CONFIG_PATH", str(config))

        assert run_migrations.config_database_urls() == (
            f"sqlite:///{tmp_path / 'a.db'}",
            f"sqlite:///{tmp_path / 'b.db'}",
        )

    def test_a_missing_config_means_the_defaults_and_is_not_created(self, tmp_path, monkeypatch):
        missing = tmp_path / "config.json"
        monkeypatch.setenv("CONFIG_PATH", str(missing))

        local_url, operations_url = run_migrations.config_database_urls(base_dir=LOCAL_SERVER_ROOT)

        assert local_url == f"sqlite:///{LOCAL_SERVER_ROOT / 'local.db'}"
        assert operations_url == f"sqlite:///{LOCAL_SERVER_ROOT / 'operations.db'}"
        assert not missing.exists()

    def test_a_relative_config_path_is_relative_to_local_server(self, tmp_path, monkeypatch):
        server = tmp_path / "server"
        (server / "conf").mkdir(parents=True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        write_config(server / "conf" / "mine.json", "data/local.db", "data/operations.db")
        monkeypatch.setattr(run_migrations, "LOCAL_SERVER_ROOT", server)
        monkeypatch.setenv("CONFIG_PATH", "conf/mine.json")
        monkeypatch.chdir(elsewhere)

        local_url, operations_url = run_migrations.config_database_urls()

        assert local_url == f"sqlite:///{server / 'data' / 'local.db'}"
        assert operations_url == f"sqlite:///{server / 'data' / 'operations.db'}"

    def test_a_database_path_is_not_expanded_for_a_home_directory(self, tmp_path):
        """The app opens the path as written, so a leading ~ is a directory called ~."""
        config = write_config(tmp_path / "config.json", "~/local.db", "~/operations.db")

        local_url, _ = run_migrations.config_database_urls(str(config), base_dir=tmp_path)

        assert local_url == f"sqlite:///{tmp_path / '~' / 'local.db'}"
