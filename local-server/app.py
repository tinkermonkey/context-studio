import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database.utils import init_db, get_db, get_dataset_manager, get_current_engine
from api import layers, domains, terms, term_relationships, graph, datasets, schema
from utils.logger import get_logger
from utils.event_processor import EventProcessor

logger = get_logger(__name__)

# Dependency injection for testability
def create_app(dataset_id=None, engine=None, session_local=None, skip_vec=False):
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
            init_db(engine=engine or get_current_engine(), skip_vec=skip_vec)
            logger.info("Database initialized.")
            
            # Initialize event processor with current dataset
            active_dataset = dataset_manager.get_active_dataset()
            if active_dataset:
                dataset_path = dataset_manager.get_dataset_file_path(active_dataset.filename)
                app.state.event_processor = EventProcessor(dataset_path)
                app.state.event_processor.start()
                logger.info(f"Event processor started for dataset: {active_dataset.title}")
            
            yield
        finally:
            if hasattr(app.state, 'event_processor') and app.state.event_processor:
                app.state.event_processor.stop()
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
    app.include_router(term_relationships.router, prefix="/api/term-relationships", tags=["term-relationships"])
    app.include_router(graph.router, prefix="/api", tags=["graph"])
    app.include_router(datasets.router, prefix="/api", tags=["datasets"])
    app.include_router(schema.router, prefix="/api", tags=["schema"])
    return app

# Default app for production
dataset_manager = get_dataset_manager()
app = create_app()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, be more specific
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser(description="Run the Context Studio FastAPI server.")
    parser.add_argument('--host', type=str, default="127.0.0.1", help='Host IP to run the server on (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on (default: 8000)')
    args = parser.parse_args()
    try:
        logger.info(f"Starting server on http://{args.host}:{args.port} ...")
        uvicorn.run("app:app", host=args.host, port=args.port, reload=True)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting.")
