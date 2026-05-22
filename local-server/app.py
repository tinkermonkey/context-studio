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

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import admin adapters and services
from adapters.config.json_store import JSONFileConfigStore
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.llm.provider_router import LLMProviderRouter
from adapters.metrics.system_collector import SystemMetricsCollector
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository

# Import adapters
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.dataset_repo import SQLiteDatasetRepository
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import (
    SQLiteExtractionRunRepository,
)
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_repo import SQLitePipelineRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.reference.cache import CachedReferenceSource
from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from adapters.sync.duckdb_sync import DuckDBSyncAdapter
from adapters.sync.noop_sync import NoOpSyncTarget

# Import sync adapters
from adapters.sync.s3_sync import S3SyncAdapter
from adapters.telemetry import setup_telemetry
from adapters.telemetry.log_bridge import OTLPLogHandler
from adapters.web.admin_routes import router as admin_router
from adapters.web.extraction_routes import router as extraction_router
from adapters.web.graph_routes import router as graph_router
from adapters.web.interchange_routes import router as interchange_router

# Import routes
from adapters.web.ontology_routes import router as ontology_router
from adapters.web.pipeline_routes import router as pipeline_router
from adapters.web.pipelines_routes import router as pipelines_router
from adapters.web.reference_routes import router as reference_router
from adapters.web.versioning_routes import router as versioning_router
from config import SyncAdapterType, get_config_manager, get_settings
from domain.admin.exceptions import ConfigurationError
from domain.admin.services import AdminService
from domain.extraction.events import ExtractionCompleted
from domain.extraction.ports import ReferenceSource
from domain.extraction.services import ExtractionService
from domain.graph.services import GraphAnalysisService
from domain.interchange.services import ImportRunService
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
    PipelineTypeRegistry,
)
from domain.ontology.events import (
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    ConceptSchemeUpdated,
    GraphInvalidated,
    IndividualCreated,
    IndividualDeleted,
    IndividualUpdated,
    PropertyDefinitionCreated,
    PropertyDefinitionDeleted,
    PropertyDefinitionUpdated,
    RelationshipCreated,
    RelationshipDeleted,
    SchemeCreated,
    SchemeDeleted,
    SchemeUpdated,
    TaxonomyCreated,
    TaxonomyDeleted,
    TaxonomyUpdated,
)

# Import domain services
from domain.ontology.services import OntologyService
from domain.pipeline.events import PipelineExecuted
from domain.pipeline.services import PipelineService
from domain.versioning.events import ChangesetMerged, SyncCompleted
from domain.versioning.ports import SyncTarget
from domain.versioning.services import VersioningService
from utils.logger import get_logger, register_otlp_handler

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

    # Capture application start time for uptime calculation (as Unix timestamp)
    app_start_time = datetime.now(timezone.utc).timestamp()

    # Get configuration from global singleton
    config_manager = get_config_manager()
    settings = config_manager.get_settings()
    logger.info("Configuration loaded from config.json")

    # Initialize telemetry FIRST (before other adapters)
    telemetry = setup_telemetry(settings.telemetry)

    # Register OTLP log handler if telemetry is enabled and log export is configured
    logger_provider = telemetry.get_logger_provider()
    if logger_provider:
        otlp_log_handler = OTLPLogHandler(logger_provider)
        otlp_log_handler.setLevel(logging.DEBUG)
        register_otlp_handler(otlp_log_handler)
        logger.info("OTLP log handler registered")

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
        extraction_run_repo = SQLiteExtractionRunRepository(local_session_factory)
        interchange_repo = SQLiteInterchangeRepository(local_session_factory)
        logger.info(
            "OntologyRepository, ExtractionRepository, ExtractionRunRepository, and"
            " InterchangeRepository created"
        )

        operations_session_factory = db_manager.get_operations_session_factory()
        pipeline_repo = SQLitePipelineRepository(operations_session_factory)
        pipeline_run_repo = PipelineRepository(local_session_factory)
        logger.info("PipelineRepository and PipelineRunRepository created")

        # Initialize pipeline registries (currently empty—implementations/configs added at startup)
        implementation_registry = PipelineImplementationRegistry()
        config_registry = PipelineConfigurationRegistry()
        type_registry = PipelineTypeRegistry()
        logger.info("Pipeline registries initialized")

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
            ConceptNetSource(
                base_url=settings.reference.conceptnet_base_url,
                timeout=settings.reference.conceptnet_timeout,
            ),
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
            extraction_run_repo=extraction_run_repo,
        )
        logger.info("ExtractionService created and wired with adapters")

        pipeline_service = PipelineService(
            pipeline_repo=pipeline_repo,
            flavor_repo=pipeline_repo,
            llm=llm_router,
            event_publisher=event_publisher,
        )
        logger.info("PipelineService created and wired with adapters")

        # Versioning service with sync adapter
        sync_config = settings.sync
        sync_target: SyncTarget

        if sync_config:
            adapter_type = sync_config.adapter

            if adapter_type == SyncAdapterType.S3:
                s3_config = sync_config.s3
                if not s3_config or not s3_config.s3_bucket:
                    raise ConfigurationError(
                        "S3 adapter configured but required settings missing: "
                        "sync.s3.s3_bucket is required when adapter is 's3'"
                    )
                try:
                    sync_target = S3SyncAdapter(
                        bucket=s3_config.s3_bucket,
                        prefix=s3_config.s3_prefix or "context-studio",
                        aws_access_key=s3_config.s3_access_key or "",
                        aws_secret_key=s3_config.s3_secret_key or "",
                        region=s3_config.s3_region or "us-east-1",
                        change_repo=change_repo,
                    )
                    logger.info("S3SyncAdapter initialized for remote sync")
                except ConfigurationError:
                    raise
                except Exception as e:
                    raise ConfigurationError(
                        f"Failed to initialize S3SyncAdapter: {type(e).__name__}: {e}"
                    ) from e

            elif adapter_type == SyncAdapterType.DUCKDB:
                duckdb_config = sync_config.duckdb
                if not duckdb_config:
                    raise ConfigurationError(
                        "DuckDB adapter configured but required settings missing: "
                        "sync.duckdb configuration is required when adapter is 'duckdb'"
                    )
                try:
                    sync_target = DuckDBSyncAdapter(
                        output_dir=duckdb_config.output_dir,
                        change_repo=change_repo,
                    )
                    logger.info("DuckDBSyncAdapter initialized for remote sync")
                except ConfigurationError:
                    raise
                except Exception as e:
                    raise ConfigurationError(
                        "Failed to initialize DuckDBSyncAdapter:" f" {type(e).__name__}: {e}"
                    ) from e

            elif adapter_type == SyncAdapterType.NONE:
                sync_target = NoOpSyncTarget()
                logger.info("Sync adapter set to 'none', using no-op sync target")
            else:
                # This should never happen due to enum validation, but kept as defense-in-depth
                raise ConfigurationError(
                    f"Invalid sync adapter type: '{adapter_type}'. "
                    f"Must be one of: {', '.join(t.value for t in SyncAdapterType)}"
                )
        else:
            sync_target = NoOpSyncTarget()
            logger.info("Sync configuration not provided, using no-op sync target")

        versioning_service = VersioningService(
            change_repo=change_repo,
            sync_target=sync_target,
            event_publisher=event_publisher,
        )
        logger.info(
            "VersioningService created and wired with repository, sync adapter, and"
            " event publisher"
        )

        # Interchange service for import run tracking
        import_run_service = ImportRunService()
        logger.info("ImportRunService created")

        # --- System Administration Service ---

        config_store = JSONFileConfigStore(config_manager)
        logger.info("JSONFileConfigStore created")

        metrics_collector = SystemMetricsCollector(
            llm=llm_router,
            nlp=nlp_processor,
            embedding=embedding_service,
            db_engine=db_manager.get_local_engine(),
            start_time=app_start_time,
        )
        logger.info("SystemMetricsCollector created")

        dataset_repo = SQLiteDatasetRepository(local_session_factory)
        logger.info("SQLiteDatasetRepository created")

        admin_service = AdminService(
            metrics_collector=metrics_collector,
            config_store=config_store,
            dataset_repository=dataset_repo,
        )
        logger.info(
            "AdminService created and wired with metrics, config store, and dataset" " repository"
        )

        # --- Wire event subscriptions ---

        event_publisher.subscribe(GraphInvalidated, graph_service.on_graph_invalidated)
        logger.info(
            "Event subscription: GraphInvalidated ->" " GraphAnalysisService.on_graph_invalidated"
        )

        event_publisher.subscribe(ExtractionCompleted, change_recorder.on_extraction_completed)
        logger.info(
            "Event subscription: ExtractionCompleted ->"
            " ChangeEventRecorder.on_extraction_completed"
        )

        event_publisher.subscribe(PipelineExecuted, change_recorder.on_pipeline_executed)
        logger.info(
            "Event subscription: PipelineExecuted ->" " ChangeEventRecorder.on_pipeline_executed"
        )

        event_publisher.subscribe(ChangesetMerged, versioning_service.on_changeset_merged)
        logger.info(
            "Event subscription: ChangesetMerged ->" " VersioningService.on_changeset_merged"
        )

        event_publisher.subscribe(SyncCompleted, versioning_service.on_sync_completed)
        logger.info("Event subscription: SyncCompleted -> VersioningService.on_sync_completed")

        # --- Ontology change event subscriptions ---

        event_publisher.subscribe(TaxonomyCreated, change_recorder.on_taxonomy_created)
        logger.info(
            "Event subscription: TaxonomyCreated ->" " ChangeEventRecorder.on_taxonomy_created"
        )

        event_publisher.subscribe(SchemeCreated, change_recorder.on_scheme_created)
        logger.info("Event subscription: SchemeCreated -> ChangeEventRecorder.on_scheme_created")

        event_publisher.subscribe(ClassCreated, change_recorder.on_class_created)
        logger.info("Event subscription: ClassCreated -> ChangeEventRecorder.on_class_created")

        event_publisher.subscribe(ClassUpdated, change_recorder.on_class_updated)
        logger.info("Event subscription: ClassUpdated -> ChangeEventRecorder.on_class_updated")

        event_publisher.subscribe(ClassDeleted, change_recorder.on_class_deleted)
        logger.info("Event subscription: ClassDeleted -> ChangeEventRecorder.on_class_deleted")

        event_publisher.subscribe(ClassMoved, change_recorder.on_class_moved)
        logger.info("Event subscription: ClassMoved -> ChangeEventRecorder.on_class_moved")

        event_publisher.subscribe(RelationshipCreated, change_recorder.on_relationship_created)
        logger.info(
            "Event subscription: RelationshipCreated ->"
            " ChangeEventRecorder.on_relationship_created"
        )

        event_publisher.subscribe(RelationshipDeleted, change_recorder.on_relationship_deleted)
        logger.info(
            "Event subscription: RelationshipDeleted ->"
            " ChangeEventRecorder.on_relationship_deleted"
        )

        event_publisher.subscribe(
            PropertyDefinitionCreated, change_recorder.on_property_definition_created
        )
        logger.info(
            "Event subscription: PropertyDefinitionCreated ->"
            " ChangeEventRecorder.on_property_definition_created"
        )

        event_publisher.subscribe(
            PropertyDefinitionUpdated, change_recorder.on_property_definition_updated
        )
        logger.info(
            "Event subscription: PropertyDefinitionUpdated ->"
            " ChangeEventRecorder.on_property_definition_updated"
        )

        event_publisher.subscribe(
            PropertyDefinitionDeleted, change_recorder.on_property_definition_deleted
        )
        logger.info(
            "Event subscription: PropertyDefinitionDeleted ->"
            " ChangeEventRecorder.on_property_definition_deleted"
        )

        event_publisher.subscribe(TaxonomyUpdated, change_recorder.on_taxonomy_updated)
        logger.info(
            "Event subscription: TaxonomyUpdated ->" " ChangeEventRecorder.on_taxonomy_updated"
        )

        event_publisher.subscribe(TaxonomyDeleted, change_recorder.on_taxonomy_deleted)
        logger.info(
            "Event subscription: TaxonomyDeleted ->" " ChangeEventRecorder.on_taxonomy_deleted"
        )

        event_publisher.subscribe(SchemeUpdated, change_recorder.on_scheme_updated)
        logger.info("Event subscription: SchemeUpdated -> ChangeEventRecorder.on_scheme_updated")

        event_publisher.subscribe(SchemeDeleted, change_recorder.on_scheme_deleted)
        logger.info("Event subscription: SchemeDeleted -> ChangeEventRecorder.on_scheme_deleted")

        event_publisher.subscribe(ConceptSchemeUpdated, change_recorder.on_concept_scheme_updated)
        logger.info(
            "Event subscription: ConceptSchemeUpdated ->"
            " ChangeEventRecorder.on_concept_scheme_updated"
        )

        event_publisher.subscribe(IndividualCreated, change_recorder.on_individual_created)
        logger.info(
            "Event subscription: IndividualCreated ->" " ChangeEventRecorder.on_individual_created"
        )

        event_publisher.subscribe(IndividualUpdated, change_recorder.on_individual_updated)
        logger.info(
            "Event subscription: IndividualUpdated ->" " ChangeEventRecorder.on_individual_updated"
        )

        event_publisher.subscribe(IndividualDeleted, change_recorder.on_individual_deleted)
        logger.info(
            "Event subscription: IndividualDeleted ->" " ChangeEventRecorder.on_individual_deleted"
        )

        # --- Store services in app.state for dependency injection ---

        app.state.ontology_service = ontology_service
        app.state.graph_service = graph_service
        app.state.extraction_service = extraction_service
        app.state.pipeline_service = pipeline_service
        app.state.versioning_service = versioning_service
        app.state.admin_service = admin_service
        app.state.db_manager = db_manager
        app.state.reference_sources = reference_sources
        app.state.ontology_repo = ontology_repo
        app.state.interchange_repo = interchange_repo
        app.state.import_run_service = import_run_service

        # Store pipeline run repo and registries for generic pipeline endpoints
        app.state.pipeline_run_repo = pipeline_run_repo
        app.state.implementation_registry = implementation_registry
        app.state.config_registry = config_registry
        app.state.type_registry = type_registry

        # Store adapters needed for health checks
        app.state.nlp_processor = nlp_processor
        app.state.llm_router = llm_router

        logger.info("Services registered in app.state for dependency injection")

        # Instrument app after FastAPI and database are initialized
        telemetry.instrument_app(app, db_engine=db_manager.get_local_engine())

        yield

        logger.info("Shutting down Context Studio server")

    finally:
        # Cleanup resources independently to ensure all cleanup operations complete
        # even if one raises an exception
        try:
            db_manager.dispose()
        except Exception as e:
            logger.error(f"Error disposing database manager: {e}")

        try:
            embedding_service.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up embedding service: {e}")

        try:
            telemetry.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down telemetry: {e}")

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
app.include_router(pipelines_router)
app.include_router(reference_router)
app.include_router(versioning_router)
app.include_router(admin_router)
app.include_router(interchange_router)


# ==================== Exception Handlers ====================
# Note: Pydantic validation errors are handled by FastAPI and return
# 422 (UNPROCESSABLE_ENTITY) by default.
# No custom handler is needed here.


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
    )
