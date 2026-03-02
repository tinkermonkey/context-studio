# Disable tokenizers parallelism warning (must be set before importing transformers/tokenizers)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import uvicorn
import argparse
import re
import time
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import create_engine

# Import root-level config module first to avoid shadowing
import config as config_module
from api import graph, datasets, nlp_analysis, schema, predicates, llm, pipeline_flavors
from api import reference, config, structure_nodes, version_management, sync, llm_traceability
from api import changeset_management, proposal_management, identity_management
from api import (
    conflict_resolution,
    analytics,
    incremental_sync,
    optimization,
    embeddings,
    model_capabilities,
    enabled_models,
)
from api import background_tasks, rag_pipeline, rag_experiments, change_events, health
from api.admin import service_monitoring, database_monitoring, event_processor_monitoring
from api.graph import get_cached_graph_service, invalidate_graph_cache
from database.migrations.migration_manager import MigrationManager
from database.utils import (
    init_db,
    get_db,
    get_dataset_manager,
    get_current_engine,
    cleanup_database_resources,
    get_database_manager,
    get_current_session_local,
)
from services.service_factory import ServiceFactory, set_service_factory
from services.task_manager import initialize_task_manager, shutdown_task_manager
from services.version_manager import VersionManager
from services.working_tree_manager import WorkingTreeManager
from pipeline.manager import get_pipeline_database_manager
from nlp.pipeline import get_pipeline
from utils.access_log_middleware import AccessLogMiddleware
from utils.event_processor import create_event_processor
from utils.logger import get_logger
from langchain_community.cache import SQLiteCache
from langchain.globals import set_llm_cache
from reference_db.manager import get_reference_manager, cleanup_reference_manager
from reference_db.config import ReferenceConfig

logger = get_logger(__name__)


# Dependency injection for testability
def create_app(dataset_id=None, engine=None, session_local=None, service_factory=None):
    logger.info("Creating FastAPI application...")

    @asynccontextmanager
    async def lifespan(app):
        try:
            logger.info("Initializing application-level Database Manager...")
            app.state.database_manager = get_database_manager()

            logger.info("Initializing application-level Service Factory...")
            if service_factory is not None:
                # Use provided service factory (for testing)
                app.state.service_factory = service_factory
            else:
                # Create new service factory for production
                app.state.service_factory = ServiceFactory(cache_ttl_seconds=3600)
            set_service_factory(app.state.service_factory)  # Set module-level reference

            # Try to get dataset manager (returns None if not configured or directory doesn't exist)
            dataset_manager = get_dataset_manager()
            active_dataset = None

            if dataset_manager is None:
                # Dataset manager disabled (no datasets directory configured or it doesn't exist)
                # Use direct database access mode
                logger.info("Dataset manager not available - using direct database access from config")
                logger.info("Initializing database...")

                if engine:
                    init_db(engine=engine)
                else:
                    # Create engine from config settings
                    settings = config_module.get_settings()
                    fresh_engine = create_engine(settings.database.default_url, poolclass=None)
                    init_db(engine=fresh_engine)
                logger.info("Database initialized.")
            else:
                # Dataset manager available - use it
                logger.info("Initializing dataset management...")

                # Set active dataset
                if dataset_id:
                    # Explicit dataset specified (for testing or specific startup)
                    success = dataset_manager.switch_dataset(dataset_id)
                    if not success:
                        logger.error(f"Failed to switch to specified dataset: {dataset_id}")
                        raise RuntimeError(f"Cannot start with dataset {dataset_id}")
                elif not dataset_manager.get_active_dataset():
                    # No active dataset - check if any datasets exist
                    existing_datasets = dataset_manager.list_datasets()
                    if existing_datasets:
                        # Use the most recently accessed dataset
                        most_recent = max(existing_datasets, key=lambda d: d.last_accessed)
                        logger.info(f"No active dataset set, using most recent: {most_recent.title}")
                        dataset_manager.switch_dataset(most_recent.id)
                    else:
                        # No datasets exist at all - create default
                        logger.info("No datasets found, creating default dataset...")
                        dataset_manager.create_dataset("Default Dataset", "default.db")

                # Get active dataset for later use
                active_dataset = dataset_manager.get_active_dataset()

                # Initialize database with current active dataset
                logger.info("Initializing database...")
                init_db(engine=engine or get_current_engine())
                logger.info("Database initialized.")

            # Initialize operations database (independent of datasets)
            logger.info("Initializing operations database...")
            operations_db_manager = get_pipeline_database_manager()
            logger.info("Operations database initialized.")

            # Configure LLM response caching to reduce API calls and costs
            # Note: This is separate from the reference-api-buddy proxy which handles
            # reference data sources (ConceptNet, DBpedia, etc.) but not LLM APIs
            try:
                cache_path = operations_db_manager.operations_db_path.replace(".db", "_llm_cache.db")
                set_llm_cache(SQLiteCache(database_path=cache_path))
                logger.info(f"LLM response caching enabled: {cache_path}")
            except Exception as e:
                logger.warning(f"Failed to enable LLM caching: {e}")

            # Run migrations to ensure schema is up to date
            if dataset_manager is None:
                # Direct database mode: run migrations on config database
                # Skip if a test engine was explicitly provided (test mode)
                if engine is None:
                    settings = config_module.get_settings()
                    # Extract file path from SQLite URL (sqlite:///./path/to/file.db)
                    db_url = settings.database.default_url
                    if db_url.startswith("sqlite:///"):
                        db_path = db_url.replace("sqlite:///", "")
                        # Ensure the directory exists (os is imported at module level)
                        os.makedirs(os.path.dirname(db_path), exist_ok=True)
                        MigrationManager(db_path).migrate_to_latest()
                        logger.info(f"Database migrations applied to: {db_path}")
            else:
                # Dataset manager mode: run migrations on active dataset
                active_dataset = dataset_manager.get_active_dataset()
                if active_dataset:
                    dataset_path = dataset_manager.get_dataset_file_path(active_dataset.filename)
                    MigrationManager(dataset_path).migrate_to_latest()
                    logger.info(f"Database migrations applied for dataset: {active_dataset.title}")
                else:
                    logger.warning("No active dataset found after initialization.")

            # Initialize event processor with version management support
            if dataset_manager is not None and active_dataset:
                # Get the database URL instead of passing the engine
                current_engine = get_current_engine()
                if current_engine is None:
                    logger.warning("No current engine available, skipping event processor initialization")
                    app.state.event_processor = None
                else:
                    database_url = str(current_engine.url)

                    # Create version manager and working tree manager for event processor
                    try:
                        # Use the session_local that was provided to create_app, not the global one
                        session_maker = session_local or get_current_session_local()
                        if session_maker is None:
                            raise RuntimeError("No session local available for version manager")

                        db_session = session_maker()
                        version_manager = VersionManager(db_session)
                        working_tree_manager = WorkingTreeManager(db_session, version_manager)
                        logger.info("VersionManager and WorkingTreeManager created for EventProcessor")

                        # Initialize Event Processor with full version management
                        app.state.event_processor = create_event_processor(
                            database_url=database_url,
                            version_manager=version_manager,
                            working_tree_manager=working_tree_manager,
                        )
                        app.state.event_processor.start()
                        logger.info(
                            f"Event processor started with full version management for dataset: {active_dataset.title}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to initialize version management services: {e}")
                        # Fall back to event processor without version management
                        app.state.event_processor = create_event_processor(database_url=database_url)
                        app.state.event_processor.start()
                        logger.warning(
                            f"Event processor started without version management for dataset: {active_dataset.title}"
                        )
            else:
                app.state.event_processor = None

            # Skip warmup if dataset manager is not available (these services depend on it)
            if dataset_manager is not None:
                # Preload NLP pipeline to reduce API response times
                logger.info("Preloading NLP pipeline...")
                try:
                    pipeline = get_pipeline()
                    if pipeline.get_nlp() is not None:
                        pipeline.process("Welcome")
                        logger.info("NLP pipeline successfully preloaded")
                    else:
                        error_msg = pipeline.get_error()
                        logger.warning(f"NLP pipeline preload failed: {error_msg}")
                except Exception as e:
                    logger.error(f"Error preloading NLP pipeline: {e}")

                # Preload GraphService to eliminate first-request delay
                logger.info("Warming up GraphService...")
                try:
                    graph_service = get_cached_graph_service()
                    if graph_service:
                        logger.info("GraphService successfully warmed up and cached")
                    else:
                        logger.warning("GraphService warmup returned None")
                except Exception as e:
                    logger.error(f"Error warming up GraphService: {e}")
                    # Continue startup even if GraphService fails to warm up
                    logger.info("Continuing startup despite GraphService warmup failure")
            else:
                logger.info("Skipping NLP and GraphService warmup (dataset manager not available)")

            # Preload Reference Database Manager and Embedding Model
            logger.info("Warming up Reference Database and Embedding Model...")
            try:
                # Initialize singleton reference manager (creates engine/session)
                ref_config = ReferenceConfig()
                ref_manager = get_reference_manager(ref_config)

                # Warm up embedding model with a test query
                # This loads the SentenceTransformer model into memory (~1.5s first call)
                logger.info("Loading embedding model (this may take a moment)...")
                warmup_start = time.perf_counter()

                # Test search to warm up both embedding model and vector search
                ref_manager.search_external_predicates_by_similarity(
                    query_text="test warmup query", limit=1, threshold=0.5
                )

                warmup_time = (time.perf_counter() - warmup_start) * 1000
                logger.info(f"Reference DB and Embedding Model warmed up successfully in {warmup_time:.0f}ms")
                logger.info("Subsequent embedding/search operations will be fast (~20-50ms)")

            except Exception as e:
                logger.error(f"Error warming up Reference DB/Embeddings: {e}")
                # Continue startup even if warmup fails
                logger.info("Continuing startup despite Reference DB warmup failure")

            # Phase 4: Initialize TaskManager for background task processing
            # This initializes the asyncio-based background task management system
            # that handles long-running operations like predicate discovery and mapping.
            # The TaskManager provides:
            # - Asyncio queue for task submission (max 100 pending tasks)
            # - Progress tracking and task cancellation support
            # - Dead letter queue for failed tasks (max 1000 entries)
            # - Sequential task processing to control resource usage
            logger.info("Initializing TaskManager for background task processing...")
            try:
                task_manager = initialize_task_manager(max_queue_size=100, max_dlq_size=1000)
                await task_manager.start()
                app.state.task_manager = task_manager
                logger.info("TaskManager initialized and started successfully")
            except Exception as e:
                logger.error(f"Failed to initialize TaskManager: {e}")
                # Continue startup even if TaskManager fails
                app.state.task_manager = None

            yield
        finally:
            # Shutdown TaskManager
            if hasattr(app.state, "task_manager") and app.state.task_manager:
                try:
                    await shutdown_task_manager()
                    logger.info("TaskManager shut down successfully")
                except Exception as e:
                    logger.warning(f"Error shutting down TaskManager: {e}")

            if hasattr(app.state, "event_processor") and app.state.event_processor:
                app.state.event_processor.stop()

            # Clean up reference database manager
            try:
                cleanup_reference_manager()
                logger.info("Reference database manager cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up reference manager: {e}")

            # Clean up graph service cache
            try:
                invalidate_graph_cache()
            except Exception as e:
                logger.warning(f"Error invalidating graph cache: {e}")

            # Clean up database resources and event listeners
            cleanup_database_resources()
            logger.info("Shutting down application.")

    app = FastAPI(lifespan=lifespan)

    # Dependency override for DB session
    if session_local:

        def _get_db():
            db = session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _get_db

    # Health check endpoint (no prefix for simplicity)
    app.include_router(health.router, tags=["health"])

    # Using unified structure_nodes API instead of separate layers/domains/terms
    app.include_router(structure_nodes.router, tags=["structure_nodes"])
    app.include_router(predicates.router, prefix="/api/predicates", tags=["predicates"])
    app.include_router(change_events.router, tags=["change_events"])
    app.include_router(version_management.router, tags=["version_management"])
    app.include_router(graph.router, prefix="/api", tags=["graph"])
    app.include_router(datasets.router, prefix="/api", tags=["datasets"])
    app.include_router(schema.router, prefix="/api", tags=["schema"])
    app.include_router(config.router)
    app.include_router(nlp_analysis.router, prefix="/api", tags=["nlp"])
    app.include_router(llm.router, prefix="/api", tags=["llm"])
    app.include_router(llm_traceability.router, tags=["llm-traceability"])
    app.include_router(pipeline_flavors.router, tags=["pipeline-flavors"])
    app.include_router(model_capabilities.router, tags=["model-capabilities"])
    app.include_router(enabled_models.router, tags=["enabled-models"])
    app.include_router(reference.router, prefix="", tags=["nlp-reference"])
    app.include_router(sync.router, tags=["sync"])

    # Phase 2: Administrative monitoring endpoints for service factory
    app.include_router(service_monitoring.router, tags=["service-monitoring"])

    # Phase 3: Collaboration workflow APIs
    app.include_router(changeset_management.router, tags=["changeset-management"])
    app.include_router(proposal_management.router, tags=["proposal-management"])
    app.include_router(identity_management.router, tags=["identity-management"])

    # Phase 3: Enhanced database management monitoring endpoints
    app.include_router(database_monitoring.router, tags=["database-monitoring"])

    # Enhanced Event Processor monitoring endpoints
    app.include_router(event_processor_monitoring.router, tags=["event-processor-monitoring"])

    # Phase 4: Advanced collaborative features
    app.include_router(conflict_resolution.router, tags=["conflict-resolution"])
    app.include_router(analytics.router, tags=["analytics"])
    app.include_router(incremental_sync.router, tags=["incremental-sync"])

    # Phase 4: Background task management
    app.include_router(background_tasks.router, tags=["background-tasks"])

    # Phase 5: Enterprise-scale optimization features
    app.include_router(optimization.router, tags=["optimization"])

    # Embeddings management
    app.include_router(embeddings.router, tags=["embeddings"])

    # Phase 5: RAG Pipeline for entity extraction
    app.include_router(rag_pipeline.router, prefix="/api/rag", tags=["rag-pipeline"])

    # Phase 5: RAG Experiments for pipeline testing and comparison
    app.include_router(rag_experiments.router, tags=["rag-experiments"])

    # Add global exception handler to sanitize error messages
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Global exception handler to sanitize error messages.

        Removes file system paths and other sensitive information from error messages
        to prevent information disclosure.
        """
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        # Get the error message
        error_msg = str(exc)

        # Sanitize file paths (Unix and Windows style)
        # Remove absolute paths like /workspace/, /home/, C:\, etc.
        error_msg = re.sub(r"/[\w\-/]+/[\w\-./]+\.py", "[REDACTED]", error_msg)
        error_msg = re.sub(r"[A-Z]:\\[\w\-\\]+\\[\w\-.\\]+\.py", "[REDACTED]", error_msg)
        error_msg = re.sub(r"/workspace/[\w\-./]+", "[REDACTED]", error_msg)
        error_msg = re.sub(r"/home/[\w\-./]+", "[REDACTED]", error_msg)
        error_msg = re.sub(r"/usr/[\w\-./]+", "[REDACTED]", error_msg)
        error_msg = re.sub(r"/local-server/[\w\-./]+", "[REDACTED]", error_msg)

        # Return generic error response
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": error_msg})

    return app


# Default app for production
# Dataset manager will be initialized on-demand based on configuration
app = create_app()

# Add access logging middleware
app.add_middleware(AccessLogMiddleware)

# Get configuration for CORS
cors_settings = config_module.get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    # Get settings
    settings = config.get_settings()

    parser = argparse.ArgumentParser(description="Run the Context Studio FastAPI server.")
    parser.add_argument(
        "--host",
        type=str,
        default=settings.server.host,
        help=f"Host IP to run the server on (default: {settings.server.host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.server.port,
        help=f"Port to run the server on (default: {settings.server.port})",
    )
    args = parser.parse_args()

    try:
        logger.info(f"Starting server on http://{args.host}:{args.port} ...")

        uvicorn.run(
            "app:app",
            host=args.host,
            port=args.port,
            reload=settings.server.reload,
            access_log=settings.server.access_log,
            log_level=settings.server.log_level.value.lower(),
        )
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting.")
