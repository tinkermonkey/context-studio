import sys
import os
import importlib.util
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from alembic.config import Config

# Ensure local-server root is in path for imports
local_server_root = Path(__file__).parent.parent.parent
if str(local_server_root) not in sys.path:
    sys.path.insert(0, str(local_server_root))

from adapters.persistence.sqlite.models import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Check if this is an operations database migration
# If -x db=operations is passed, delegate to operations/env.py
x_args = context.get_x_argument(as_dictionary=True)
if x_args.get("db") == "operations":
    # Programmatically invoke operations environment
    operations_env_path = Path(__file__).parent / "operations" / "env.py"

    if operations_env_path.exists():
        # Load operations config from the same alembic.ini
        operations_config = Config(str(Path(__file__).parent / "alembic.ini"))
        operations_db_url = x_args.get("operations_db_url") or "sqlite:///./operations.db"
        operations_config.set_main_option("sqlalchemy.url", operations_db_url)

        # Import and execute operations environment
        spec = importlib.util.spec_from_file_location("operations_env", operations_env_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Failed to load operations environment from {operations_env_path}")

        operations_env_module = importlib.util.module_from_spec(spec)
        operations_env_module.config = operations_config  # type: ignore[attr-defined]
        operations_env_module.context = context  # type: ignore[attr-defined]
        spec.loader.exec_module(operations_env_module)

        # Operations env has handled the migration
        sys.exit(0)
    else:
        raise FileNotFoundError(f"Operations environment not found at {operations_env_path}")

# add your model's MetaData object here
# for 'autogenerate' support
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
    x_args = context.get_x_argument(as_dictionary=True)
    url = x_args.get("local_db_url") or config.get_main_option("sqlalchemy.url")
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
    x_args = context.get_x_argument(as_dictionary=True)
    config_section = config.get_section(config.config_ini_section) or {}
    config_section["sqlalchemy.url"] = x_args.get("local_db_url") or config_section.get("sqlalchemy.url", "sqlite:///./local.db")
    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
