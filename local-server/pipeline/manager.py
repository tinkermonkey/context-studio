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
            
            # Create pipeline_flavor_executions table for LLM traceability
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS pipeline_flavor_executions (
                    id TEXT PRIMARY KEY,
                    pipeline_flavor_id TEXT NOT NULL,
                    pipeline_type TEXT NOT NULL,
                    pipeline_flavor_version INTEGER NOT NULL,
                    request_context TEXT NOT NULL,  -- JSON
                    user_prompt TEXT NOT NULL,
                    response_message TEXT,
                    
                    execution_time_ms INTEGER,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    
                    started_at TEXT DEFAULT (datetime('now')),
                    completed_at TEXT,
                    
                    FOREIGN KEY (pipeline_flavor_id) REFERENCES pipeline_flavors(id) ON DELETE CASCADE
                )
            """))
            
            # Create pipeline_flavor_selections table for user selection tracking
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS pipeline_flavor_selections (
                    id TEXT PRIMARY KEY,
                    pipeline_execution_id TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    suggestion_field TEXT NOT NULL,
                    selected_content TEXT NOT NULL,
                    date_created TEXT DEFAULT (datetime('now')),
                    
                    FOREIGN KEY (pipeline_execution_id) REFERENCES pipeline_flavor_executions(id) ON DELETE CASCADE
                )
            """))
            
            # Create indexes for pipeline_flavors performance
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
            
            # Create indexes for pipeline_flavor_executions performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_executions_flavor_id 
                ON pipeline_flavor_executions(pipeline_flavor_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_executions_pipeline_type 
                ON pipeline_flavor_executions(pipeline_type)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_executions_status 
                ON pipeline_flavor_executions(status)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_executions_started_at 
                ON pipeline_flavor_executions(started_at)
            """))
            
            # Create indexes for pipeline_flavor_selections performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_selections_execution_id 
                ON pipeline_flavor_selections(pipeline_execution_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_selections_record 
                ON pipeline_flavor_selections(record_type, record_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_selections_created 
                ON pipeline_flavor_selections(date_created)
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
