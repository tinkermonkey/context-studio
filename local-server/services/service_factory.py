"""
Service Factory - Production-ready service creation and caching

This module implements a sophisticated service factory pattern with intelligent caching,
performance monitoring, and lifecycle management for better resource utilization.
"""

import uuid
from typing import Dict, Any, Optional, TypeVar, Type, Callable, List, cast
from threading import RLock
from time import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from dataclasses import dataclass, field
from enum import Enum
from fastapi import Depends

from services.ontology_entity_service import OntologyEntityService
from services.relationship_service import RelationshipService
from services.node_service import NodeService  # Re-exported from OntologyEntityService
from services.node_link_service import (
    NodeLinkService,
)  # Re-exported from RelationshipService
from services.version_manager import VersionManager
from services.working_tree_manager import WorkingTreeManager
from services.diff_generator import DiffGenerator
from services.s3_sync_manager import S3SyncManager
from services.changeset_manager import ChangesetManager
from services.proposal_manager import ProposalManager
from services.crdt_merge_engine import CRDTMergeEngine
from services.identity_manager import IdentityManager
from services.conflict_resolution_engine import (
    ConflictResolutionEngine,
    IntelligentConflictDetector,
)
from services.duckdb_service import DuckDBService, ChangeAnalyticsEngine
from services.incremental_sync_engine import IncrementalSyncEngine

# Phase 5 Optimization Services
from services.duckdb_query_analyzer import DuckDBQueryAnalyzer
from services.s3_storage_manager import S3StorageManager
from services.hierarchical_diff_engine import HierarchicalDiffEngine
from services.batch_operation_processor import BatchOperationProcessor
from services.performance_monitor import PerformanceMonitor
from graph.graph_service import GraphService
from graph.network_service import NetworkService
from graph.sparql_service import SPARQLService
from llm.flavor_service import PipelineFlavorService
from llm.service import LLMService
from llm.execution_tracker import ExecutionTracker
from reference_api.service import ReferenceService
from database.utils import get_db
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ServiceType(Enum):
    """Enumeration of supported service types."""

    # New primary names
    ONTOLOGY_ENTITY_SERVICE = "ontology_entity_service"
    RELATIONSHIP_SERVICE = "relationship_service"
    # Deprecated aliases (kept for backward compatibility)
    NODE_SERVICE = "node_service"
    NODE_LINK_SERVICE = "node_link_service"
    VERSION_MANAGER = "version_manager"
    WORKING_TREE_MANAGER = "working_tree_manager"
    DIFF_GENERATOR = "diff_generator"
    GRAPH_SERVICE = "graph_service"
    NETWORK_SERVICE = "network_service"
    SPARQL_SERVICE = "sparql_service"
    PIPELINE_FLAVOR_SERVICE = "pipeline_flavor_service"
    LLM_SERVICE = "llm_service"
    EXECUTION_TRACKER = "execution_tracker"
    REFERENCE_SERVICE = "reference_service"
    S3_SYNC_MANAGER = "s3_sync_manager"
    CHANGESET_MANAGER = "changeset_manager"
    PROPOSAL_MANAGER = "proposal_manager"
    CRDT_MERGE_ENGINE = "crdt_merge_engine"
    IDENTITY_MANAGER = "identity_manager"
    # Phase 4 Advanced Features
    CONFLICT_RESOLUTION_ENGINE = "conflict_resolution_engine"
    DUCKDB_SERVICE = "duckdb_service"
    CHANGE_ANALYTICS_ENGINE = "change_analytics_engine"
    INCREMENTAL_SYNC_ENGINE = "incremental_sync_engine"
    # Phase 5 Analysis and Management Services
    DUCKDB_QUERY_ANALYZER = "duckdb_query_analyzer"
    S3_STORAGE_MANAGER = "s3_storage_manager"
    HIERARCHICAL_DIFF_ENGINE = "hierarchical_diff_engine"
    BATCH_OPERATION_PROCESSOR = "batch_operation_processor"
    PERFORMANCE_MONITOR = "performance_monitor"


@dataclass
class ServiceMetrics:
    """Metrics tracking for service creation and usage."""

    service_type: str
    total_created: int = 0
    total_cache_hits: int = 0
    total_cache_misses: int = 0
    avg_creation_time_ms: float = 0.0
    last_created_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    creation_times: List[float] = field(default_factory=list)

    def record_creation(self, creation_time_ms: float):
        """Record a service creation event."""
        self.total_created += 1
        self.creation_times.append(creation_time_ms)

        # Keep only last 100 creation times for rolling average
        if len(self.creation_times) > 100:
            self.creation_times = self.creation_times[-100:]

        self.avg_creation_time_ms = sum(self.creation_times) / len(self.creation_times)
        self.last_created_at = datetime.now(timezone.utc)

    def record_cache_hit(self):
        """Record a cache hit event."""
        self.total_cache_hits += 1
        self.last_accessed_at = datetime.now(timezone.utc)

    def record_cache_miss(self):
        """Record a cache miss event."""
        self.total_cache_misses += 1
        self.last_accessed_at = datetime.now(timezone.utc)

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total_requests = self.total_cache_hits + self.total_cache_misses
        if total_requests == 0:
            return 0.0
        return (self.total_cache_hits / total_requests) * 100.0


@dataclass
class CachedServiceEntry:
    """Cache entry with metadata for service factory."""

    service_class: Type
    service_key: str
    created_at: float
    access_count: int = 0
    last_accessed: float = 0
    creation_time_ms: float = 0

    def touch(self):
        """Update access tracking."""
        self.access_count += 1
        self.last_accessed = time()

    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time() - self.created_at


class ServiceFactory:
    """
    Production-ready service factory with intelligent caching and performance monitoring.

    This factory provides:
    - Service class caching to avoid repeated imports and reflection
    - Performance metrics and monitoring
    - Configurable cache TTL and cleanup
    - Thread-safe operations
    - Health monitoring and diagnostics
    """

    def __init__(self, cache_ttl_seconds: int = 3600, cleanup_interval: int = 300):
        """
        Initialize the service factory.

        Args:
            cache_ttl_seconds: Time-to-live for cached service classes in seconds
            cleanup_interval: Interval between cache cleanup operations in seconds
        """
        self._cache: Dict[str, CachedServiceEntry] = {}
        self._metrics: Dict[str, ServiceMetrics] = {}
        self._lock = RLock()  # Using RLock for reentrant operations
        self._cache_ttl = cache_ttl_seconds
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time()
        self._factory_id = str(uuid.uuid4())[:8]

        # Initialize metrics for all service types
        for service_type in ServiceType:
            self._metrics[service_type.value] = ServiceMetrics(service_type.value)

        logger.info(
            f"ServiceFactory [{self._factory_id}] initialized with {cache_ttl_seconds}s TTL"
        )

    def create_ontology_entity_service(
        self,
        db: Session,
        graph_service: Optional[GraphService] = None,
        version_manager: Optional[VersionManager] = None,
        working_tree_manager: Optional[WorkingTreeManager] = None,
    ) -> OntologyEntityService:
        """
        Create OntologyEntityService with optimized instantiation.

        Args:
            db: Database session for this request
            graph_service: Optional graph service dependency
            version_manager: Optional version manager for versioning
            working_tree_manager: Optional working tree manager for state tracking

        Returns:
            OntologyEntityService instance
        """
        if version_manager is None:
            version_manager = self.create_version_manager(db)

        if working_tree_manager is None:
            working_tree_manager = self.create_working_tree_manager(db, version_manager)

        return self._create_service(
            ServiceType.ONTOLOGY_ENTITY_SERVICE,
            OntologyEntityService,
            db,
            graph_service,
            version_manager,
            working_tree_manager,
        )

    def create_relationship_service(self, db: Session) -> RelationshipService:
        """
        Create RelationshipService with optimized instantiation.

        Args:
            db: Database session for this request

        Returns:
            RelationshipService instance
        """
        return self._create_service(
            ServiceType.RELATIONSHIP_SERVICE, RelationshipService, db
        )

    def create_node_service(
        self,
        db: Session,
        graph_service: Optional[GraphService] = None,
        version_manager: Optional[VersionManager] = None,
        working_tree_manager: Optional[WorkingTreeManager] = None,
    ) -> NodeService:
        """
        DEPRECATED: Use create_ontology_entity_service() instead.

        This method is kept for backward compatibility and delegates to
        create_ontology_entity_service().

        Args:
            db: Database session for this request
            graph_service: Optional graph service dependency
            version_manager: Optional version manager for versioning
            working_tree_manager: Optional working tree manager for state tracking

        Returns:
            NodeService instance (alias for OntologyEntityService)
        """
        return self.create_ontology_entity_service(db, graph_service, version_manager, working_tree_manager)  # type: ignore

    def create_node_link_service(self, db: Session) -> NodeLinkService:
        """
        DEPRECATED: Use create_relationship_service() instead.

        This method is kept for backward compatibility and delegates to
        create_relationship_service().

        Args:
            db: Database session for this request

        Returns:
            NodeLinkService instance (alias for RelationshipService)
        """
        return self.create_relationship_service(db)  # type: ignore

    def create_version_manager(self, db: Session) -> VersionManager:
        """
        Create VersionManager with optimized instantiation.

        Args:
            db: Database session for this request

        Returns:
            VersionManager instance
        """
        return self._create_service(ServiceType.VERSION_MANAGER, VersionManager, db)

    def create_working_tree_manager(
        self, db: Session, version_manager: Optional[VersionManager] = None
    ) -> WorkingTreeManager:
        """
        Create WorkingTreeManager with optimized instantiation.

        Args:
            db: Database session for this request
            version_manager: Optional VersionManager dependency

        Returns:
            WorkingTreeManager instance
        """
        if version_manager is None:
            version_manager = self.create_version_manager(db)

        return self._create_service(
            ServiceType.WORKING_TREE_MANAGER, WorkingTreeManager, db, version_manager
        )

    def create_diff_generator(
        self,
        db: Session,
        version_manager: Optional[VersionManager] = None,
        working_tree_manager: Optional[WorkingTreeManager] = None,
    ) -> DiffGenerator:
        """
        Create DiffGenerator with optimized instantiation.

        Args:
            db: Database session for this request
            version_manager: Optional VersionManager dependency
            working_tree_manager: Optional WorkingTreeManager dependency

        Returns:
            DiffGenerator instance
        """
        if version_manager is None:
            version_manager = self.create_version_manager(db)

        if working_tree_manager is None:
            working_tree_manager = self.create_working_tree_manager(db, version_manager)

        return self._create_service(
            ServiceType.DIFF_GENERATOR,
            DiffGenerator,
            version_manager,
            working_tree_manager,
        )

    def create_graph_service(self, db: Session) -> GraphService:
        """
        Create GraphService with optimized instantiation.

        Args:
            db: Database session for this request

        Returns:
            GraphService instance
        """
        return self._create_service(ServiceType.GRAPH_SERVICE, GraphService, db)

    def create_network_service(self, db: Session) -> NetworkService:
        """
        Create NetworkService with optimized instantiation.

        Args:
            db: Database session for this request

        Returns:
            NetworkService instance
        """
        return self._create_service(ServiceType.NETWORK_SERVICE, NetworkService, db)

    def create_sparql_service(self, db: Session) -> SPARQLService:
        """
        Create SPARQLService with optimized instantiation.

        Args:
            db: Database session for this request

        Returns:
            SPARQLService instance
        """
        return self._create_service(ServiceType.SPARQL_SERVICE, SPARQLService, db)

    def create_pipeline_flavor_service(self) -> PipelineFlavorService:
        """
        Create PipelineFlavorService with optimized instantiation.

        Returns:
            PipelineFlavorService instance
        """
        return self._create_service(
            ServiceType.PIPELINE_FLAVOR_SERVICE, PipelineFlavorService
        )

    def create_llm_service(
        self, model_name: str = "gpt-3.5-turbo", temperature: float = 0
    ) -> LLMService:
        """
        Create LLMService with optimized instantiation.

        Args:
            model_name: LLM model name
            temperature: Temperature setting for the model

        Returns:
            LLMService instance
        """
        service_key = f"{ServiceType.LLM_SERVICE.value}_{model_name}_{temperature}"
        return self._create_service_with_key(
            service_key, ServiceType.LLM_SERVICE, LLMService, model_name, temperature
        )

    def get_execution_tracker(self) -> ExecutionTracker:
        """
        Get ExecutionTracker instance.

        ExecutionTracker is stateless and doesn't need caching.

        Returns:
            ExecutionTracker instance
        """
        return ExecutionTracker()

    def create_reference_service(self) -> ReferenceService:
        """
        Create ReferenceService with optimized instantiation.

        Returns:
            ReferenceService instance
        """
        return self._create_service(ServiceType.REFERENCE_SERVICE, ReferenceService)

    def create_changeset_manager(
        self,
        db: Session,
        s3_sync_manager: Optional[S3SyncManager] = None,
        working_tree_manager: Optional[WorkingTreeManager] = None,
        version_manager: Optional[VersionManager] = None,
    ) -> ChangesetManager:
        """
        Create ChangesetManager with optimized instantiation.

        Args:
            db: Database session for this request
            s3_sync_manager: Optional S3SyncManager dependency
            working_tree_manager: Optional WorkingTreeManager dependency
            version_manager: Optional VersionManager dependency

        Returns:
            ChangesetManager instance
        """

        def create_service() -> ChangesetManager:
            s3_sync = s3_sync_manager or self.get_s3_sync_manager(db)
            working_tree = working_tree_manager or self.create_working_tree_manager(db)
            version_mgr = version_manager or self.create_version_manager(db)
            return ChangesetManager(db, s3_sync, working_tree, version_mgr)

        return self._create_service_with_factory(
            ServiceType.CHANGESET_MANAGER, create_service
        )

    def create_proposal_manager(
        self,
        db: Session,
        s3_sync_manager: Optional[S3SyncManager] = None,
        changeset_manager: Optional[ChangesetManager] = None,
    ) -> ProposalManager:
        """
        Create ProposalManager with optimized instantiation.

        Args:
            db: Database session for this request
            s3_sync_manager: Optional S3SyncManager dependency
            changeset_manager: Optional ChangesetManager dependency

        Returns:
            ProposalManager instance
        """

        def create_service() -> ProposalManager:
            s3_sync = s3_sync_manager or self.get_s3_sync_manager(db)
            changeset_mgr = changeset_manager or self.create_changeset_manager(db)
            return ProposalManager(db, s3_sync, changeset_mgr)

        return self._create_service_with_factory(
            ServiceType.PROPOSAL_MANAGER, create_service
        )

    def create_crdt_merge_engine(
        self,
        db: Session,
        version_manager: Optional[VersionManager] = None,
        changeset_manager: Optional[ChangesetManager] = None,
    ) -> CRDTMergeEngine:
        """
        Create CRDTMergeEngine with optimized instantiation.

        Args:
            db: Database session for this request
            version_manager: Optional VersionManager dependency
            changeset_manager: Optional ChangesetManager dependency

        Returns:
            CRDTMergeEngine instance
        """

        def create_service() -> CRDTMergeEngine:
            version_mgr = version_manager or self.create_version_manager(db)
            changeset_mgr = changeset_manager or self.create_changeset_manager(db)
            return CRDTMergeEngine(db, version_mgr, changeset_mgr)

        return self._create_service_with_factory(
            ServiceType.CRDT_MERGE_ENGINE, create_service
        )

    def create_identity_manager(
        self, db: Session, s3_sync_manager: Optional[S3SyncManager] = None
    ) -> IdentityManager:
        """
        Create IdentityManager with optimized instantiation.

        Args:
            db: Database session for this request
            s3_sync_manager: Optional S3SyncManager dependency

        Returns:
            IdentityManager instance
        """

        def create_service() -> IdentityManager:
            s3_sync = s3_sync_manager or self.get_s3_sync_manager(db)
            return IdentityManager(db, s3_sync)

        return self._create_service_with_factory(
            ServiceType.IDENTITY_MANAGER, create_service
        )

    # Phase 4 Advanced Features Services

    def create_conflict_resolution_engine(
        self, db: Session
    ) -> ConflictResolutionEngine:
        """
        Create ConflictResolutionEngine with optimized instantiation and dependency injection.

        Args:
            db: Database session for this request

        Returns:
            ConflictResolutionEngine instance
        """

        def create_service() -> ConflictResolutionEngine:
            version_manager = self.create_version_manager(db)
            conflict_detector = IntelligentConflictDetector(version_manager)
            return ConflictResolutionEngine(db, conflict_detector, version_manager)

        return self._create_service_with_factory(
            ServiceType.CONFLICT_RESOLUTION_ENGINE, create_service
        )

    def create_duckdb_service(
        self, s3_config: Optional[Dict[str, str]] = None
    ) -> DuckDBService:
        """
        Create DuckDBService with optimized instantiation.

        Args:
            s3_config: Optional S3 configuration dictionary

        Returns:
            DuckDBService instance
        """

        def create_service() -> DuckDBService:
            if s3_config is None:
                settings = get_settings()
                s3_config_obj = settings.get_s3_config()
                # Convert S3Config to dict if needed
                if s3_config_obj is not None:
                    s3_conf = {
                        "bucket": s3_config_obj.bucket,
                        "region": s3_config_obj.region,
                        "access_key": s3_config_obj.access_key or "",
                        "secret_key": s3_config_obj.secret_key or "",
                        "endpoint": s3_config_obj.endpoint or "",
                    }
                else:
                    s3_conf = None
            else:
                s3_conf = s3_config
            return DuckDBService(db_path=None, s3_config=s3_conf)

        return self._create_service_with_factory(
            ServiceType.DUCKDB_SERVICE, create_service
        )

    def create_change_analytics_engine(
        self, duckdb_service: Optional[DuckDBService] = None
    ) -> ChangeAnalyticsEngine:
        """
        Create ChangeAnalyticsEngine with optimized instantiation and dependency injection.

        Args:
            duckdb_service: Optional DuckDBService dependency

        Returns:
            ChangeAnalyticsEngine instance
        """

        def create_service() -> ChangeAnalyticsEngine:
            duckdb = duckdb_service or self.create_duckdb_service()
            return ChangeAnalyticsEngine(duckdb)

        return self._create_service_with_factory(
            ServiceType.CHANGE_ANALYTICS_ENGINE, create_service
        )

    def create_incremental_sync_engine(
        self, db: Session, s3_sync_manager: Optional[S3SyncManager] = None
    ) -> IncrementalSyncEngine:
        """
        Create IncrementalSyncEngine with optimized instantiation and dependency injection.

        Args:
            db: Database session for this request
            s3_sync_manager: Optional S3SyncManager dependency

        Returns:
            IncrementalSyncEngine instance
        """

        def create_service() -> IncrementalSyncEngine:
            # Create required dependencies with proper defaults
            duckdb_service = self.create_duckdb_service()
            version_manager = self.create_version_manager(db)

            # Get S3 config from settings or use defaults
            try:
                settings = get_settings()
                s3_config_obj = settings.get_s3_config()
            except Exception as e:
                logger.error(
                    f"Failed to retrieve S3 configuration for IncrementalSyncEngine: {e}",
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Cannot create IncrementalSyncEngine without valid S3 configuration: {e}"
                ) from e

            if s3_config_obj is None:
                raise RuntimeError(
                    "S3 configuration is required for IncrementalSyncEngine. "
                    "Please configure S3 settings in your configuration."
                )

            if not s3_config_obj.access_key:
                raise RuntimeError(
                    "S3 access_key is required but not configured for IncrementalSyncEngine."
                )
            if not s3_config_obj.secret_key:
                raise RuntimeError(
                    "S3 secret_key is required but not configured for IncrementalSyncEngine."
                )
            if not s3_config_obj.bucket:
                raise RuntimeError(
                    "S3 bucket is required but not configured for IncrementalSyncEngine."
                )

            s3_config_dict = {
                "aws_access_key_id": s3_config_obj.access_key,
                "aws_secret_access_key": s3_config_obj.secret_key,
                "region": s3_config_obj.region,
                "bucket": s3_config_obj.bucket,
            }

            return IncrementalSyncEngine(
                db, duckdb_service, version_manager, s3_config_dict
            )

        return self._create_service_with_factory(
            ServiceType.INCREMENTAL_SYNC_ENGINE, create_service
        )

    # Phase 5 Optimization Services

    def create_duckdb_query_analyzer(
        self,
        duckdb_conn: Optional[Any] = None,
        s3_config: Optional[Dict[str, str]] = None,
    ) -> DuckDBQueryAnalyzer:
        """
        Create DuckDBQueryAnalyzer with optimized instantiation and dependency injection.

        Args:
            duckdb_conn: Optional DuckDB connection
            s3_config: Optional S3 configuration dictionary

        Returns:
            DuckDBQueryAnalyzer instance
        """

        def create_service() -> DuckDBQueryAnalyzer:
            if s3_config is None:
                try:
                    settings = get_settings()
                    s3_config_obj = settings.get_s3_config()
                except Exception as e:
                    logger.error(
                        f"Failed to retrieve S3 configuration for DuckDBQueryAnalyzer: {e}",
                        exc_info=True,
                    )
                    raise RuntimeError(
                        f"Cannot create DuckDBQueryAnalyzer without valid S3 configuration: {e}"
                    ) from e

                if s3_config_obj is None:
                    raise RuntimeError(
                        "S3 configuration is required for DuckDBQueryAnalyzer. "
                        "Please configure S3 settings in your configuration."
                    )

                if not s3_config_obj.bucket:
                    raise RuntimeError(
                        "S3 bucket is required but not configured for DuckDBQueryAnalyzer."
                    )

                s3_conf: Dict[str, str] = {
                    "enable_analyzer": "True",
                    "cache_size": "1000",
                    "query_timeout": "30",
                    "bucket_name": s3_config_obj.bucket,
                }
            else:
                s3_conf = s3_config

            if duckdb_conn is None:
                try:
                    duckdb_service = self.create_duckdb_service(s3_conf)
                    duckdb_connection = duckdb_service.connection
                except Exception as e:
                    logger.error(
                        f"Failed to create DuckDB service for DuckDBQueryAnalyzer: {e}",
                        exc_info=True,
                    )
                    raise RuntimeError(
                        f"Cannot create DuckDBQueryAnalyzer without valid DuckDB connection: {e}"
                    ) from e
            else:
                duckdb_connection = cast(Any, duckdb_conn)

            return DuckDBQueryAnalyzer(cast(Any, duckdb_connection), s3_conf)

        return self._create_service_with_factory(
            ServiceType.DUCKDB_QUERY_ANALYZER, create_service
        )

    def create_s3_storage_manager(
        self, s3_config: Optional[Dict[str, str]] = None
    ) -> S3StorageManager:
        """
        Create S3StorageManager with optimized instantiation and dependency injection.

        Args:
            s3_config: Optional S3 configuration dictionary

        Returns:
            S3StorageManager instance
        """

        def create_service() -> S3StorageManager:
            # Use provided s3_config if available, otherwise retrieve from settings
            s3_conf_dict: Dict[str, str]
            if s3_config is not None:
                s3_conf_dict = s3_config
            else:
                settings = get_settings()
                s3_config_obj = settings.get_s3_config()

                if s3_config_obj is None:
                    raise RuntimeError(
                        "S3 configuration is required for S3StorageManager. "
                        "Please configure S3 settings in your configuration."
                    )

                if not s3_config_obj.access_key:
                    raise RuntimeError(
                        "S3 access_key is required but not configured for S3StorageManager."
                    )
                if not s3_config_obj.secret_key:
                    raise RuntimeError(
                        "S3 secret_key is required but not configured for S3StorageManager."
                    )
                if not s3_config_obj.bucket:
                    raise RuntimeError(
                        "S3 bucket is required but not configured for S3StorageManager."
                    )

                s3_conf_dict = {
                    "aws_access_key_id": s3_config_obj.access_key,
                    "aws_secret_access_key": s3_config_obj.secret_key,
                    "region": s3_config_obj.region,
                    "bucket_name": s3_config_obj.bucket,
                }

            # Create S3 client with validated configuration
            try:
                import boto3  # type: ignore[import-untyped]

                s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=s3_conf_dict.get("aws_access_key_id"),
                    aws_secret_access_key=s3_conf_dict.get("aws_secret_access_key"),
                    region_name=s3_conf_dict.get("region", "us-east-1"),
                )
            except ImportError:
                # boto3 not installed, create a mock S3 client
                s3_client = None

            bucket_name = s3_conf_dict.get("bucket_name")
            if not bucket_name:
                raise RuntimeError(
                    "S3 bucket_name is required but missing from configuration for S3StorageManager."
                )

            return S3StorageManager(s3_client, bucket_name)

        return self._create_service_with_factory(
            ServiceType.S3_STORAGE_MANAGER, create_service
        )

    def create_hierarchical_diff_engine(
        self, db: Session, nlp_service=None
    ) -> HierarchicalDiffEngine:
        """
        Create HierarchicalDiffEngine with optimized instantiation and dependency injection.

        Args:
            db: Database session for this request
            nlp_service: Optional NLP service for semantic analysis

        Returns:
            HierarchicalDiffEngine instance
        """

        def create_service() -> HierarchicalDiffEngine:
            # nlp_service would come from actual NLP service dependency
            return HierarchicalDiffEngine(db, nlp_service)

        return self._create_service_with_factory(
            ServiceType.HIERARCHICAL_DIFF_ENGINE, create_service
        )

    def create_batch_operation_processor(
        self, db: Session, s3_sync_manager: Optional[S3SyncManager] = None
    ) -> BatchOperationProcessor:
        """
        Create BatchOperationProcessor with optimized instantiation and dependency injection.

        Args:
            db: Database session for this request
            s3_sync_manager: Optional S3SyncManager dependency

        Returns:
            BatchOperationProcessor instance
        """

        def create_service() -> BatchOperationProcessor:
            s3_sync = s3_sync_manager or self.get_s3_sync_manager(db)
            version_manager = self.create_version_manager(db)
            working_tree_manager = self.create_working_tree_manager(db)
            return BatchOperationProcessor(
                db, s3_sync, version_manager, working_tree_manager
            )

        return self._create_service_with_factory(
            ServiceType.BATCH_OPERATION_PROCESSOR, create_service
        )

    def create_performance_monitor(
        self,
        db_connection=None,
        duckdb_conn=None,
        s3_sync_manager: Optional[S3SyncManager] = None,
    ) -> PerformanceMonitor:
        """
        Create PerformanceMonitor with optimized instantiation and dependency injection.

        Args:
            db_connection: SQLite database connection
            duckdb_conn: Optional DuckDB connection for analytics
            s3_sync_manager: Optional S3 sync manager

        Returns:
            PerformanceMonitor instance
        """
        # DON'T cache PerformanceMonitor - it holds database connections that become stale
        # Create fresh instance each time to avoid session/connection issues

        # Use provided connections or create defaults for tests
        sqlite_connection = db_connection
        if sqlite_connection is None:
            try:
                sqlite_connection = self.get_database_connection()
            except Exception as e:
                logger.error(
                    f"Failed to get database connection for PerformanceMonitor: {e}",
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Cannot create PerformanceMonitor without valid SQLite connection: {e}"
                ) from e

        duckdb_connection = duckdb_conn
        if duckdb_connection is None:
            try:
                duckdb_service = self.create_duckdb_service()
                duckdb_connection = duckdb_service.connection
            except Exception as e:
                logger.error(
                    f"Failed to create DuckDB service for PerformanceMonitor: {e}",
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Cannot create PerformanceMonitor without valid DuckDB connection: {e}"
                ) from e

        s3_sync = s3_sync_manager

        return PerformanceMonitor(sqlite_connection, duckdb_connection, s3_sync)

    def get_database_connection(self):
        """Get database connection using the database utilities."""
        from database.utils import get_db

        return next(get_db())

    def get_s3_sync_manager(self, db_session: Session) -> S3SyncManager:
        """
        Get or create S3SyncManager instance.

        Args:
            db_session: Database session for this request

        Returns:
            S3SyncManager instance
        """

        # Create service with dependency injection for S3 config
        def create_service() -> S3SyncManager:
            settings = get_settings()
            s3_config = settings.get_s3_config()
            return S3SyncManager(db_session, s3_config)

        # Use the service type as cache key for session-independent caching of class metadata
        return self._create_service_with_factory(
            ServiceType.S3_SYNC_MANAGER, create_service
        )

    def _create_service_with_factory(
        self, service_type: ServiceType, factory_func: Callable[[], T]
    ) -> T:
        """
        Create service using a factory function instead of direct class instantiation.

        Args:
            service_type: Service type for metrics tracking
            factory_func: Factory function that creates the service instance

        Returns:
            Service instance
        """
        service_key = service_type.value
        metrics = self._metrics[service_type.value]

        with self._lock:
            self._maybe_cleanup()
            metrics.record_cache_miss()  # Always miss since we can't cache instances with sessions

            creation_start = time()
            instance = factory_func()
            creation_time_ms = (time() - creation_start) * 1000

            metrics.record_creation(creation_time_ms)

            logger.debug(
                f"Factory creation for {service_key} (creation: {creation_time_ms:.2f}ms)"
            )

            return instance

    def _create_service(
        self, service_type: ServiceType, service_class: Type[T], *args, **kwargs
    ) -> T:
        """
        Generic service creation with caching using service type as key.

        Args:
            service_type: Service type enumeration
            service_class: Service class to instantiate
            *args: Arguments for service constructor
            **kwargs: Keyword arguments for service constructor

        Returns:
            Service instance
        """
        return self._create_service_with_key(
            service_type.value, service_type, service_class, *args, **kwargs
        )

    def _create_service_with_key(
        self,
        service_key: str,
        service_type: ServiceType,
        service_class: Type[T],
        *args,
        **kwargs,
    ) -> T:
        """
        Generic service creation with caching using custom key.

        Args:
            service_key: Unique cache key for this service configuration
            service_type: Service type for metrics tracking
            service_class: Service class to instantiate
            *args: Arguments for service constructor
            **kwargs: Keyword arguments for service constructor

        Returns:
            Service instance
        """
        now = time()

        with self._lock:
            # Periodic cleanup
            self._maybe_cleanup()

            metrics = self._metrics[service_type.value]

            # Check if we have a cached entry
            if service_key in self._cache:
                entry = self._cache[service_key]

                # Check if cache entry is still valid
                if now - entry.created_at < self._cache_ttl:
                    entry.touch()
                    metrics.record_cache_hit()

                    # Create instance using cached class
                    creation_start = time()
                    instance = entry.service_class(*args, **kwargs)
                    creation_time_ms = (time() - creation_start) * 1000

                    metrics.record_creation(creation_time_ms)

                    logger.debug(
                        f"Cache HIT for {service_key} (access #{entry.access_count}, age: {entry.age_seconds:.1f}s)"
                    )
                    return cast(T, instance)
                else:
                    # Cache expired
                    logger.debug(
                        f"Cache EXPIRED for {service_key} (age: {entry.age_seconds:.1f}s)"
                    )
                    del self._cache[service_key]

            # Cache miss - create new entry
            metrics.record_cache_miss()

            creation_start = time()
            instance = service_class(*args, **kwargs)
            creation_time_ms = (time() - creation_start) * 1000

            # Create cache entry
            entry = CachedServiceEntry(
                service_class=service_class,
                service_key=service_key,
                created_at=now,
                access_count=1,
                last_accessed=now,
                creation_time_ms=creation_time_ms,
            )

            self._cache[service_key] = entry
            metrics.record_creation(creation_time_ms)

            logger.debug(
                f"Cache MISS for {service_key} - created new entry (creation: {creation_time_ms:.2f}ms)"
            )

            return cast(T, instance)

    def _maybe_cleanup(self):
        """Perform periodic cleanup of expired cache entries."""
        now = time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = []
        for key, entry in self._cache.items():
            if now - entry.created_at >= self._cache_ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        self._last_cleanup = now

        if expired_keys:
            logger.info(
                f"ServiceFactory [{self._factory_id}] cleaned up {len(expired_keys)} expired cache entries"
            )

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics for monitoring.

        Returns:
            Dictionary with cache statistics and performance metrics
        """
        with self._lock:
            # Force cleanup to get accurate stats
            self._maybe_cleanup()

            cache_info = {}
            for key, entry in self._cache.items():
                cache_info[key] = {
                    "access_count": entry.access_count,
                    "created_at": datetime.fromtimestamp(
                        entry.created_at, timezone.utc
                    ).isoformat(),
                    "last_accessed": datetime.fromtimestamp(
                        entry.last_accessed, timezone.utc
                    ).isoformat(),
                    "age_seconds": entry.age_seconds,
                    "creation_time_ms": entry.creation_time_ms,
                }

            service_metrics = {}
            for service_type, metrics in self._metrics.items():
                service_metrics[service_type] = {
                    "total_created": metrics.total_created,
                    "cache_hits": metrics.total_cache_hits,
                    "cache_misses": metrics.total_cache_misses,
                    "cache_hit_rate_percent": metrics.cache_hit_rate,
                    "avg_creation_time_ms": metrics.avg_creation_time_ms,
                    "last_created_at": (
                        metrics.last_created_at.isoformat()
                        if metrics.last_created_at
                        else None
                    ),
                    "last_accessed_at": (
                        metrics.last_accessed_at.isoformat()
                        if metrics.last_accessed_at
                        else None
                    ),
                }

            return {
                "factory_id": self._factory_id,
                "cache_ttl_seconds": self._cache_ttl,
                "cleanup_interval_seconds": self._cleanup_interval,
                "total_cache_entries": len(self._cache),
                "last_cleanup": datetime.fromtimestamp(
                    self._last_cleanup, timezone.utc
                ).isoformat(),
                "cache_entries": cache_info,
                "service_metrics": service_metrics,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary for quick monitoring.

        Returns:
            Dictionary with performance summary
        """
        with self._lock:
            total_created = sum(m.total_created for m in self._metrics.values())
            total_hits = sum(m.total_cache_hits for m in self._metrics.values())
            total_misses = sum(m.total_cache_misses for m in self._metrics.values())

            overall_hit_rate = (
                (total_hits / (total_hits + total_misses)) * 100.0
                if (total_hits + total_misses) > 0
                else 0.0
            )

            # Find best and worst performing services
            best_hit_rate = max(
                self._metrics.values(), key=lambda m: m.cache_hit_rate, default=None
            )
            worst_hit_rate = min(
                self._metrics.values(), key=lambda m: m.cache_hit_rate, default=None
            )

            return {
                "factory_id": self._factory_id,
                "overall_cache_hit_rate_percent": overall_hit_rate,
                "total_services_created": total_created,
                "total_cache_entries": len(self._cache),
                "best_performing_service": {
                    "type": best_hit_rate.service_type if best_hit_rate else None,
                    "hit_rate_percent": (
                        best_hit_rate.cache_hit_rate if best_hit_rate else 0.0
                    ),
                },
                "worst_performing_service": {
                    "type": worst_hit_rate.service_type if worst_hit_rate else None,
                    "hit_rate_percent": (
                        worst_hit_rate.cache_hit_rate if worst_hit_rate else 0.0
                    ),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

    def clear_cache(self):
        """Clear the service cache and reset metrics."""
        with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()

            # Reset all metrics including total_created for complete test isolation
            for metrics in self._metrics.values():
                metrics.total_created = 0
                metrics.total_cache_hits = 0
                metrics.total_cache_misses = 0
                metrics.avg_creation_time_ms = 0.0
                metrics.creation_times.clear()
                metrics.last_created_at = None
                metrics.last_accessed_at = None

            logger.info(
                f"ServiceFactory [{self._factory_id}] cleared {cleared_count} cache entries and reset metrics"
            )

    def force_cleanup(self) -> int:
        """Force cleanup of expired cache entries."""
        with self._lock:
            expired_count = 0
            now = time()
            expired_keys = []

            for key, entry in self._cache.items():
                if now - entry.created_at >= self._cache_ttl:
                    expired_keys.append(key)
                    expired_count += 1

            for key in expired_keys:
                del self._cache[key]

            self._last_cleanup = now

            if expired_count > 0:
                logger.info(
                    f"ServiceFactory [{self._factory_id}] force cleanup removed {expired_count} expired entries"
                )

            return expired_count

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the service factory.

        Returns:
            Dictionary with health status information
        """
        with self._lock:
            now = time()
            health = "healthy"
            issues = []

            # Check for potential issues
            if len(self._cache) > 1000:
                issues.append("High cache entry count")
                health = "warning"

            if now - self._last_cleanup > self._cleanup_interval * 2:
                issues.append("Cleanup overdue")
                health = "warning"

            # Check service creation rates
            for service_type, metrics in self._metrics.items():
                if metrics.avg_creation_time_ms > 100:  # > 100ms average
                    issues.append(f"Slow creation for {service_type}")
                    health = "warning"

            return {
                "factory_id": self._factory_id,
                "status": health,
                "issues": issues,
                "cache_size": len(self._cache),
                "last_cleanup_age_seconds": now - self._last_cleanup,
                "uptime_seconds": now
                - self._last_cleanup,  # Approximate since we don't track factory start time
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }


# Application-level service factory instance (initialized in app.py)
_service_factory: Optional[ServiceFactory] = None


def get_service_factory() -> ServiceFactory:
    """Get the application-level service factory instance."""
    if _service_factory is None:
        raise RuntimeError(
            "Service factory not initialized. This should be initialized during application startup."
        )
    return _service_factory


def set_service_factory(factory: ServiceFactory):
    """Set the application-level service factory instance (called from app.py)."""
    global _service_factory
    _service_factory = factory


# FastAPI dependency functions for Phase 2 implementation
def get_node_service_via_factory(db: Session) -> NodeService:
    """
    FastAPI dependency for NodeService using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        NodeService instance
    """
    factory = get_service_factory()
    return factory.create_node_service(db)


def get_node_link_service_via_factory(db: Session) -> NodeLinkService:
    """
    FastAPI dependency for NodeLinkService using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        NodeLinkService instance
    """
    factory = get_service_factory()
    return factory.create_node_link_service(db)


def get_graph_service_via_factory(db: Session) -> GraphService:
    """
    FastAPI dependency for GraphService using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        GraphService instance
    """
    factory = get_service_factory()
    return factory.create_graph_service(db)


def get_llm_service_via_factory(
    model_name: str = "gpt-3.5-turbo", temperature: float = 0
) -> LLMService:
    """
    FastAPI dependency for LLMService using optimized service factory.

    Args:
        model_name: LLM model name
        temperature: Temperature setting for the model

    Returns:
        LLMService instance
    """
    factory = get_service_factory()
    return factory.create_llm_service(model_name, temperature)


def get_reference_service_via_factory() -> ReferenceService:
    """
    FastAPI dependency for ReferenceService using optimized service factory.

    Returns:
        ReferenceService instance
    """
    factory = get_service_factory()
    return factory.create_reference_service()


# Change Management Service Dependencies
def get_version_manager_via_factory(db: Session = Depends(get_db)) -> VersionManager:
    """
    FastAPI dependency for VersionManager using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        VersionManager instance
    """
    factory = get_service_factory()
    return factory.create_version_manager(db)


def get_working_tree_manager_via_factory(
    db: Session = Depends(get_db),
) -> WorkingTreeManager:
    """
    FastAPI dependency for WorkingTreeManager using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        WorkingTreeManager instance
    """
    factory = get_service_factory()
    return factory.create_working_tree_manager(db)


def get_diff_generator_via_factory(db: Session = Depends(get_db)) -> DiffGenerator:
    """
    FastAPI dependency for DiffGenerator using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        DiffGenerator instance
    """
    factory = get_service_factory()
    return factory.create_diff_generator(db)


# Phase 4 Advanced Features Service Dependencies


def get_conflict_resolution_engine_via_factory(
    db: Session = Depends(get_db),
) -> ConflictResolutionEngine:
    """
    FastAPI dependency for ConflictResolutionEngine using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        ConflictResolutionEngine instance
    """
    factory = get_service_factory()
    return factory.create_conflict_resolution_engine(db)


def get_duckdb_service_via_factory() -> DuckDBService:
    """
    FastAPI dependency for DuckDBService using optimized service factory.

    Returns:
        DuckDBService instance
    """
    factory = get_service_factory()
    return factory.create_duckdb_service()


def get_change_analytics_engine_via_factory() -> ChangeAnalyticsEngine:
    """
    FastAPI dependency for ChangeAnalyticsEngine using optimized service factory.

    Returns:
        ChangeAnalyticsEngine instance
    """
    factory = get_service_factory()
    return factory.create_change_analytics_engine()


def get_incremental_sync_engine_via_factory(
    db: Session = Depends(get_db),
) -> IncrementalSyncEngine:
    """
    FastAPI dependency for IncrementalSyncEngine using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        IncrementalSyncEngine instance
    """
    factory = get_service_factory()
    return factory.create_incremental_sync_engine(db)


# Phase 5 Optimization Service Dependencies


def get_duckdb_query_analyzer_via_factory() -> DuckDBQueryAnalyzer:
    """
    FastAPI dependency for DuckDBQueryAnalyzer using optimized service factory.

    Returns:
        DuckDBQueryAnalyzer instance
    """
    factory = get_service_factory()
    return factory.create_duckdb_query_analyzer()


def get_s3_storage_manager_via_factory() -> S3StorageManager:
    """
    FastAPI dependency for S3StorageManager using optimized service factory.

    Returns:
        S3StorageManager instance
    """
    factory = get_service_factory()
    return factory.create_s3_storage_manager()


def get_hierarchical_diff_engine_via_factory(
    db: Session = Depends(get_db),
) -> HierarchicalDiffEngine:
    """
    FastAPI dependency for HierarchicalDiffEngine using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        HierarchicalDiffEngine instance
    """
    factory = get_service_factory()
    return factory.create_hierarchical_diff_engine(db)


def get_batch_operation_processor_via_factory(
    db: Session = Depends(get_db),
) -> BatchOperationProcessor:
    """
    FastAPI dependency for BatchOperationProcessor using optimized service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        BatchOperationProcessor instance
    """
    factory = get_service_factory()
    return factory.create_batch_operation_processor(db)


def get_performance_monitor_via_factory() -> PerformanceMonitor:
    """
    FastAPI dependency for PerformanceMonitor using optimized service factory.

    Returns:
        PerformanceMonitor instance
    """
    factory = get_service_factory()
    return factory.create_performance_monitor()
