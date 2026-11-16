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
from collections.abc import Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import uvicorn
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from adapters.chat.claim_tools import build_claim_tools
from adapters.chat.context import ConfigChatSettings, OntologyWorkspaceContext
from adapters.chat.interchange_tools import build_interchange_tools
from adapters.chat.proposal_tools import (
    DrSpecDriftTool,
    MarkProposalLandedTool,
    build_proposal_tools,
)
from adapters.chat.run_tools import build_run_tools
from adapters.chat.source_tools import build_source_tools
from adapters.chat.tools import ToolBase, build_chat_tools
from adapters.clustering.sklearn_clusterer import SklearnClusterer

# Import admin adapters and services
from adapters.config.json_store import JSONFileConfigStore
from adapters.decision.registry import build_decision_models
from adapters.demo import CanonDemoDatasetLoader
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.interchange.dr_drift import DrDriftPlanner
from adapters.interchange.dr_predicates import DrPredicateRules
from adapters.interchange.dr_relationships import DrRelationshipRules
from adapters.llm.provider_router import LLMProviderRouter
from adapters.mcp.server import McpEndpoint, is_loopback_host, start_mcp_server
from adapters.metrics.system_collector import SystemMetricsCollector
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.persistence.sqlite.approval_policy_repo import SQLiteApprovalPolicyRepository
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.chat_repo import SqliteConversationRepository
from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository

# Import adapters
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import (
    SQLiteExtractionRunRepository,
)
from adapters.persistence.sqlite.individual_vector_index import (
    SqliteIndividualVectorIndex,
)
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.persistence.sqlite.models import OntologyEntity
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_config_repo import (
    PipelineConfigurationRepository as PipelineConfigRepo,
)
from adapters.persistence.sqlite.pipeline_config_repo import (
    load_user_configurations,
)
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.persistence.sqlite.entity_source_repo import SQLiteEntitySourceRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from adapters.persistence.sqlite.source_repo import SQLiteSourceRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from adapters.pipelines.run_executor import BackgroundRunExecutor
from adapters.recognition.individual_recognizer import CascadeIndividualRecognizer
from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.grounding import GroundingAdapter
from adapters.reference.proxy import ReferenceProxy
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from adapters.sources.fetcher import HttpPageFetcher
from adapters.sources.file_store import LocalSourceFileStore
from adapters.sources.readers import source_readers
from adapters.sync.duckdb_sync import DuckDBSyncAdapter
from adapters.sync.noop_sync import NoOpSyncTarget

# Import sync adapters
from adapters.sync.s3_sync import S3SyncAdapter
from adapters.telemetry import setup_telemetry
from adapters.telemetry.log_bridge import OTLPLogHandler
from adapters.web.admin_routes import router as admin_router
from adapters.web.bundle_routes import router as bundle_router
from adapters.web.chat_routes import router as chat_router
from adapters.web.claims_routes import router as claims_router
from adapters.web.decision_routes import router as decision_router
from adapters.web.drift_routes import router as drift_router
from adapters.web.extraction_examples import load_extraction_examples
from adapters.web.extraction_routes import router as extraction_router
from adapters.web.graph_routes import router as graph_router
from adapters.web.interchange_routes import router as interchange_router

# Import routes
from adapters.web.ontology_routes import router as ontology_router
from adapters.web.pipelines_routes import config_router as pipeline_config_router
from adapters.web.pipelines_routes import router as pipelines_router
from adapters.web.proposals_routes import router as proposals_router
from adapters.web.reference_routes import router as reference_router
from adapters.web.request_guard import add_browser_guards
from adapters.web.sources_routes import router as sources_router
from adapters.web.versioning_routes import router as versioning_router
from config import SyncAdapterType, get_config_manager, get_settings
from domain.admin.demo_dataset_service import LoadDemoDataset
from domain.admin.exceptions import ConfigurationError
from domain.admin.services import AdminService
from domain.chat.services import ChatService
from domain.extraction.events import ExtractionCompleted
from domain.extraction.ports import ReferenceSource
from domain.extraction.services import ExtractionService
from domain.extraction.sources import SourceService
from domain.graph.services import GraphAnalysisService
from domain.interchange.bundle import BundleExporter
from domain.interchange.services import ImportRunService
from domain.ontology.events import (
    AttributeDefinitionCreated,
    AttributeDefinitionDeleted,
    AttributeDefinitionUpdated,
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    GraphInvalidated,
    IndividualCreated,
    IndividualDeleted,
    IndividualUpdated,
    PredicateCreated,
    PredicateDeleted,
    PredicateUpdated,
    PropertyDefinitionCreated,
    PropertyDefinitionDeleted,
    PropertyDefinitionUpdated,
    RelationshipCreated,
    RelationshipDeleted,
    RelationshipUpdated,
    SchemeCreated,
    SchemeDeleted,
    SchemeUpdated,
    TaxonomyCreated,
    TaxonomyDeleted,
    TaxonomyUpdated,
)

# Import domain services
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.pipelines.bootstrap import register_pipelines
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
    PipelineTypeRegistry,
)
from domain.pipelines.requested_via import RequestedVia
from domain.pipelines.schema_extraction.apply_service import (
    SchemaExtractionApplyService,
)
from domain.pipelines.schema_extraction.recognition_preview import (
    SchemaRecognitionPreviewService,
)
from domain.pipelines.source_extraction import SourceExtractionService
from domain.pipelines.schema_node_connection_refinement.apply_service import (
    SchemaConnectionRefinementApplyService,
)
from domain.pipelines.schema_node_definition_refinement.apply_service import (
    SchemaDefinitionRefinementApplyService,
)
from domain.pipelines.schema_node_grounding.apply_service import (
    SchemaGroundingApplyService,
)
from domain.pipelines.schema_node_grounding.scoring import GroundingScorer
from domain.versioning.approval_policy import ApprovalPolicyService
from domain.versioning.bundle_import import BundleImportService
from domain.versioning.claims import ClaimService
from domain.versioning.drift import DriftImportService
from domain.versioning.events import SyncCompleted
from domain.versioning.ports import SyncTarget
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import ProposalSource
from domain.versioning.services import VersioningService
from utils.logger import get_logger, register_otlp_handler

logger = get_logger(__name__)
# Domain code logs through std logging (it can't import utils.logger); attach the
# log file handler to the "domain" package logger so those records reach it too.
get_logger("domain")


# MCP endpoint at /mcp: mounted below, given its session manager in the lifespan.
mcp_endpoint = McpEndpoint()


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

    # Caching, rate-limiting proxy for reference API calls (started with the sources below)
    reference_proxy = ReferenceProxy(settings.reference.proxy)

    try:
        # --- Driven Adapters (Infrastructure) ---

        # Persistence
        # Repositories receive session factories, not sessions.
        # Per-request sessions are created in route dependencies.
        local_session_factory = db_manager.get_local_session_factory()
        # The ontology and change repositories share sessions inside a
        # transaction scope, so a revert commits as one unit.
        shared_session_factory = SharedSessionFactory(local_session_factory)
        ontology_repo: OntologyRepository = cast(
            OntologyRepository, SQLiteOntologyRepository(shared_session_factory)
        )
        extraction_repo = SQLiteExtractionRepository(local_session_factory)
        extraction_run_repo = SQLiteExtractionRunRepository(local_session_factory)
        interchange_repo = SQLiteInterchangeRepository(local_session_factory)
        logger.info(
            "OntologyRepository, ExtractionRepository, ExtractionRunRepository, and"
            " InterchangeRepository created"
        )

        operations_session_factory = db_manager.get_operations_session_factory()
        pipeline_run_repo = PipelineRepository(local_session_factory)
        batch_repo = BatchRepository(local_session_factory)
        pipeline_config_repo = PipelineConfigRepo(operations_session_factory)
        logger.info("PipelineRunRepository, BatchRepository, and PipelineConfigRepo created")

        # Initialize pipeline registries (currently empty—implementations/configs added at startup)
        implementation_registry = PipelineImplementationRegistry()
        config_registry = PipelineConfigurationRegistry()
        type_registry = PipelineTypeRegistry()
        logger.info("Pipeline registries initialized")

        # Embedding service
        embedding_service = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")
        logger.info("EmbeddingService created")

        # Clustering adapter (open-extraction schema distillation)
        clusterer = SklearnClusterer()
        logger.info("SklearnClusterer created")

        # LLM provider router
        llm_router = LLMProviderRouter(
            openai_api_key=settings.llm.openai_api_key,
            anthropic_api_key=settings.llm.anthropic_api_key,
            openrouter_api_key=settings.llm.openrouter_api_key,
        )
        logger.info("LLM provider router created")

        # Decision models: the named instances in config.json's decision_models
        app.state.decision_models = build_decision_models(settings.decision_models, llm_router)

        # NLP processor
        nlp_processor = SpacyNLPProcessor()
        logger.info("NLP processor created")

        # Reference sources: every API call goes through the reference proxy, which
        # caches and rate limits it; schema.org is local and makes no calls.
        reference_proxy.start()
        conceptnet_source = ConceptNetSource(
            base_url=reference_proxy.base_url("conceptnet"),
            upstream_url=reference_proxy.upstream_url("conceptnet"),
            timeout=settings.reference.conceptnet_timeout,
        )
        dbpedia_source = DBpediaSource(
            base_url=reference_proxy.base_url("dbpedia"),
            upstream_url=reference_proxy.upstream_url("dbpedia"),
        )
        wikidata_source = WikidataSource(
            base_url=reference_proxy.base_url("wikidata"),
            upstream_url=reference_proxy.upstream_url("wikidata"),
        )
        schema_org_source = SchemaOrgSource()
        reference_sources: list[ReferenceSource] = [
            conceptnet_source,
            dbpedia_source,
            wikidata_source,
            schema_org_source,
        ]
        logger.info("Reference sources created")

        # Event publisher
        event_publisher = InProcessEventPublisher()
        logger.info("Event publisher created")

        # Change event recorder for audit trail
        change_repo = SQLiteChangeRepository(shared_session_factory)
        change_recorder = ChangeEventRecorder(change_repo)
        logger.info("ChangeEventRecorder created")

        # --- Domain Services ---

        # The indexes write embeddings onto ontology_entities rows, so they share
        # the ontology repository's sessions: inside a transaction scope (a
        # proposal apply, a revert) the index write joins the scope instead of
        # waiting on its write lock until busy_timeout, and rolls back with it.
        schema_vector_index = SqliteSchemaVectorIndex(shared_session_factory, embedding_service)
        logger.info("SchemaVectorIndex created")

        individual_vector_index = SqliteIndividualVectorIndex(
            shared_session_factory, embedding_service
        )
        app.state.individual_vector_index = individual_vector_index
        logger.info("IndividualVectorIndex created")

        # One-time recognition backfill (#1142): individual embeddings persist on
        # the entity row, so this fires only when unindexed individuals exist —
        # pre-feature rows on the first boot after this ships, then never again.
        # Skipped entirely on a fresh/empty database.
        with local_session_factory() as session:
            unindexed_individuals = (
                session.query(OntologyEntity)
                .filter(
                    OntologyEntity.node_type == "individual",
                    OntologyEntity.is_indexed.is_(False),
                )
                .count()
            )
        if unindexed_individuals:
            indexed = individual_vector_index.reindex_all_individuals()
            logger.info("Individual recognition backfill: indexed %d individuals", indexed)

        # Recognition stage: resolves an extracted individual to an existing
        # graph node before individual_extraction apply() treats it as new.
        individual_recognizer = CascadeIndividualRecognizer(
            individual_index=individual_vector_index,
            embedding_service=embedding_service,
            llm=llm_router,
            threshold=settings.recognition.individual_match_threshold,
        )
        app.state.individual_recognizer = individual_recognizer
        logger.info("CascadeIndividualRecognizer created")

        ontology_service = OntologyService(
            repository=ontology_repo,
            embedding_service=embedding_service,
            event_publisher=event_publisher,
            schema_index=schema_vector_index,
            individual_index=individual_vector_index,
            transaction_scope=SqliteTransactionScope(shared_session_factory),
        )
        logger.info("OntologyService created and wired with adapters")

        graph_engine = NetworkXGraphEngine()
        query_engine = RDFLibQueryEngine()
        graph_service = GraphAnalysisService(
            repository=cast(OntologyRepository, ontology_repo),
            graph_engine=graph_engine,
            query_engine=query_engine,
        )
        logger.info("GraphAnalysisService created and wired with adapters")

        extraction_service = ExtractionService(
            ontology_repo=cast(OntologyRepository, ontology_repo),
            embedding_service=embedding_service,
            llm=llm_router,
            nlp=nlp_processor,
            reference_sources=reference_sources,
            event_publisher=event_publisher,
            extraction_repo=extraction_repo,
            extraction_run_repo=extraction_run_repo,
            schema_index=schema_vector_index,
            individual_index=individual_vector_index,
            individual_recognizer=individual_recognizer,
        )
        logger.info("ExtractionService created and wired with adapters")

        # Register every pipeline's implementations and system configurations,
        # with the defaults a run gets when it names none (traversal and other
        # dependencies are injected when an orchestrator is instantiated)
        pipeline_resolver = register_pipelines(implementation_registry, config_registry)
        logger.info("Pipelines registered")

        # Create schema node grounding orchestrator
        grounding_adapter = GroundingAdapter(
            dbpedia=dbpedia_source,
            conceptnet=conceptnet_source,
            wikidata=wikidata_source,
            schema_org=schema_org_source,
        )

        def log_embedding_error(node_label: str, candidate_label: str, error: Exception) -> None:
            logger.warning(
                f"Failed to compute embedding similarity for '{node_label}' vs "
                f"'{candidate_label}': {error}. Semantic similarity score set to "
                f"0.0 (40% of grounding confidence)"
            )

        grounding_scorer = GroundingScorer(
            embedding_service=embedding_service,
            error_callback=log_embedding_error,
        )

        # Load user-created pipeline configurations from DB into the in-memory registry
        try:
            loaded = load_user_configurations(pipeline_config_repo, config_registry)
            if loaded:
                logger.info(f"Loaded {loaded} user pipeline configurations from DB")
        except Exception as cfg_exc:
            logger.warning(f"Failed to load user pipeline configurations: {cfg_exc}")

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

        from domain.versioning.revert_service import RevertService

        revert_service = RevertService(
            change_repo=change_repo,
            ontology_repo=cast(OntologyRepository, ontology_repo),
            schema_index=schema_vector_index,
            individual_index=individual_vector_index,
            event_publisher=event_publisher,
            transaction_scope=SqliteTransactionScope(shared_session_factory),
        )
        logger.info(
            "RevertService created and wired with repositories, vector indexes and event publisher"
        )

        approval_policy_repo = SQLiteApprovalPolicyRepository(shared_session_factory)
        proposal_repo = SQLiteChangeProposalRepository(shared_session_factory)
        # Gold backfill (#1407): operations decided before decisions were
        # recorded get one (decided_by "unknown"). Idempotent: once every decided
        # operation has a decision, this finds nothing.
        try:
            backfilled = proposal_repo.backfill_decisions()
            if backfilled:
                logger.info("Gold backfill: recorded %d decisions", backfilled)
        except OperationalError as exc:  # local.db not migrated to the gold table yet
            logger.error("Gold backfill skipped (run migrations): %s", exc)
        except Exception:  # noqa: BLE001 - history must never stop the app starting
            logger.exception("Gold backfill failed; skipped")
        proposal_service = ProposalService(
            proposals=proposal_repo,
            ontology_service=ontology_service,
            ontology_repo=cast(OntologyRepository, ontology_repo),
            revert_service=revert_service,
            approval_policies=approval_policy_repo,
            apply_rules=[
                DrRelationshipRules(cast(OntologyRepository, ontology_repo)),
                DrPredicateRules(cast(OntologyRepository, ontology_repo)),
            ],
            transaction_scope=SqliteTransactionScope(shared_session_factory),
            event_publisher=event_publisher,
            entity_sources=SQLiteEntitySourceRepository(shared_session_factory),
        )
        approval_policy_service = ApprovalPolicyService(
            approval_policy_repo, cast(OntologyRepository, ontology_repo)
        )
        logger.info("ProposalService and ApprovalPolicyService created")
        claim_service = ClaimService(
            SQLiteClaimRepository(shared_session_factory), cast(OntologyRepository, ontology_repo)
        )
        # Sources' original files are kept beside the workspace databases
        sources_dir = Path(settings.database.local_db_path).resolve().parent / "sources"
        source_service = SourceService(
            sources=SQLiteSourceRepository(local_session_factory),
            ontology_repo=cast(OntologyRepository, ontology_repo),
            readers=source_readers(),
            # Wikipedia pages go through the reference proxy (cached, rate limited)
            fetcher=HttpPageFetcher(
                proxied={
                    reference_proxy.upstream_url("wikipedia"): reference_proxy.base_url(
                        "wikipedia"
                    )
                }
            ),
            files=LocalSourceFileStore(sources_dir),
            max_bytes=settings.sources.max_bytes,
        )
        try:
            interrupted = source_service.fail_interrupted_fetches()
            if interrupted:
                logger.info("Failed %d source fetches the last run left unfinished", interrupted)
        except OperationalError as exc:  # local.db not migrated to the sources table yet
            logger.error("Source fetch cleanup skipped (run migrations): %s", exc)
        logger.info("SourceService created; originals kept in %s", sources_dir)

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

        admin_service = AdminService(
            metrics_collector=metrics_collector,
            config_store=config_store,
        )
        logger.info(
            "AdminService created and wired with metrics, config store, and dataset" " repository"
        )

        # Example paragraphs for the extraction review page (read-only, ships with the app)
        app.state.extraction_examples = load_extraction_examples()
        logger.info(f"Loaded {len(app.state.extraction_examples)} extraction examples")

        # Demo dataset loader (canon-backed, offline)
        canon_root = Path(__file__).resolve().parent / "datafiles" / "canon"
        demo_loader = CanonDemoDatasetLoader(
            canon_root=canon_root,
            ontology_repo=ontology_repo,
        )
        load_demo_dataset = LoadDemoDataset(loader=demo_loader)
        logger.info("CanonDemoDatasetLoader and LoadDemoDataset use case created")

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

        event_publisher.subscribe(RelationshipUpdated, change_recorder.on_relationship_updated)
        logger.info(
            "Event subscription: RelationshipUpdated ->"
            " ChangeEventRecorder.on_relationship_updated"
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

        event_publisher.subscribe(
            AttributeDefinitionDeleted, change_recorder.on_attribute_definition_deleted
        )
        event_publisher.subscribe(
            AttributeDefinitionCreated, change_recorder.on_attribute_definition_created
        )
        event_publisher.subscribe(
            AttributeDefinitionUpdated, change_recorder.on_attribute_definition_updated
        )
        event_publisher.subscribe(PredicateCreated, change_recorder.on_predicate_created)
        event_publisher.subscribe(PredicateUpdated, change_recorder.on_predicate_updated)
        event_publisher.subscribe(PredicateDeleted, change_recorder.on_predicate_deleted)
        logger.info(
            "Event subscription: AttributeDefinitionCreated/Updated/Deleted ->"
            " ChangeEventRecorder.on_attribute_definition_*"
        )

        # --- Store services in app.state for dependency injection ---

        app.state.ontology_service = ontology_service
        app.state.graph_service = graph_service
        app.state.extraction_service = extraction_service
        app.state.versioning_service = versioning_service
        app.state.revert_service = revert_service
        app.state.proposal_service = proposal_service
        app.state.bundle_import_service = BundleImportService(
            proposal_service, ontology_service, cast(OntologyRepository, ontology_repo)
        )
        app.state.drift_import_service = DriftImportService(
            proposal_service,
            ontology_service,
            DrDriftPlanner(cast(OntologyRepository, ontology_repo)),
        )
        app.state.approval_policy_service = approval_policy_service
        app.state.claim_service = claim_service
        app.state.source_service = source_service
        app.state.admin_service = admin_service
        app.state.load_demo_dataset = load_demo_dataset
        app.state.db_manager = db_manager
        app.state.reference_sources = reference_sources
        # ConceptNet source for open-extraction enrichment.
        app.state.conceptnet_source = conceptnet_source
        app.state.ontology_repo = ontology_repo
        app.state.change_repo = change_repo
        app.state.interchange_repo = interchange_repo
        app.state.import_run_service = import_run_service

        # Store pipeline run repo and registries for generic pipeline endpoints
        app.state.pipeline_run_repo = pipeline_run_repo
        app.state.batch_repo = batch_repo
        app.state.implementation_registry = implementation_registry
        app.state.config_registry = config_registry
        app.state.type_registry = type_registry
        app.state.pipeline_config_repo = pipeline_config_repo

        # Pipeline apply services — materialize pipeline output into ontology entities
        app.state.schema_extraction_apply_svc = SchemaExtractionApplyService(
            ontology_service, ontology_repo
        )
        app.state.schema_recognition_preview_svc = SchemaRecognitionPreviewService(
            ontology_repo, schema_index=schema_vector_index, embedding_service=embedding_service
        )
        app.state.individual_extraction_apply_svc = IndividualExtractionApplyService(
            ontology_service, ontology_repo, individual_recognizer=individual_recognizer
        )
        app.state.schema_grounding_apply_svc = SchemaGroundingApplyService(
            ontology_service, ontology_repo
        )
        app.state.schema_definition_apply_svc = SchemaDefinitionRefinementApplyService(
            ontology_service, ontology_repo
        )
        app.state.schema_connection_apply_svc = SchemaConnectionRefinementApplyService(
            ontology_service, ontology_repo
        )

        # Store grounding dependencies for orchestrator factory
        app.state.grounding_adapter = grounding_adapter
        app.state.grounding_scorer = grounding_scorer
        app.state.extraction_repo = extraction_repo

        # Store adapters needed for health checks
        app.state.nlp_processor = nlp_processor
        app.state.llm_router = llm_router

        # Ports for the open extraction pipelines (open_v1 implementations)
        app.state.embedding_service = embedding_service
        app.state.clusterer = clusterer
        app.state.schema_vector_index = schema_vector_index

        # Background pipeline runs (#1409): workers execute pending runs off the
        # request; runs left RUNNING by a previous process become INTERRUPTED
        app.state.run_executor = BackgroundRunExecutor(
            runs=pipeline_run_repo,
            batches=batch_repo,
            implementations=implementation_registry,
            configurations=config_registry,
            llm_provider=llm_router,
            app_state=app.state,
            workers=settings.pipelines.background_workers,
        )
        # Extracting a source (#1552): background runs that each end in a proposal
        app.state.source_extraction_service = SourceExtractionService(
            sources=SQLiteSourceRepository(local_session_factory),
            ontology_repo=cast(OntologyRepository, ontology_repo),
            resolver=pipeline_resolver,
            submitter=app.state.run_executor,
            runs=pipeline_run_repo,
            proposals=proposal_repo,
        )

        def run_tools_for(requested_via: RequestedVia) -> Sequence[ToolBase]:
            """The run tools for one caller; its runs record where they came from."""
            return build_run_tools(
                app.state.run_executor, pipeline_run_repo, ontology_service, requested_via
            )

        # Read-only tools over the ontology and graph services, and the proposal
        # tools (propose changes; a person reviews them), shared by the chat
        # assistant and the MCP server so both can do the same things
        read_tools = build_chat_tools(
            ontology_service,
            graph_service,
            embedding=embedding_service,
            schema_index=schema_vector_index,
            individual_index=individual_vector_index,
            sources_of=proposal_service.sources_of,
        )
        app.state.chat_service = ChatService(
            model=llm_router,
            tools=[
                *read_tools,
                *build_proposal_tools(proposal_service, ProposalSource.CHAT),
                *run_tools_for(RequestedVia.CHAT),
            ],
            repository=SqliteConversationRepository(operations_session_factory),
            settings=ConfigChatSettings(config_manager),
            workspace=OntologyWorkspaceContext(ontology_service),
        )

        logger.info("Services registered in app.state for dependency injection")

        # Instrument app after FastAPI and database are initialized
        telemetry.instrument_app(app, db_engine=db_manager.get_local_engine())

        async with AsyncExitStack() as mcp_stack:
            # MCP server for Claude Code and other MCP clients, loopback hosts only
            if is_loopback_host(settings.server.host):
                await start_mcp_server(
                    mcp_stack,
                    mcp_endpoint,
                    app.state,
                    config_manager,
                    read_tools,
                    ontology_service,
                    BundleExporter(ontology_repo),
                    write_tools=[
                        *build_proposal_tools(proposal_service, ProposalSource.MCP),
                        MarkProposalLandedTool(proposal_service, ProposalSource.MCP),
                        DrSpecDriftTool(app.state.drift_import_service),
                        *build_interchange_tools(
                            proposal_service, ontology_repo, ProposalSource.MCP
                        ),
                        *run_tools_for(RequestedVia.MCP),
                        *build_source_tools(
                            source_service,
                            app.state.source_extraction_service,
                            settings.sources.allowed_roots,
                        ),
                        *build_claim_tools(claim_service),
                    ],
                )
                logger.info("MCP server available at /mcp (bearer token required)")
            else:
                logger.warning(
                    "MCP server not started: server.host %r is not a loopback address",
                    settings.server.host,
                )

            app.state.run_executor.start()
            try:
                yield
            finally:
                app.state.run_executor.stop()

            mcp_endpoint.session_manager = None
            mcp_endpoint.auth_token = None

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
            reference_proxy.stop()
        except Exception as e:
            logger.error(f"Error stopping reference proxy: {e}")

        try:
            telemetry.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down telemetry: {e}")

        logger.info("Cleanup completed")


app = FastAPI(lifespan=lifespan, title="Context Studio", version="1.0.0")

# Get settings for middleware configuration from global singleton
settings = get_settings()

# Only the app's own UI may call the API from a browser
add_browser_guards(app, settings.server)

# Include routers (these are the FastAPI APIRouter instances)
app.include_router(ontology_router)
app.include_router(graph_router)
app.include_router(extraction_router)
app.include_router(pipelines_router)
app.include_router(pipeline_config_router)
app.include_router(reference_router)
app.include_router(versioning_router)
app.include_router(admin_router)
app.include_router(interchange_router)
app.include_router(chat_router)
app.include_router(proposals_router)
app.include_router(claims_router)
app.include_router(sources_router)
app.include_router(bundle_router)
app.include_router(drift_router)
app.include_router(decision_router)
# A route rather than a mount, so POST /mcp is served without a redirect to /mcp/
app.add_route("/mcp", mcp_endpoint, include_in_schema=False)


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
