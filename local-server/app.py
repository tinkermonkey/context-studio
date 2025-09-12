import uvicorn
import argparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from api import graph, datasets, nlp_analysis, schema, predicates, llm, pipeline_flavors
from api import enrichment, config, structure_nodes, version_management, sync, llm_traceability
from api import changeset_management, proposal_management, identity_management
from api import conflict_resolution, analytics, incremental_sync, optimization
from api.admin import service_monitoring
from schema_org import api as schema_org_api
from api.graph import get_cached_graph_service, invalidate_graph_cache
from database.migrations.migration_manager import MigrationManager
from database.utils import (
    init_db, get_db, get_dataset_manager, get_current_engine, cleanup_database_resources,
    get_database_manager
)
from services.service_factory import ServiceFactory, set_service_factory
from pipeline.manager import get_pipeline_database_manager
from nlp.pipeline import get_pipeline
from utils.access_log_middleware import AccessLogMiddleware
from utils.event_processor import create_event_processor
from utils.logger import get_logger

logger = get_logger(__name__)





# Dependency injection for testability
def create_app(dataset_id=None, engine=None, session_local=None, service_factory=None):
    logger.info("Creating FastAPI application...")
    
    @asynccontextmanager
    async def lifespan(app):
        try:
            logger.info(" Initializing application-level Database Manager...")
            app.state.database_manager = get_database_manager()
            
            logger.info("Initializing application-level Service Factory...")
            if service_factory is not None:
                # Use provided service factory (for testing)
                app.state.service_factory = service_factory
            else:
                # Create new service factory for production
                app.state.service_factory = ServiceFactory(cache_ttl_seconds=3600)
            set_service_factory(app.state.service_factory)  # Set module-level reference
                        
            
            # Initialize dataset manager
            logger.info("Initializing dataset management...")
            dataset_manager = get_dataset_manager()
            
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
            
            # Initialize database with current active dataset
            logger.info("Initializing database...")
            init_db(engine=engine or get_current_engine())
            logger.info("Database initialized.")
            
            # Initialize pipeline database (independent of datasets)
            logger.info("Initializing pipeline database...")
            pipeline_db_manager = get_pipeline_database_manager()
            logger.info("Pipeline database initialized.")
            
            # Run migrations to ensure schema is up to date
            active_dataset = dataset_manager.get_active_dataset()
            if active_dataset:
                dataset_path = dataset_manager.get_dataset_file_path(active_dataset.filename)
                MigrationManager(dataset_path).migrate_to_latest()
                logger.info(f"Database migrations applied for dataset: {active_dataset.title}")
            else:
                logger.warning("No active dataset found after initialization.")

            # Initialize event processor with current dataset
            if active_dataset:
                # Get the database URL instead of passing the engine
                current_engine = get_current_engine()
                database_url = str(current_engine.url)
                # Initialize Event Processor with Phase 3 optimizations
                app.state.event_processor = create_event_processor(
                    database_url=database_url
                )
                app.state.event_processor.start()
                logger.info(f"Event processor started for dataset: {active_dataset.title}")
            
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
            
            yield
        finally:
            if hasattr(app.state, 'event_processor') and app.state.event_processor:
                app.state.event_processor.stop()
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

    # Using unified structure_nodes API instead of separate layers/domains/terms
    app.include_router(structure_nodes.router, tags=["structure_nodes"])
    app.include_router(predicates.router, prefix="/api/predicates", tags=["predicates"])
    app.include_router(version_management.router, tags=["version_management"])
    app.include_router(graph.router, prefix="/api", tags=["graph"])
    app.include_router(datasets.router, prefix="/api", tags=["datasets"])
    app.include_router(schema.router, prefix="/api", tags=["schema"])
    app.include_router(config.router)
    app.include_router(schema_org_api.router)
    app.include_router(nlp_analysis.router, prefix="/api", tags=["nlp"])
    app.include_router(llm.router, prefix="/api", tags=["llm"])
    app.include_router(llm_traceability.router, tags=["llm-traceability"])
    app.include_router(pipeline_flavors.router, tags=["pipeline-flavors"])
    app.include_router(enrichment.router, prefix="", tags=["nlp-reference"])
    app.include_router(sync.router, tags=["sync"])
    
    # Phase 2: Administrative monitoring endpoints for service factory
    app.include_router(service_monitoring.router, tags=["service-monitoring"])
    
    # Phase 3: Collaboration workflow APIs
    app.include_router(changeset_management.router, tags=["changeset-management"])
    app.include_router(proposal_management.router, tags=["proposal-management"])
    app.include_router(identity_management.router, tags=["identity-management"])
    
    # Phase 3: Enhanced database management monitoring endpoints
    from api.admin import database_monitoring
    app.include_router(database_monitoring.router, tags=["database-monitoring"])
    
    # Enhanced Event Processor monitoring endpoints
    from api.admin import event_processor_monitoring
    app.include_router(event_processor_monitoring.router, tags=["event-processor-monitoring"])
    
    # Phase 4: Advanced collaborative features
    app.include_router(conflict_resolution.router, tags=["conflict-resolution"])
    app.include_router(analytics.router, tags=["analytics"])
    app.include_router(incremental_sync.router, tags=["incremental-sync"])
    
    # Phase 5: Enterprise-scale optimization features
    app.include_router(optimization.router, tags=["optimization"])
    return app

# Default app for production
dataset_manager = get_dataset_manager()
app = create_app()

# Add access logging middleware
app.add_middleware(AccessLogMiddleware)

# Get configuration for CORS
from config import get_settings
cors_settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    # Import configuration
    from config import get_settings
    
    # Get settings
    settings = get_settings()
    
    parser = argparse.ArgumentParser(description="Run the Context Studio FastAPI server.")
    parser.add_argument('--host', type=str, default=settings.server.host, help=f'Host IP to run the server on (default: {settings.server.host})')
    parser.add_argument('--port', type=int, default=settings.server.port, help=f'Port to run the server on (default: {settings.server.port})')
    args = parser.parse_args()
    
    try:
        logger.info(f"Starting server on http://{args.host}:{args.port} ...")
        
        uvicorn.run(
            "app:app",
            host=args.host,
            port=args.port,
            reload=settings.server.reload,
            access_log=settings.server.access_log,
            log_level=settings.server.log_level.value.lower()
        )
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting.")
