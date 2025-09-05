import uvicorn
import argparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from api import layers, domains, terms, term_relationships, graph, datasets, nlp_analysis, schema, predicates, llm, pipeline_flavors
from api import enrichment, config, nodes
from schema_org import api as schema_org_api
from api.graph import get_cached_graph_service, invalidate_graph_cache
from database.migrations.migration_manager import MigrationManager
from database.utils import init_db, get_db, get_dataset_manager, get_current_engine, cleanup_database_resources
from pipeline.manager import get_pipeline_database_manager
from nlp.pipeline import get_pipeline
from utils.access_log_middleware import AccessLogMiddleware
from utils.event_processor import EventProcessor
from utils.logger import get_logger

logger = get_logger(__name__)

# Dependency injection for testability
def create_app(dataset_id=None, engine=None, session_local=None):
    logger.info("Creating FastAPI application...")
    
    @asynccontextmanager
    async def lifespan(app):
        try:
            logger.info("Initializing dataset management...")
            
            # Initialize dataset manager
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
            
            # Migrate existing pipeline flavors from current dataset to pipeline database
            # This is a one-time migration for existing installations
            active_dataset = dataset_manager.get_active_dataset()
            if active_dataset:
                try:
                    # Get current dataset session for migration
                    from database.utils import get_current_session_local
                    current_session_local = get_current_session_local()
                    if current_session_local:
                        # Check if there are flavors in the dataset database to migrate
                        with current_session_local() as db:
                            try:
                                existing_flavors = db.execute(text("""
                                    SELECT COUNT(*) FROM pipeline_flavors
                                """)).fetchone()
                                if existing_flavors and existing_flavors[0] > 0:
                                    logger.info(f"Found {existing_flavors[0]} pipeline flavors to migrate")
                                    migrated = pipeline_db_manager.migrate_from_dataset_database(current_session_local)
                                    logger.info(f"Successfully migrated {migrated} pipeline flavors to pipeline database")
                            except Exception as e:
                                # Table might not exist or already migrated - this is fine
                                logger.debug(f"No pipeline flavors to migrate (pipeline flavors managed separately): {e}")
                except Exception as e:
                    logger.warning(f"Pipeline flavor migration check failed: {e}")
            
            # Run migrations to ensure schema is up to date
            active_dataset = dataset_manager.get_active_dataset()
            if active_dataset:
                dataset_path = dataset_manager.get_dataset_file_path(active_dataset.filename)
                MigrationManager(dataset_path).migrate_to_latest()
                logger.info(f"Database migrations applied for dataset: {active_dataset.title}")
            else:
                logger.warning("No active dataset found after initialization.")

            # Initialize event processor with current dataset
            active_dataset = dataset_manager.get_active_dataset()
            if active_dataset:
                dataset_path = dataset_manager.get_dataset_file_path(active_dataset.filename)
                app.state.event_processor = EventProcessor(dataset_path)
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
            logger.info("Preloading GraphService...")
            try:
                graph_service = get_cached_graph_service()
                logger.info("GraphService successfully preloaded")
            except Exception as e:
                logger.error(f"Error preloading GraphService: {e}")
            
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

    app.include_router(layers.router, prefix="/api/layers", tags=["layers"])
    app.include_router(domains.router, prefix="/api/domains", tags=["domains"])
    app.include_router(terms.router, prefix="/api/terms", tags=["terms"])
    # Unified nodes API (Great Normalization)
    app.include_router(nodes.router, tags=["nodes"])
    app.include_router(term_relationships.router, prefix="/api/term-relationships", tags=["term-relationships"])
    app.include_router(predicates.router, prefix="/api/predicates", tags=["predicates"])
    app.include_router(graph.router, prefix="/api", tags=["graph"])
    app.include_router(datasets.router, prefix="/api", tags=["datasets"])
    app.include_router(schema.router, prefix="/api", tags=["schema"])
    # Configuration management API
    app.include_router(config.router)
    # Schema.org API (separate router with its own prefix)
    app.include_router(schema_org_api.router)
    # Integrate NLP router
    app.include_router(nlp_analysis.router, prefix="/api", tags=["nlp"])
    # LLM router
    app.include_router(llm.router, prefix="/api", tags=["llm"])
    # Pipeline flavors router
    app.include_router(pipeline_flavors.router, tags=["pipeline-flavors"])
    # NLP enrichment reference API
    app.include_router(enrichment.router, prefix="", tags=["nlp-reference"])
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
