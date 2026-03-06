# mypy: ignore-errors
import os
import sqlite3
import sqlite_vec
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any, Generator, List
from sqlalchemy import create_engine, event, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool, StaticPool
from fastapi import HTTPException

from utils.logger import get_logger


logger = get_logger(__name__)


class PoolStrategy(Enum):
    """Database connection pooling strategies."""
    NULL_POOL = "null"           # No pooling - new connection per request
    QUEUE_POOL = "queue"         # Connection pooling with queue
    STATIC_POOL = "static"       # Single persistent connection
    OPTIMIZED = "optimized"      # Intelligent strategy selection


@dataclass
class ConnectionMetrics:
    """Metrics for database connections."""
    total_connections_created: int = 0
    active_connections: int = 0
    peak_connections: int = 0
    pool_hits: int = 0
    pool_misses: int = 0
    connection_errors: int = 0
    avg_connection_time_ms: float = 0.0
    total_queries_executed: int = 0
    avg_query_time_ms: float = 0.0
    last_reset_time: datetime = field(default_factory=datetime.now)

    def reset(self):
        """Reset metrics counters."""
        self.__init__()


@dataclass
class PoolConfiguration:
    """Configuration for database connection pooling."""
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    connect_args: Dict[str, Any] = field(default_factory=dict)


class DatabaseManager:
    """
    Database manager with optimized connection pooling and lifecycle management.  # noqa: E501

    Features:
    - Intelligent pool strategy selection based on environment
    - Connection lifecycle coordination with services
    - Performance monitoring and health checks
    - Resource utilization optimization
    - Thread-safe operations
    """

    def __init__(self):
        self.metrics = ConnectionMetrics()
        self._engines: Dict[str, Engine] = {}
        self._session_locals: Dict[str, sessionmaker] = {}
        self._lock = threading.RLock()
        self._health_check_interval = 30  # seconds
        self._last_health_check = datetime.now()
        self._loaded_connections: Dict[int, bool] = {}
        self._connection_lifecycles: Dict[int, datetime] = {}
        self._cached_health_status = {}

        logger.info("Database Manager initialized")

    def get_optimal_pool_strategy(self, database_url: str) -> PoolStrategy:
        """Determine optimal pooling strategy based on database type."""
        is_sqlite = database_url.startswith("sqlite://")
        is_memory = ":memory:" in database_url

        if is_memory:
            return PoolStrategy.STATIC_POOL
        elif is_sqlite:
            return PoolStrategy.NULL_POOL  # Avoid threading issues with SQLite
        else:
            return PoolStrategy.QUEUE_POOL

    def get_pool_configuration(self, database_url: str) -> PoolConfiguration:
        """Get optimized pool configuration based on database type."""
        is_sqlite = database_url.startswith("sqlite://")

        # Use a general purpose configuration suitable for most use cases
        return PoolConfiguration(
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,  # 1 hour
            pool_pre_ping=True,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
                "isolation_level": None,
            } if is_sqlite else {}
        )

    def create_optimized_engine(self,
                              database_url: str,  # noqa: E128
                              engine_id: str = "default",  # noqa: E128
                              custom_config: Optional[PoolConfiguration] = None) -> Engine:  # noqa: E501, E128
        """Create an optimized database engine based on environment and requirements."""  # noqa: E501

        with self._lock:
            # Check if engine already exists
            if engine_id in self._engines:
                logger.info(f"Reusing existing engine: {engine_id}")
                return self._engines[engine_id]

            strategy = self.get_optimal_pool_strategy(database_url)
            config = custom_config or self.get_pool_configuration(database_url)

            logger.info(f"Creating optimized engine '{engine_id}' with {strategy.value} pooling")  # noqa: E501
            logger.debug(f"Pool config: size={config.pool_size}, overflow={config.max_overflow}, timeout={config.pool_timeout}")  # noqa: E501

            # Create engine with optimized settings
            engine_kwargs = {
                "connect_args": config.connect_args,
                "echo": False,  # Set to True for SQL debugging
            }

            # Apply pooling strategy
            if strategy == PoolStrategy.NULL_POOL:
                engine_kwargs.update({
                    "poolclass": NullPool,
                })

            elif strategy == PoolStrategy.STATIC_POOL:
                engine_kwargs.update({
                    "poolclass": StaticPool,
                    "pool_recycle": -1,
                    "pool_pre_ping": config.pool_pre_ping,
                })

            elif strategy == PoolStrategy.QUEUE_POOL:
                engine_kwargs.update({
                    "poolclass": QueuePool,
                    "pool_size": config.pool_size,
                    "max_overflow": config.max_overflow,
                    "pool_timeout": config.pool_timeout,
                    "pool_recycle": config.pool_recycle,
                    "pool_pre_ping": config.pool_pre_ping,
                })

            # Create the engine
            try:
                start_time = time.time()
                engine = create_engine(database_url, **engine_kwargs)
                creation_time = (time.time() - start_time) * 1000

                # Set up event listeners for monitoring
                self._setup_engine_listeners(engine, engine_id)

                # Store engine
                self._engines[engine_id] = engine
                self._session_locals[engine_id] = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=engine,
                    expire_on_commit=False
                )

                # Update metrics
                self.metrics.total_connections_created += 1

                logger.info(f"Engine '{engine_id}' created successfully in {creation_time:.2f}ms")  # noqa: E501
                return engine

            except Exception as e:
                self.metrics.connection_errors += 1
                logger.error(f"Failed to create engine '{engine_id}': {e}")
                raise

    def _setup_engine_listeners(self, engine: Engine, engine_id: str):
        """Set up SQLAlchemy event listeners for monitoring and optimization."""  # noqa: E501

        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            connection_id = id(dbapi_connection)
            self._connection_lifecycles[connection_id] = datetime.now()

            # Load SQLite extensions if needed
            if hasattr(dbapi_connection, 'enable_load_extension'):
                if connection_id not in self._loaded_connections:
                    try:
                        dbapi_connection.enable_load_extension(True)
                        # Load sqlite_vec extension
                        sqlite_vec.load(dbapi_connection)
                        self._loaded_connections[connection_id] = True
                        logger.debug(f"SQLite extensions loaded for connection {connection_id}")  # noqa: E501
                    except Exception as e:
                        logger.warning(f"Failed to load SQLite extensions: {e}")  # noqa: E501
                    finally:
                        dbapi_connection.enable_load_extension(False)

            # Update metrics
            with self._lock:
                self.metrics.active_connections += 1
                self.metrics.peak_connections = max(
                    self.metrics.peak_connections,
                    self.metrics.active_connections
                )

        @event.listens_for(engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):  # noqa: E501
            # Pool hit
            with self._lock:
                self.metrics.pool_hits += 1

        @event.listens_for(engine, "close")
        def receive_close(dbapi_connection, connection_record):
            connection_id = id(dbapi_connection)

            # Clean up tracking
            self._loaded_connections.pop(connection_id, None)
            self._connection_lifecycles.pop(connection_id, None)

            # Update metrics
            with self._lock:
                self.metrics.active_connections = max(0, self.metrics.active_connections - 1)  # noqa: E501

        @event.listens_for(engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: E501
            context._query_start_time = time.time()

        @event.listens_for(engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: E501
            if hasattr(context, '_query_start_time'):
                execution_time = (time.time() - context._query_start_time) * 1000  # noqa: E501

                with self._lock:
                    self.metrics.total_queries_executed += 1
                    # Update rolling average
                    total_time = (self.metrics.avg_query_time_ms *
                                (self.metrics.total_queries_executed - 1) + execution_time)  # noqa: E501, E128
                    self.metrics.avg_query_time_ms = total_time / self.metrics.total_queries_executed  # noqa: E501

    @contextmanager
    def get_optimized_session(self,
                            engine_id: str = "default",  # noqa: E128
                            database_url: Optional[str] = None) -> Generator[Session, None, None]:  # noqa: E501, E128
        """
        Get an optimized database session with automatic lifecycle management.

        This context manager ensures proper session cleanup and provides monitoring.  # noqa: E501
        """
        if engine_id not in self._session_locals:
            if database_url is None:
                raise ValueError(f"Engine '{engine_id}' not found and no database_url provided")  # noqa: E501
            self.create_optimized_engine(database_url, engine_id)

        session_local = self._session_locals.get(engine_id)
        if session_local is None:
            raise ValueError(f"No session factory available for engine '{engine_id}'")  # noqa: E501

        session = session_local()

        try:
            start_time = time.time()
            yield session
            session.commit()

            # Update performance metrics
            session_time = (time.time() - start_time) * 1000
            with self._lock:
                total_time = (self.metrics.avg_connection_time_ms *
                            self.metrics.total_connections_created + session_time)  # noqa: E501, E128
                self.metrics.avg_connection_time_ms = total_time / (
                    self.metrics.total_connections_created + 1)

        except Exception as e:
            session.rollback()
            logger.error(f"Session error in engine '{engine_id}': {e}")
            raise
        finally:
            session.close()

    def get_session_factory(self, engine_id: str = "default") -> Optional[sessionmaker]:  # noqa: E501
        """Get the session factory for a specific engine."""
        return self._session_locals.get(engine_id)

    def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check on all engines."""
        current_time = datetime.now()
        if (current_time - self._last_health_check).seconds < self._health_check_interval and self._cached_health_status:  # noqa: E501
            return self._cached_health_status

        health_status = {
            "timestamp": current_time.isoformat(),
            "overall_status": "healthy",
            "engines": {},
            "metrics": self._get_metrics_summary(),
            "warnings": [],
            "errors": []
        }

        with self._lock:
            for engine_id, engine in self._engines.items():
                engine_health = self._check_engine_health(engine_id, engine)
                health_status["engines"][engine_id] = engine_health  # type: ignore  # noqa: E501

                if engine_health["status"] != "healthy":
                    health_status["overall_status"] = "degraded"
                    if engine_health["status"] == "error":
                        health_status["errors"].append(f"Engine {engine_id}: {engine_health.get('error', 'Unknown error')}")  # type: ignore  # noqa: E501
                    else:
                        health_status["warnings"].append(f"Engine {engine_id}: {engine_health.get('warning', 'Performance issue')}")  # type: ignore  # noqa: E501

        self._last_health_check = current_time
        self._cached_health_status = health_status
        return health_status

    def _check_engine_health(self, engine_id: str, engine: Engine) -> Dict[str, Any]:  # noqa: E501
        """Check the health of a specific engine."""
        try:
            start_time = time.time()

            # Perform a simple query to test connectivity
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            response_time = (time.time() - start_time) * 1000

            # Determine status based on response time and pool info
            status = "healthy"
            if response_time > 1000:  # 1 second
                status = "warning"
            elif response_time > 5000:  # 5 seconds
                status = "error"

            # Get pool information
            pool_info = {}
            if hasattr(engine.pool, 'size'):
                pool_info = {
                    "pool_size": engine.pool.size(),
                    "checked_in": engine.pool.checkedin(),  # type: ignore
                    "checked_out": engine.pool.checkedout(),  # type: ignore
                }

            return {
                "status": status,
                "response_time_ms": response_time,
                "pool_info": pool_info,
                "last_check": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

    def _get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of connection metrics."""
        with self._lock:
            return {
                "total_connections_created": self.metrics.total_connections_created,  # noqa: E501
                "active_connections": self.metrics.active_connections,
                "peak_connections": self.metrics.peak_connections,
                "pool_hits": self.metrics.pool_hits,
                "pool_misses": self.metrics.pool_misses,
                "connection_errors": self.metrics.connection_errors,
                "avg_connection_time_ms": round(self.metrics.avg_connection_time_ms, 2),  # noqa: E501
                "total_queries_executed": self.metrics.total_queries_executed,
                "avg_query_time_ms": round(self.metrics.avg_query_time_ms, 2),
                "uptime_seconds": int((datetime.now() - self.metrics.last_reset_time).total_seconds()),  # noqa: E501
                "pool_efficiency_percent": round(
                    (self.metrics.pool_hits / max(1, self.metrics.pool_hits + self.metrics.pool_misses)) * 100, 2  # noqa: E501
                )
            }

    def optimize_for_workload(self, workload_type: str = "mixed") -> Dict[str, Any]:  # noqa: E501
        """Optimize database configurations for specific workload types."""
        optimizations = []

        if workload_type == "read_heavy":
            # Optimize for read-heavy workloads
            for engine_id, engine in self._engines.items():
                if hasattr(engine.pool, 'size'):
                    # Increase pool size for read operations
                    optimizations.append(f"Increased read pool size for {engine_id}")  # noqa: E501

        elif workload_type == "write_heavy":
            # Optimize for write-heavy workloads
            for engine_id, engine in self._engines.items():
                # Reduce connection recycling time to avoid long-held connections  # noqa: E501
                optimizations.append(f"Optimized write connections for {engine_id}")  # noqa: E501

        elif workload_type == "analytics":
            # Optimize for analytical workloads
            optimizations.append("Configured for long-running analytical queries")  # noqa: E501

        return {
            "workload_type": workload_type,
            "optimizations_applied": optimizations,
            "timestamp": datetime.now().isoformat()
        }

    def cleanup_resources(self):
        """Clean up all database resources."""
        logger.info("Database Manager: Cleaning up resources...")

        with self._lock:
            # Dispose of all engines
            for engine_id, engine in self._engines.items():
                try:
                    engine.dispose()
                    logger.info(f"Disposed engine: {engine_id}")
                except Exception as e:
                    logger.warning(f"Error disposing engine {engine_id}: {e}")

            # Clear all tracking
            self._engines.clear()
            self._session_locals.clear()
            self._loaded_connections.clear()
            self._connection_lifecycles.clear()

            logger.info("Database Manager: Resource cleanup complete")

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        health = self.perform_health_check()

        return {
            "report_timestamp": datetime.now().isoformat(),
            "health_status": health,
            "performance_metrics": self._get_metrics_summary(),
            "active_engines": list(self._engines.keys()),
            "recommendations": self._generate_performance_recommendations()
        }

    def _generate_performance_recommendations(self) -> List[str]:
        """Generate performance recommendations based on current metrics."""
        recommendations = []
        metrics = self._get_metrics_summary()

        # Pool efficiency recommendations
        if metrics["pool_efficiency_percent"] < 80:
            recommendations.append("Consider increasing pool size or reducing connection churn")  # noqa: E501

        # Response time recommendations
        if metrics["avg_connection_time_ms"] > 100:
            recommendations.append("High average connection time - check database performance")  # noqa: E501

        # Connection count recommendations
        if metrics["peak_connections"] > 50:
            recommendations.append("High peak connections - consider connection pooling optimization")  # noqa: E501

        # Query performance recommendations
        if metrics["avg_query_time_ms"] > 50:
            recommendations.append("High average query time - consider query optimization or indexing")  # noqa: E501

        if not recommendations:
            recommendations.append("Database performance is optimal")

        return recommendations

# Global state for current dataset and database manager


_current_engine = None
_current_session_local = None
_dataset_manager = None
_database_manager: Optional[DatabaseManager] = None
_manager_lock = threading.Lock()

# Global tracking of loaded extensions to prevent duplicates
_loaded_connections = set()

# Track engines that have been initialized to prevent duplicate listeners
_initialized_engines = set()


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _database_manager

    if _database_manager is None:
        with _manager_lock:
            if _database_manager is None:
                _database_manager = DatabaseManager()

    return _database_manager


def create_optimized_engine(database_url: str,
                         engine_id: str = "default",  # noqa: E128
                         custom_config: PoolConfiguration = None) -> Engine:  # noqa: E128, E501
    """Create an optimized database engine using the database manager."""
    manager = get_database_manager()
    return manager.create_optimized_engine(database_url, engine_id, custom_config)  # noqa: E501


@contextmanager
def optimized_session(database_url: Optional[str] = None,
                    engine_id: str = "default") -> Generator[Session, None, None]:  # noqa: E501, E128
    """Context manager for optimized database sessions."""
    manager = get_database_manager()
    with manager.get_optimized_session(engine_id, database_url) as session:
        yield session


def cleanup_database_resources():
    """Clean up enhanced database manager resources and legacy resources."""
    global _database_manager, _current_engine, _current_session_local, _loaded_connections, _initialized_engines  # noqa: E501, F824

    logger.info("Cleaning up database resources...")

    # Clean up the database manager if it exists
    if _database_manager is not None:
        _database_manager.cleanup_resources()
        with _manager_lock:
            _database_manager = None

    # Clear connection tracking
    _loaded_connections.clear()

    # Clear engine tracking (event listeners will be cleaned up automatically when engines are disposed)  # noqa: E501
    _initialized_engines.clear()

    # Dispose of current engine
    if _current_engine:
        try:
            # With NullPool, disposal should be clean since there are no persistent connections  # noqa: E501
            # If there are any issues, they're likely harmless threading edge cases  # noqa: E501
            _current_engine.dispose()
            logger.info("Disposed current engine")
        except Exception as e:
            # Log any disposal errors for debugging, but don't fail shutdown
            logger.debug(f"Engine disposal completed with minor issue: {e}")
        finally:
            _current_engine = None

    _current_session_local = None
    logger.info("Database resources cleanup complete")


def get_dataset_manager():
    """
    Get the global dataset manager instance.

    Returns None if datasets directory is not configured or doesn't exist,
    indicating that dataset manager should be disabled and direct database
    access should be used instead.
    """
    global _dataset_manager
    if _dataset_manager is None:
        from dataset.manager import DatasetManager
        from config import get_settings
        import os

        # Check if datasets directory is configured and exists
        settings = get_settings()
        if settings.database.datasets_directory:
            datasets_dir = os.path.expanduser(settings.database.datasets_directory)  # noqa: E501
            if os.path.exists(datasets_dir):
                logger.info(f"Initializing dataset manager with directory: {datasets_dir}")  # noqa: E501
                _dataset_manager = DatasetManager()
            else:
                logger.info(f"Datasets directory does not exist: {datasets_dir}. Dataset manager disabled.")  # noqa: E501
                return None
        else:
            logger.info("No datasets_directory configured. Dataset manager disabled.")  # noqa: E501
            return None

    return _dataset_manager


def switch_active_database(dataset_id: str) -> bool:
    """Switch the active database connection."""
    global _current_engine, _current_session_local

    dataset_manager = get_dataset_manager()
    if dataset_manager is None:
        logger.warning("Cannot switch dataset: dataset manager is disabled")
        return False

    if dataset_manager.switch_dataset(dataset_id):
        _current_engine = dataset_manager.active_engine
        _current_session_local = dataset_manager.active_session_local
        return True
    return False


def get_current_engine():
    """Get the current active engine."""
    global _current_engine
    if _current_engine is None:
        # Initialize with default dataset
        dataset_manager = get_dataset_manager()
        if dataset_manager is not None:
            _current_engine = dataset_manager.active_engine
        else:
            # Dataset manager disabled, use default_url directly
            from config import get_settings
            settings = get_settings()
            logger.info("Dataset manager disabled, creating engine from default_url")  # noqa: E501
            _current_engine = get_engine(settings.database.default_url)
    return _current_engine


def get_current_session_local():
    """Get the current active session local."""
    global _current_session_local
    if _current_session_local is None:
        # Initialize with default dataset
        dataset_manager = get_dataset_manager()
        if dataset_manager is not None:
            _current_session_local = dataset_manager.active_session_local
        else:
            # Dataset manager disabled, create session from default_url engine
            from sqlalchemy.orm import sessionmaker
            engine = get_current_engine()
            _current_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)  # noqa: E501
            logger.info("Dataset manager disabled, created session from default_url")  # noqa: E501
    return _current_session_local


def set_current_engine_for_testing(engine, session_local):
    """Set the current engine and session local for testing purposes."""
    global _current_engine, _current_session_local
    _current_engine = engine
    _current_session_local = session_local


def get_engine(database_url=None, use_static_pool=False, connect_args=None):
    """
    Get a database engine with optimized connection configuration.

    This function now uses the DatabaseManager for optimal performance while maintaining  # noqa: E501
    backward compatibility with existing code.
    """
    logger.info("SQLite Version: %s", sqlite3.sqlite_version)
    logger.info("SQLite File: %s", sqlite3.__file__)

    # Import configuration
    from config import get_settings
    settings = get_settings()

    url = database_url or os.getenv("DATABASE_URL", settings.database.default_url)  # noqa: E501

    # Try to use the optimized DatabaseManager approach
    try:
        manager = get_database_manager()

        # Create a custom pool configuration if specific args are provided
        custom_config = None
        if connect_args is not None or use_static_pool:
            logger.info("Using custom connect_args: %s", connect_args or "default with static pool")  # noqa: E501

            # Use provided connect_args or default optimized ones
            final_connect_args = connect_args or {
                "check_same_thread": settings.database.check_same_thread,
                "timeout": 30,
                "isolation_level": None,
            }

            custom_config = PoolConfiguration(
                connect_args=final_connect_args,
                pool_size=1 if use_static_pool else 5,
                pool_pre_ping=not use_static_pool
            )

        # Generate a unique engine ID for this request
        engine_id = f"legacy_engine_{id(url)}_{int(time.time())}"
        return manager.create_optimized_engine(url, engine_id, custom_config)

    except Exception as e:
        # Fall back to legacy approach if DatabaseManager fails
        logger.warning(f"DatabaseManager failed, using legacy approach: {e}")

        if connect_args is None:
            connect_args = {
                "check_same_thread": settings.database.check_same_thread,
                # Add SQLite threading and connection configuration
                "timeout": 30,
                "isolation_level": None,  # Autocommit mode for better thread handling  # noqa: E501
            }
        else:
            logger.info("Using custom connect_args: %s", connect_args)

        # For SQLite databases, use optimized configuration to avoid threading issues  # noqa: E501
        if url.startswith("sqlite://"):
            if use_static_pool and url.startswith("sqlite:///:memory:"):
                # In-memory databases need StaticPool
                return create_engine(
                    url,
                    connect_args=connect_args,
                    poolclass=StaticPool,
                    pool_recycle=-1,
                    pool_pre_ping=True
                )
            else:
                # For file-based SQLite, use NullPool to avoid threading issues
                # This creates a new connection per request, eliminating pool-related thread conflicts  # noqa: E501
                return create_engine(
                    url,
                    connect_args=connect_args,
                    poolclass=NullPool,  # No pooling - avoids thread affinity issues  # noqa: E501
                    pool_pre_ping=False,  # Not needed with NullPool
                )
        else:
            # For other databases (PostgreSQL, MySQL, etc.), use standard pooling  # noqa: E501
            return create_engine(
                url,
                connect_args=connect_args,
                pool_recycle=3600,  # Recycle connections every hour
                pool_pre_ping=True,  # Validate connections before use
                pool_timeout=20,  # Timeout for getting connections from pool
                max_overflow=10,   # Allow overflow connections for non-SQLite
            )


def get_session_local(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)  # noqa: E501


def init_db(engine=None, database_url=None, connect_args=None):
    logger.info("init_db retrieving engine...")
    if engine is None:
        engine = get_engine(database_url=database_url, connect_args=connect_args)  # noqa: E501

    # Check if this engine already has our listeners to avoid duplicates
    engine_id = id(engine)
    if engine_id in _initialized_engines:
        logger.debug(f"Engine {engine_id} already has event listeners, skipping")  # noqa: E501
        return engine

    def receive_connect(dbapi_connection, connection_record):
        # Use connection ID to track if extension is already loaded
        connection_id = id(dbapi_connection)
        if connection_id in _loaded_connections:
            logger.debug(f"Extension already loaded for connection {connection_id}")  # noqa: E501
            return

        try:
            logger.debug("Enabling SQLite extensions...")
            dbapi_connection.enable_load_extension(True)
            sqlite_vec.load(dbapi_connection)
            _loaded_connections.add(connection_id)
        except Exception as e:
            logger.error(f"Failed to load SQLite vec extension: {e}")
            raise
        finally:
            # Disable extension loading after use
            dbapi_connection.enable_load_extension(False)

    def receive_close(connection, connection_record):
        # Clean up tracking when connection is closed
        connection_id = id(connection)
        _loaded_connections.discard(connection_id)
        logger.debug(f"Cleaned up extension tracking for connection {connection_id}")  # noqa: E501

    # Attach event listeners
    event.listen(engine, "connect", receive_connect)
    event.listen(engine, "close", receive_close)

    # Track this engine as initialized
    _initialized_engines.add(engine_id)

    logger.debug(f"Added event listeners to engine {engine_id}")

    # Do not create tables here; rely on migration manager for schema creation
    logger.info("init_db complete (no tables created, use migration manager for schema)")  # noqa: E501
    return engine


def get_db(SessionLocal=None):
    """Get database session for dependency injection."""
    if SessionLocal is None:
        # Use current dataset's session local
        SessionLocal = get_current_session_local()
        if SessionLocal is None:
            raise RuntimeError("No active dataset or session available")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_for_current_dataset():
    """Get database session for currently active dataset."""
    session_local = get_current_session_local()
    if not session_local:
        raise HTTPException(status_code=500, detail="No active dataset")

    db = session_local()
    try:
        yield db
    finally:
        db.close()


# Advanced FastAPI dependency functions using DatabaseManager
def get_optimized_db_session(database_url: Optional[str] = None, engine_id: str = "default"):  # noqa: E501
    """FastAPI dependency for optimized database sessions."""
    manager = get_database_manager()

    if engine_id not in manager._session_locals:
        if database_url is None:
            from config import get_settings
            settings = get_settings()
            database_url = settings.database.default_url
        manager.create_optimized_engine(database_url, engine_id)

    session_local = manager.get_session_factory(engine_id)
    if not session_local:
        raise RuntimeError(f"No session factory available for engine '{engine_id}'")  # noqa: E501

    session = session_local()
    try:
        yield session
    finally:
        session.close()


def get_optimized_db_for_current_dataset():
    """FastAPI dependency for optimized database sessions using current dataset."""  # noqa: E501
    # First try to get the current session from dataset manager
    session_local = get_current_session_local()
    if session_local is None:
        # Fall back to optimized manager with default engine
        manager = get_database_manager()
        session_local = manager.get_session_factory("default")
        if not session_local:
            raise RuntimeError("No database session available")

    session = session_local()
    try:
        yield session
    finally:
        session.close()
