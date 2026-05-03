import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Ensure local-server root is in path for imports
local_server_root = Path(__file__).parent.parent.parent.parent
if str(local_server_root) not in sys.path:
    sys.path.insert(0, str(local_server_root))

try:
    from adapters.persistence.sqlite.operations.models import OperationsBase  # noqa: E402
    target_metadata = OperationsBase.metadata
except ImportError as e:
    raise RuntimeError(
        f"Failed to import OperationsBase for operations database migrations. "
        f"Ensure adapters/persistence/sqlite/operations/models.py exists and is importable. "
        f"Original error: {e}"
    ) from e

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Configure version locations to only include operations.db migrations
# This prevents "multiple head revisions" errors when upgrading
ops_dir = Path(__file__).parent
config.set_main_option("version_locations", str(ops_dir / "versions"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

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
    # x_args is either passed from parent env.py or from context
    try:
        x_args_local = globals().get("x_args", context.get_x_argument(as_dictionary=True))
    except:
        x_args_local = {}
    url = x_args_local.get("operations_db_url") or "sqlite:///./operations.db"
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
    # x_args is either passed from parent env.py or from context
    try:
        x_args_local = globals().get("x_args", context.get_x_argument(as_dictionary=True))
    except:
        x_args_local = {}
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = x_args_local.get("operations_db_url") or "sqlite:///./operations.db"

    connectable = engine_from_config(
        configuration,
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
