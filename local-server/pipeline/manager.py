"""
Operations Database Manager for handling operational data independently of datasets.

This includes pipeline configurations, audit logs, and task management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from utils.logger import get_logger

logger = get_logger(__name__)


class OperationsDatabaseManager:
    """Manages the operations database independently of dataset databases."""
    
    def __init__(self, operations_db_path: str = None):
        """
        Initialize operations database manager.

        Args:
            operations_db_path: Path to operations database file. If None, uses default location.
        """
        if operations_db_path is None:
            # Use config path for operations database
            from config import get_settings
            settings = get_settings()
            operations_db_path = settings.database.operations_path
        
        self.operations_db_path = operations_db_path
        self.engine = None
        self.session_local = None
        self.logger = logger

        # Ensure datafiles directory exists
        db_dir = os.path.dirname(self.operations_db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the operations database connection and schema."""
        try:
            # Create SQLite engine for operations database
            # Use NullPool to avoid readonly connection caching issues in E2E tests
            self.engine = create_engine(
                f"sqlite:///{self.operations_db_path}",
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20
                },
                poolclass=NullPool,  # Don't pool connections - create fresh each time
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
            
            logger.info(f"Operations database initialized: {self.operations_db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize operations database: {e}")
            raise
    
    def _create_schema(self):
        """
        Create/update operations database schema automatically.
        
        Uses SQLAlchemy's metadata.create_all() which:
        - Creates new tables if they don't exist
        - Adds new columns to existing tables
        - Preserves existing data
        - Does NOT drop columns (safe for schema evolution)
        
        No manual migrations needed!
        """
        from operations.models import OperationsBase
        
        # Auto-create/update all tables defined in operations.models
        OperationsBase.metadata.create_all(bind=self.engine)
        
        logger.info("Operations database schema created/updated automatically")
    
    def get_session(self):
        """Get a database session for pipeline operations."""
        if not self.session_local:
            raise RuntimeError("Operations database not initialized")
        return self.session_local()
    
    def get_engine(self):
        """Get the database engine for pipeline operations."""
        if not self.engine:
            raise RuntimeError("Operations database not initialized")
        return self.engine


# Global instance
_operations_db_manager = None


def get_operations_database_manager() -> OperationsDatabaseManager:
    """Get the global operations database manager instance."""
    global _operations_db_manager
    if _operations_db_manager is None:
        _operations_db_manager = OperationsDatabaseManager()
    return _operations_db_manager


# Backward compatibility aliases
PipelineDatabaseManager = OperationsDatabaseManager
_operations_db_manager = None


def get_pipeline_database_manager() -> OperationsDatabaseManager:
    """
    Get the global operations database manager instance.
    
    DEPRECATED: Use get_operations_database_manager() instead.
    Kept for backward compatibility.
    """
    return get_operations_database_manager()


def get_pipeline_session():
    """
    Get a database session for pipeline operations.
    
    DEPRECATED: Use get_operations_database_manager().get_session() instead.
    """
    manager = get_operations_database_manager()
    return manager.get_session()


def get_pipeline_engine():
    """
    Get the database engine for pipeline operations.
    
    DEPRECATED: Use get_operations_database_manager().get_engine() instead.
    """
    manager = get_operations_database_manager()
    return manager.get_engine()
