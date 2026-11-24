#!/usr/bin/env python
"""
Utility script to run Alembic migrations for both local.db and operations.db.

Both databases are the ones the app opens: database.local_db_path and
database.operations_db_path from the config the app loads (the file CONFIG_PATH
names, else local-server/config.json; the defaults when there is no file, which
this script never creates). A relative path is relative to local-server/, where
the app runs, so the result does not depend on the directory this is started
from. --local-db-url and --operations-db-url override one database explicitly.

Usage:
    python scripts/run_migrations.py local upgrade head
    python scripts/run_migrations.py operations downgrade -1
    python scripts/run_migrations.py all upgrade head
    python scripts/run_migrations.py local upgrade head --local-db-url sqlite:///./custom.db
    python scripts/run_migrations.py all upgrade head --operations-db-url sqlite:///./custom_ops.db

This script abstracts away the need to specify --config and working directories.
"""

import os
import subprocess
import sys
from pathlib import Path

# Resolve alembic from the same venv as the running Python interpreter
_alembic = Path(sys.executable).parent / "alembic"
ALEMBIC = str(_alembic) if _alembic.exists() else "alembic"

# Get the local-server root directory
LOCAL_SERVER_ROOT = Path(__file__).parent.parent
SQLITE_DIR = LOCAL_SERVER_ROOT / "adapters" / "persistence" / "sqlite"

if str(LOCAL_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCAL_SERVER_ROOT))


def config_database_urls(
    config_path: str | None = None, base_dir: Path = LOCAL_SERVER_ROOT
) -> tuple[str, str]:
    """
    The (local.db, operations.db) SQLAlchemy URLs from the config the app loads.

    config_path defaults to CONFIG_PATH, else local-server/config.json. A missing
    file means the defaults and is not created. A relative database path is
    taken relative to base_dir (local-server/, where the app runs); the URLs are
    absolute.
    """
    from config import ConfigurationManager, DatabaseConfig

    path = config_path or os.getenv("CONFIG_PATH") or str(LOCAL_SERVER_ROOT / "config.json")
    if os.path.exists(path):
        database = ConfigurationManager(config_file=path).get_settings().database
    else:
        database = DatabaseConfig()

    def url(db_path: str) -> str:
        return f"sqlite:///{(base_dir / os.path.expanduser(db_path)).resolve()}"

    return url(database.local_db_path), url(database.operations_db_path)


def run_migrations(
    database: str,
    args: list[str],
    local_db_url: str | None = None,
    operations_db_url: str | None = None,
) -> int:
    """Run Alembic command for a specific database."""
    if database not in ["local", "operations"]:
        print(
            f"Error: Invalid database '{database}'. Must be 'local' or 'operations'.",
            file=sys.stderr,
        )
        return 1

    if database == "operations":
        # For operations.db, use Python API directly to work around version_locations issues
        return run_operations_migrations(args, operations_db_url or config_database_urls()[1])
    else:
        return run_local_migrations(args, local_db_url or config_database_urls()[0])


def run_local_migrations(args: list[str], local_db_url: str | None = None) -> int:
    """Run migrations for local.db using alembic CLI (the config's database when no URL is given)."""
    config_path = SQLITE_DIR / "alembic.ini"

    # Construct the alembic command
    cmd = [ALEMBIC, "--config", str(config_path)]

    cmd.extend(["-x", f"local_db_url={local_db_url or config_database_urls()[0]}"])

    cmd.extend(args)

    # Run the command from the local-server directory so database paths are correct
    return subprocess.run(cmd, cwd=str(LOCAL_SERVER_ROOT)).returncode


def run_operations_migrations(args: list[str], operations_db_url: str | None = None) -> int:
    """Run migrations for operations.db using Alembic Python API."""
    import argparse

    from alembic import command
    from alembic.config import Config

    try:
        # Create Alembic configuration
        config = Config(str(SQLITE_DIR / "alembic.ini"))

        # Set cmd_opts so env.py can detect this is for operations database
        db_url = operations_db_url or config_database_urls()[1]
        config.cmd_opts = argparse.Namespace(x=["db=operations", f"operations_db_url={db_url}"])

        # Set version locations to operations directory only
        config.set_main_option("version_locations", str(SQLITE_DIR / "operations" / "versions"))

        # Set database URL
        config.set_main_option("sqlalchemy.url", db_url)

        # Parse arguments and run the appropriate Alembic command
        if not args:
            return 1

        command_name = args[0]
        command_args = args[1:] if len(args) > 1 else []

        if command_name == "upgrade":
            # Support both "head" and "heads" for upgrade target
            revision = command_args[0] if command_args else "head"
            if revision == "heads":
                revision = "head"
            command.upgrade(config, revision)
            return 0
        elif command_name == "downgrade":
            revision = command_args[0] if command_args else "-1"
            command.downgrade(config, revision)
            return 0
        elif command_name == "revision":
            message = None
            autogenerate = False

            # Parse command arguments for flags
            i = 0
            while i < len(command_args):
                if command_args[i] in ("-m", "--message"):
                    if i + 1 < len(command_args):
                        message = command_args[i + 1]
                        i += 2
                    else:
                        print("Error: -m requires a message value", file=sys.stderr)
                        return 1
                elif command_args[i] == "--autogenerate":
                    autogenerate = True
                    i += 1
                else:
                    print(
                        f"Warning: Ignoring unknown argument '{command_args[i]}'",
                        file=sys.stderr,
                    )
                    i += 1

            command.revision(config, message=message, autogenerate=autogenerate)
            return 0
        else:
            print(f"Error: Unknown command '{command_name}'", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error running operations migrations: {e}", file=sys.stderr)
        return 1


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_migrations.py [local|operations|all]" " <alembic-args>")
        print()
        print("Examples:")
        print("  python scripts/run_migrations.py local upgrade head")
        print(
            "  python scripts/run_migrations.py operations revision --autogenerate -m"
            " 'add pipeline table'"
        )
        print("  python scripts/run_migrations.py all upgrade head")
        print(
            "  python scripts/run_migrations.py local upgrade head --local-db-url"
            " sqlite:///./custom.db"
        )
        sys.exit(1)

    database = sys.argv[1]
    alembic_args = sys.argv[2:]

    # Extract database URL arguments if provided
    local_db_url = None
    operations_db_url = None

    if "--local-db-url" in alembic_args:
        idx = alembic_args.index("--local-db-url")
        if idx + 1 < len(alembic_args):
            local_db_url = alembic_args[idx + 1]
            alembic_args = alembic_args[:idx] + alembic_args[idx + 2 :]
        else:
            print("Error: --local-db-url requires a value", file=sys.stderr)
            sys.exit(1)

    if "--operations-db-url" in alembic_args:
        idx = alembic_args.index("--operations-db-url")
        if idx + 1 < len(alembic_args):
            operations_db_url = alembic_args[idx + 1]
            alembic_args = alembic_args[:idx] + alembic_args[idx + 2 :]
        else:
            print("Error: --operations-db-url requires a value", file=sys.stderr)
            sys.exit(1)

    if database in ("all", "local", "operations"):
        config_local_url, config_operations_url = config_database_urls()
        local_db_url = local_db_url or config_local_url
        operations_db_url = operations_db_url or config_operations_url
        if database in ("all", "local"):
            print(f"local.db: {local_db_url}")
        if database in ("all", "operations"):
            print(f"operations.db: {operations_db_url}")

    if database == "all":
        print("Running migrations for local.db...")
        ret_local = run_migrations("local", alembic_args, local_db_url=local_db_url)
        if ret_local != 0:
            print(
                "Error: local.db migrations failed with exit code",
                ret_local,
                file=sys.stderr,
            )
            return ret_local
        print()
        print("Running migrations for operations.db...")
        ret_ops = run_migrations("operations", alembic_args, operations_db_url=operations_db_url)
        if ret_ops != 0:
            print(
                "Error: operations.db migrations failed with exit code",
                ret_ops,
                file=sys.stderr,
            )
        return ret_ops
    else:
        return run_migrations(
            database,
            alembic_args,
            local_db_url=local_db_url,
            operations_db_url=operations_db_url,
        )


if __name__ == "__main__":
    sys.exit(main())
