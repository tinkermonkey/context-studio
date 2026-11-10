"""
Each database's Alembic migrations form one chain (one head).

Lanes add migrations in parallel; two migrations on the same parent merge
cleanly in git but leave two heads, and `upgrade head` then fails. This
catches it in CI: regenerate the later migration on the current head.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

SQLITE_DIR = Path(__file__).resolve().parents[4] / "adapters" / "persistence" / "sqlite"


@pytest.mark.parametrize(
    "database, versions",
    [
        ("local.db", SQLITE_DIR / "versions"),
        ("operations.db", SQLITE_DIR / "operations" / "versions"),
    ],
)
def test_migrations_have_one_head(database, versions):
    config = Config(str(SQLITE_DIR / "alembic.ini"))
    config.set_main_option("version_locations", str(versions))

    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1, (
        f"{database} has {len(heads)} Alembic heads {sorted(heads)}: delete the newer"
        " migration and regenerate it with autogenerate on the current head"
    )
