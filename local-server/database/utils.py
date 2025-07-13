import sqlite3
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from database.models import Base
from utils.logger import get_logger
import sqlite_vec
import os

logger = get_logger(__name__)

def get_engine(database_url=None, use_static_pool=False, connect_args={"check_same_thread": False}):
    logger.info("SQLite Version: %s", sqlite3.sqlite_version)
    logger.info("SQLite File: %s", sqlite3.__file__)

    if connect_args is None:
        connect_args = {"check_same_thread": False}
    else:
        logger.info("Using custom connect_args: %s", connect_args)

    url = database_url or os.getenv('DATABASE_URL', 'sqlite:///./local.db')
    if use_static_pool and url.startswith("sqlite:///:memory:"):
        from sqlalchemy.pool import StaticPool
        return create_engine(
            url,
            connect_args=connect_args,
            poolclass=StaticPool
        )
    return create_engine(url, connect_args=connect_args)

def get_session_local(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

def init_db(engine=None, skip_vec=False, database_url=None, connect_args=None):
    logger.info("init_db retrieving engine...")
    if engine is None:
        engine = get_engine(database_url=database_url, connect_args=connect_args)

    @event.listens_for(engine, "connect")
    def receive_connect(connection, _):
        try:
            logger.info("Enabling SQLite extensions...")
            connection.enable_load_extension(True)
            sqlite_vec.load(connection)
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to load SQLite vec extension: {e}")
            raise e
        finally:
            # Disable extension loading after use
            logger.info("Extension loaded successfully, disabling further loading.")
            connection.enable_load_extension(False)

    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    # Only create sqlite-vec virtual tables if not running in test/in-memory mode
    url = str(engine.url)
    # Defensive: skip if in-memory, skip_vec True, or SKIP_SQLITE_VEC env var is set
    if not (url.startswith("sqlite:///:memory:") or skip_vec or os.getenv("SKIP_SQLITE_VEC", "0") == "1"):
        from sqlalchemy import text
        with engine.connect() as conn:
            logger.info("Database connection established, checking vec_version...")
            vec_version, = conn.execute(text("select vec_version()")).fetchone()
            logger.info(f"vec_version={vec_version}")

            # Create virtual tables for vector search if not present
            for table in ("terms_vec", "domains_vec", "layers_vec"):
                logger.info(f"Creating virtual table {table} if not exists...")
                conn.execute(text(f'''
                    CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING vec0(
                        id TEXT PRIMARY KEY,
                        title_embedding FLOAT[384],
                        definition_embedding FLOAT[384]
                    );
                '''))

            logger.info(f"Virtual tables created.")
    return engine

def get_db(SessionLocal=None):
    if SessionLocal is None:
        raise RuntimeError("get_db must be called with an explicit SessionLocal. Do not use the default in tests or production; always inject the session.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
