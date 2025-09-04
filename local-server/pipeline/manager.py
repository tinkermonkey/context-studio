"""
Pipeline Database Manager for handling pipeline configurations independently of datasets.
"""

import os
import sqlite3
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from utils.logger import get_logger

logger = get_logger(__name__)


class PipelineDatabaseManager:
    """Manages the pipeline configuration database independently of dataset databases."""
    
    def __init__(self, pipeline_db_path: str = None):
        """
        Initialize pipeline database manager.
        
        Args:
            pipeline_db_path: Path to pipeline database file. If None, uses default location.
        """
        if pipeline_db_path is None:
            # Use datasets directory for pipeline database
            from database.utils import get_dataset_manager
            dataset_manager = get_dataset_manager()
            datasets_dir = dataset_manager.datasets_directory
            os.makedirs(datasets_dir, exist_ok=True)
            pipeline_db_path = os.path.join(datasets_dir, "pipeline_configurations.db")
        
        self.pipeline_db_path = pipeline_db_path
        self.engine = None
        self.session_local = None
        self.logger = logger
        
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the pipeline database connection and schema."""
        try:
            # Create SQLite engine for pipeline database
            self.engine = create_engine(
                f"sqlite:///{self.pipeline_db_path}",
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20
                },
                poolclass=StaticPool,
                echo=False
            )
            
            # Create session factory
            self.session_local = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Load SQLite extensions on each connection
            @event.listens_for(self.engine, "connect")
            def load_extensions(dbapi_connection, connection_record):
                dbapi_connection.enable_load_extension(True)
                try:
                    # Load sqlite-vec extension for vector operations
                    try:
                        import sqlite_vec
                        sqlite_vec.load(dbapi_connection)
                    except ImportError:
                        logger.warning("sqlite_vec not available, vector operations may be limited")
                except Exception as e:
                    logger.warning(f"Failed to load sqlite-vec extension: {e}")
                finally:
                    dbapi_connection.enable_load_extension(False)
            
            # Create schema if it doesn't exist
            self._create_schema()
            
            logger.info(f"Pipeline database initialized: {self.pipeline_db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize pipeline database: {e}")
            raise
    
    def _create_schema(self):
        """Create pipeline database schema if it doesn't exist."""
        with self.engine.connect() as conn:
            # Create pipeline_flavors table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS pipeline_flavors (
                    id TEXT PRIMARY KEY,
                    pipeline TEXT NOT NULL,
                    title TEXT NOT NULL,
                    llm_provider TEXT NOT NULL,
                    llm_model TEXT NOT NULL,
                    llm_config TEXT NOT NULL,  -- JSON string
                    system_prompt TEXT NOT NULL,
                    user_prompt TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(pipeline, title)
                )
            """))
            
            # Create indexes for better performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pipeline_flavors_pipeline 
                ON pipeline_flavors(pipeline)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pipeline_flavors_enabled 
                ON pipeline_flavors(enabled)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pipeline_flavors_created_at 
                ON pipeline_flavors(created_at)
            """))
            
            conn.commit()
            
        logger.info("Pipeline database schema created/verified")
    
    def get_session(self):
        """Get a database session for pipeline operations."""
        if not self.session_local:
            raise RuntimeError("Pipeline database not initialized")
        return self.session_local()
    
    def get_engine(self):
        """Get the database engine for pipeline operations."""
        if not self.engine:
            raise RuntimeError("Pipeline database not initialized")
        return self.engine
    
    def migrate_from_dataset_database(self, dataset_session_local):
        """
        Migrate existing pipeline flavors from a dataset database to pipeline database.
        
        Args:
            dataset_session_local: Session factory for the source dataset database
        """
        migrated_count = 0
        
        try:
            # Get existing flavors from dataset database
            with dataset_session_local() as dataset_db:
                existing_flavors = dataset_db.execute(text("""
                    SELECT id, pipeline, title, llm_provider, llm_model, llm_config,
                           system_prompt, user_prompt, enabled, created_at, updated_at
                    FROM pipeline_flavors
                """)).fetchall()
            
            if not existing_flavors:
                logger.info("No existing pipeline flavors found to migrate")
                return 0
            
            # Insert flavors into pipeline database
            with self.get_session() as pipeline_db:
                for flavor in existing_flavors:
                    # Check if flavor already exists in pipeline database
                    existing = pipeline_db.execute(text("""
                        SELECT id FROM pipeline_flavors WHERE id = :id
                    """), {"id": flavor.id}).fetchone()
                    
                    if not existing:
                        # Insert flavor into pipeline database
                        pipeline_db.execute(text("""
                            INSERT INTO pipeline_flavors 
                            (id, pipeline, title, llm_provider, llm_model, llm_config,
                             system_prompt, user_prompt, enabled, created_at, updated_at)
                            VALUES (:id, :pipeline, :title, :llm_provider, :llm_model, :llm_config,
                                    :system_prompt, :user_prompt, :enabled, :created_at, :updated_at)
                        """), {
                            "id": flavor.id,
                            "pipeline": flavor.pipeline,
                            "title": flavor.title,
                            "llm_provider": flavor.llm_provider,
                            "llm_model": flavor.llm_model,
                            "llm_config": flavor.llm_config,
                            "system_prompt": flavor.system_prompt,
                            "user_prompt": flavor.user_prompt,
                            "enabled": flavor.enabled,
                            "created_at": flavor.created_at,
                            "updated_at": flavor.updated_at
                        })
                        migrated_count += 1
                
                pipeline_db.commit()
            
            logger.info(f"Migrated {migrated_count} pipeline flavors to pipeline database")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Failed to migrate pipeline flavors: {e}")
            raise


# Global instance
_pipeline_db_manager = None


def get_pipeline_database_manager() -> PipelineDatabaseManager:
    """Get the global pipeline database manager instance."""
    global _pipeline_db_manager
    if _pipeline_db_manager is None:
        _pipeline_db_manager = PipelineDatabaseManager()
    return _pipeline_db_manager


def get_pipeline_session():
    """Get a database session for pipeline operations."""
    manager = get_pipeline_database_manager()
    return manager.get_session()


def get_pipeline_engine():
    """Get the database engine for pipeline operations."""
    manager = get_pipeline_database_manager()
    return manager.get_engine()
