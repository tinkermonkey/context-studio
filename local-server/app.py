"""
Context Studio FastAPI application.

This module is the composition root for dependency injection. The lifespan
function creates all adapters and domain services, then stores them in
app.state for injection into route handlers via FastAPI Depends().

Architecture:
1. Lifespan setup: Create adapters and domain services
2. Register routes: Import and include routers
3. Route handling: Handlers receive services via Depends(get_service)
4. Lifespan shutdown: Clean up resources
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ConfigurationManager
from utils.logger import get_logger

# Import adapters
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.llm.provider_router import LLMProviderRouter
from adapters.events.in_process import InProcessEventPublisher

# Import domain services
from domain.ontology.services import OntologyService

# Import routes
from adapters.web.ontology_routes import router as ontology_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Startup:
    - Load configuration
    - Initialize database connections
    - Run migrations
    - Create adapter instances
    - Create domain services
    - Wire event subscriptions
    - Store services in app.state for dependency injection

    Shutdown:
    - Dispose of database connections
    - Clean up resources
    """
    logger.info("Starting Context Studio server")

    # Load configuration
    config_manager = ConfigurationManager()
    settings = config_manager.get_settings()
    logger.info(f"Configuration loaded from config.json")

    # Initialize database manager
    db_manager = DatabaseManager()
    local_db_url = f"sqlite:///{settings.database.local_db_path}"
    operations_db_url = f"sqlite:///{settings.database.operations_db_path}"

    db_manager.initialize(
        local_db_url=local_db_url,
        operations_db_url=operations_db_url,
    )
    logger.info("Database connections initialized")

    # Get local database session for creating repositories
    local_session = db_manager.get_local_session()

    try:
        # --- Driven Adapters (Infrastructure) ---

        # Persistence
        ontology_repo = SQLiteOntologyRepository(local_session)
        logger.info("OntologyRepository created")

        # Embedding service
        embedding_service = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")
        logger.info("EmbeddingService created")

        # LLM provider router
        llm_provider = LLMProviderRouter()
        logger.info("LLM provider router created")

        # Event publisher
        event_publisher = InProcessEventPublisher()
        logger.info("Event publisher created")

        # --- Domain Services ---

        ontology_service = OntologyService(
            repository=ontology_repo,
            embedding_service=embedding_service,
            event_publisher=event_publisher,
        )
        logger.info("OntologyService created and wired with adapters")

        # --- Store services in app.state for dependency injection ---

        app.state.ontology_service = ontology_service
        app.state.db_manager = db_manager

        logger.info("Services registered in app.state for dependency injection")

        yield

        logger.info("Shutting down Context Studio server")

    finally:
        # Cleanup
        local_session.close()
        db_manager.dispose()
        embedding_service.cleanup()
        logger.info("Cleanup completed")


app = FastAPI(lifespan=lifespan, title="Context Studio", version="1.0.0")

# Load settings for middleware configuration
config_manager = ConfigurationManager()
settings = config_manager.get_settings()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (these are the FastAPI APIRouter instances)
app.include_router(ontology_router)


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
    )
