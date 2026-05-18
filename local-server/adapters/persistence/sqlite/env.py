import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure local-server root is in path for imports
local_server_root = Path(__file__).parent.parent.parent.parent
if str(local_server_root) not in sys.path:
    sys.path.insert(0, str(local_server_root))

from adapters.persistence.sqlite.models import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Configure version locations based on target database
sqlite_dir = Path(__file__).parent
x_args = context.get_x_argument(as_dictionary=True)

if x_args.get("db") == "operations":
    # For operations database, only include operations migrations
    config.set_main_option("version_locations", str(sqlite_dir / "operations" / "versions"))
    operations_db_url = x_args.get("operations_db_url") or "sqlite:///./operations.db"
    config.set_main_option("sqlalchemy.url", operations_db_url)

    # Import operations models instead of local models
    from adapters.persistence.sqlite.operations.models import (
        OperationsBase,
    )  # noqa: E402

    target_metadata = OperationsBase.metadata
else:
    # For local database, only include local migrations
    config.set_main_option("version_locations", str(sqlite_dir / "versions"))
    local_db_url = x_args.get("local_db_url")
    if local_db_url:
        config.set_main_option("sqlalchemy.url", local_db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target_metadata for local database if not already set
if x_args.get("db") != "operations":
    target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.get_x_argument(as_dictionary=True)
    # Use the sqlalchemy.url already set in config, which respects operations vs local
    url = config.get_main_option("sqlalchemy.url") or "sqlite:///./local.db"
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    config_section = config.get_section(config.config_ini_section) or {}
    # Use the sqlalchemy.url already set in config, which respects operations vs local
    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
