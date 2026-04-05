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
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config_manager, get_settings
from utils.logger import get_logger

# Import adapters
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.pipeline_repo import SQLitePipelineRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.llm.provider_router import LLMProviderRouter
from adapters.events.in_process import InProcessEventPublisher
from adapters.events.change_recorder import ChangeEventRecorder
from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.wikidata import WikidataSource
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.cache import CachedReferenceSource

# Import domain services
from domain.ontology.services import OntologyService
from domain.graph.services import GraphAnalysisService
from domain.extraction.services import ExtractionService
from domain.extraction.ports import ReferenceSource
from domain.pipeline.services import PipelineService
from domain.versioning.services import VersioningService
from domain.ontology.events import GraphInvalidated
from domain.extraction.events import ExtractionCompleted
from domain.pipeline.events import PipelineExecuted
from domain.versioning.events import ChangesetMerged, SyncCompleted
from domain.versioning.ports import SyncTarget

# Import sync adapters
from adapters.sync.s3_sync import S3SyncAdapter
from adapters.sync.noop_sync import NoOpSyncTarget

# Import routes
from adapters.web.ontology_routes import router as ontology_router
from adapters.web.graph_routes import router as graph_router
from adapters.web.extraction_routes import router as extraction_router
from adapters.web.pipeline_routes import router as pipeline_router
from adapters.web.reference_routes import router as reference_router
from adapters.web.versioning_routes import router as versioning_router
from adapters.web.admin_routes import router as admin_router

# Import admin adapters and services
from adapters.config.json_store import JSONFileConfigStore
from adapters.metrics.system_collector import SystemMetricsCollector
from domain.admin.services import AdminService

logger = get_logger(__name__)


# ==================== Event Handlers ====================
# Note: Event handlers are created and wired during application startup in the lifespan
# function. See the "Wire event subscriptions" section below.


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

    # Capture application start time for uptime calculation
    app_start_time = datetime.now(timezone.utc)

    # Get configuration from global singleton
    config_manager = get_config_manager()
    settings = config_manager.get_settings()
    logger.info("Configuration loaded from config.json")

    # Initialize database manager
    db_manager = DatabaseManager()
    local_db_url = f"sqlite:///{settings.database.local_db_path}"
    operations_db_url = f"sqlite:///{settings.database.operations_db_path}"

    db_manager.initialize(
        local_db_url=local_db_url,
        operations_db_url=operations_db_url,
    )
    logger.info("Database connections initialized")

    try:
        # --- Driven Adapters (Infrastructure) ---

        # Persistence
        # Repositories receive session factories, not sessions.
        # Per-request sessions are created in route dependencies.
        local_session_factory = db_manager.get_local_session_factory()
        ontology_repo = SQLiteOntologyRepository(local_session_factory)
        extraction_repo = SQLiteExtractionRepository(local_session_factory)
        logger.info("OntologyRepository and ExtractionRepository created")

        operations_session_factory = db_manager.get_operations_session_factory()
        pipeline_repo = SQLitePipelineRepository(operations_session_factory)
        logger.info("PipelineRepository created")

        # Embedding service
        embedding_service = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")
        logger.info("EmbeddingService created")

        # LLM provider router
        llm_router = LLMProviderRouter(
            openai_api_key=settings.llm.openai_api_key,
            anthropic_api_key=settings.llm.anthropic_api_key,
        )
        logger.info("LLM provider router created")

        # NLP processor
        nlp_processor = SpacyNLPProcessor()
        logger.info("NLP processor created")

        # Reference sources (wrapped in cache)
        raw_sources: list[ReferenceSource] = [
            ConceptNetSource(),
            DBpediaSource(),
            WikidataSource(),
            SchemaOrgSource(),
        ]
        reference_sources: list[ReferenceSource] = [
            CachedReferenceSource(src, cache_db_path=settings.reference.cache_db_path)
            for src in raw_sources
        ]
        logger.info("Reference sources created and wrapped with caching")

        # Event publisher
        event_publisher = InProcessEventPublisher()
        logger.info("Event publisher created")

        # Change event recorder for audit trail
        change_repo = SQLiteChangeRepository(local_session_factory)
        change_recorder = ChangeEventRecorder(change_repo)
        logger.info("ChangeEventRecorder created")

        # --- Domain Services ---

        ontology_service = OntologyService(
            repository=ontology_repo,
            embedding_service=embedding_service,
            event_publisher=event_publisher,
        )
        logger.info("OntologyService created and wired with adapters")

        graph_engine = NetworkXGraphEngine()
        query_engine = RDFLibQueryEngine()
        graph_service = GraphAnalysisService(
            repository=ontology_repo,
            graph_engine=graph_engine,
            query_engine=query_engine,
        )
        logger.info("GraphAnalysisService created and wired with adapters")

        extraction_service = ExtractionService(
            ontology_repo=ontology_repo,
            embedding_service=embedding_service,
            llm=llm_router,
            nlp=nlp_processor,
            reference_sources=reference_sources,
            event_publisher=event_publisher,
            extraction_repo=extraction_repo,
        )
        logger.info("ExtractionService created and wired with adapters")

        pipeline_service = PipelineService(
            pipeline_repo=pipeline_repo,
            llm=llm_router,
            event_publisher=event_publisher,
        )
        logger.info("PipelineService created and wired with adapters")

        # Versioning service with sync adapter
        sync_config = settings.sync if hasattr(settings, "sync") else None
        sync_target: SyncTarget
        if sync_config and sync_config.s3_bucket:
            try:
                sync_target = S3SyncAdapter(
                    bucket=sync_config.s3_bucket,
                    prefix=sync_config.s3_prefix or "context-studio",
                    aws_access_key=sync_config.s3_access_key or "",
                    aws_secret_key=sync_config.s3_secret_key or "",
                    region=sync_config.s3_region or "us-east-1",
                )
                logger.info("S3SyncAdapter initialized for remote sync")
            except Exception as e:
                logger.warning(f"Failed to initialize S3SyncAdapter, falling back to no-op: {e}")
                sync_target = NoOpSyncTarget()
        else:
            sync_target = NoOpSyncTarget()
            logger.info("S3 not configured, using no-op sync target")

        versioning_service = VersioningService(
            change_repo=change_repo,
            sync_target=sync_target,
            event_publisher=event_publisher,
        )
        logger.info("VersioningService created and wired with repository, sync adapter, and event publisher")

        # --- System Administration Service ---

        config_store = JSONFileConfigStore(config_manager)
        logger.info("JSONFileConfigStore created")

        metrics_collector = SystemMetricsCollector(
            llm_router=llm_router,
            nlp_processor=nlp_processor,
            embedding_service=embedding_service,
            start_time=app_start_time,
            db_engine=db_manager.get_local_engine(),
        )
        logger.info("SystemMetricsCollector created")

        admin_service = AdminService(
            metrics_collector=metrics_collector,
            config_store=config_store,
        )
        logger.info("AdminService created and wired with metrics and config store")

        # --- Wire event subscriptions ---

        event_publisher.subscribe(GraphInvalidated, graph_service.on_graph_invalidated)
        logger.info("Event subscription: GraphInvalidated -> GraphAnalysisService.on_graph_invalidated")

        event_publisher.subscribe(ExtractionCompleted, change_recorder.on_extraction_completed)
        logger.info("Event subscription: ExtractionCompleted -> ChangeEventRecorder.on_extraction_completed")

        event_publisher.subscribe(PipelineExecuted, change_recorder.on_pipeline_executed)
        logger.info("Event subscription: PipelineExecuted -> ChangeEventRecorder.on_pipeline_executed")

        event_publisher.subscribe(ChangesetMerged, versioning_service.on_changeset_merged)
        logger.info("Event subscription: ChangesetMerged -> VersioningService.on_changeset_merged")

        event_publisher.subscribe(SyncCompleted, versioning_service.on_sync_completed)
        logger.info("Event subscription: SyncCompleted -> VersioningService.on_sync_completed")

        # --- Store services in app.state for dependency injection ---

        app.state.ontology_service = ontology_service
        app.state.graph_service = graph_service
        app.state.extraction_service = extraction_service
        app.state.pipeline_service = pipeline_service
        app.state.versioning_service = versioning_service
        app.state.admin_service = admin_service
        app.state.db_manager = db_manager
        app.state.reference_sources = reference_sources

        # Store adapters needed for health checks
        app.state.nlp_processor = nlp_processor
        app.state.llm_router = llm_router

        logger.info("Services registered in app.state for dependency injection")

        yield

        logger.info("Shutting down Context Studio server")

    finally:
        # Cleanup
        db_manager.dispose()
        embedding_service.cleanup()
        logger.info("Cleanup completed")


app = FastAPI(lifespan=lifespan, title="Context Studio", version="1.0.0")

# Get settings for middleware configuration from global singleton
settings = get_settings()

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
app.include_router(graph_router)
app.include_router(extraction_router)
app.include_router(pipeline_router)
app.include_router(reference_router)
app.include_router(versioning_router)
app.include_router(admin_router)


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
    )
