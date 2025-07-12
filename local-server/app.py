from fastapi import FastAPI
from contextlib import asynccontextmanager
from database.utils import init_db, get_db
from api import layers, domains, terms, term_relationships
from utils.logger import get_logger
import os
from utils.event_processor import EventProcessor

logger = get_logger(__name__)

# Dependency injection for testability
def create_app(engine=None, session_local=None, skip_vec=False):
    logger.info("Creating FastAPI application...")
    @asynccontextmanager
    async def lifespan(app):
        try:
            logger.info("Initializing database...")
            init_db(engine=engine, skip_vec=skip_vec)
            logger.info("Database initialized.")
            yield
        finally:
            logger.info("Shutting down application.")

    app = FastAPI(lifespan=lifespan)

    # --- FAISS Manager and Event Processor Initialization ---
    db_url = os.environ.get("SQLALCHEMY_DATABASE_URL")
    if not db_url:
        try:
            from config import settings as _settings
            db_url = getattr(_settings, "SQLALCHEMY_DATABASE_URL", None)
        except Exception:
            db_url = None
    if db_url and db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        # Load FAISS indexes at startup
        from utils.faiss_manager import FaissManager
        app.state.faiss_manager = FaissManager(db_path)
        app.state.faiss_manager.load_all_indexes()
        # Pass faiss_manager to EventProcessor
        app.state.event_processor = EventProcessor(db_path, faiss_manager=app.state.faiss_manager)
        app.state.event_processor.start()
    else:
        app.state.faiss_manager = None
        app.state.event_processor = None

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
    return app

# Default app for production
app = create_app()

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
