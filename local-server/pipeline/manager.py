"""
Pipeline Database Manager for handling pipeline configurations independently of datasets.
"""

import os
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
