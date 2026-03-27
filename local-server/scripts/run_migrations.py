#!/usr/bin/env python
"""
Utility script to run Alembic migrations for both local.db and operations.db.

Usage:
    python scripts/run_migrations.py local upgrade head
    python scripts/run_migrations.py operations downgrade -1
    python scripts/run_migrations.py all upgrade head

This script abstracts away the need to specify --config and working directories.
"""

import subprocess
import sys
from pathlib import Path

# Get the local-server root directory
LOCAL_SERVER_ROOT = Path(__file__).parent.parent
SQLITE_DIR = LOCAL_SERVER_ROOT / "adapters" / "persistence" / "sqlite"

def run_migrations(database: str, args: list[str]) -> int:
    """Run Alembic command for a specific database."""
    if database not in ["local", "operations"]:
        print(f"Error: Invalid database '{database}'. Must be 'local' or 'operations'.")
        return 1

    config_path = SQLITE_DIR / "alembic.ini"

    # Construct the alembic command
    cmd = [
        "alembic",
        "--config",
        str(config_path),
    ]

    # For operations.db, route using the -x flag
    if database == "operations":
        cmd.extend(["-x", "db=operations"])

    cmd.extend(args)

    # Run the command from the sqlite directory to ensure relative paths work
    return subprocess.run(cmd, cwd=str(SQLITE_DIR)).returncode


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_migrations.py [local|operations] <alembic-args>")
        print("   or: python scripts/run_migrations.py all <alembic-args>  (runs on both)")
        print()
        print("Examples:")
        print("  python scripts/run_migrations.py local upgrade head")
        print("  python scripts/run_migrations.py operations revision --autogenerate -m 'add pipeline table'")
        print("  python scripts/run_migrations.py all upgrade head")
        sys.exit(1)

    database = sys.argv[1]
    alembic_args = sys.argv[2:]

    if database == "all":
        print("Running migrations for local.db...")
        ret_local = run_migrations("local", alembic_args)
        print()
        print("Running migrations for operations.db...")
        ret_ops = run_migrations("operations", alembic_args)
        return max(ret_local, ret_ops)
    else:
        return run_migrations(database, alembic_args)


if __name__ == "__main__":
    sys.exit(main())
