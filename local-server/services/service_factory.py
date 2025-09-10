"""
Service Factory - Production-ready service creation and caching

This module implements a sophisticated service factory pattern with intelligent caching,
performance monitoring, and lifecycle management for better resource utilization.
"""

import uuid
from typing import Dict, Any, Optional, TypeVar, Type, Callable, List
from threading import Lock, RLock
from time import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from dataclasses import dataclass, field
from enum import Enum
from fastapi import Depends

from services.node_service import NodeService
from services.node_link_service import NodeLinkService
from services.version_manager import VersionManager
from services.working_tree_manager import WorkingTreeManager
from services.diff_generator import DiffGenerator
from graph.graph_service import GraphService
from graph.network_service import NetworkService
from graph.sparql_service import SPARQLService
from llm.flavor_service import PipelineFlavorService
from llm.service import LLMService
from enrichment.service import EnrichmentService
from schema_org.service import SchemaOrgService
from database.utils import get_db
from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class ServiceType(Enum):
    """Enumeration of supported service types."""
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
    ENRICHMENT_SERVICE = "enrichment_service"
    SCHEMA_ORG_SERVICE = "schema_org_service"


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
            
        logger.info(f"ServiceFactory [{self._factory_id}] initialized with {cache_ttl_seconds}s TTL")
    
    def create_node_service(self, db: Session, graph_service: Optional[GraphService] = None) -> NodeService:
        """
        Create NodeService with optimized instantiation.
        
        Args:
            db: Database session for this request
            graph_service: Optional graph service dependency
            
        Returns:
            NodeService instance
        """
        return self._create_service(ServiceType.NODE_SERVICE, NodeService, db, graph_service)
    
    def create_node_link_service(self, db: Session) -> NodeLinkService:
        """
        Create NodeLinkService with optimized instantiation.
        
        Args:
            db: Database session for this request
            
        Returns:
            NodeLinkService instance
        """
        return self._create_service(ServiceType.NODE_LINK_SERVICE, NodeLinkService, db)
    
    def create_version_manager(self, db: Session) -> VersionManager:
        """
        Create VersionManager with optimized instantiation.
        
        Args:
            db: Database session for this request
            
        Returns:
            VersionManager instance
        """
        return self._create_service(ServiceType.VERSION_MANAGER, VersionManager, db)
    
    def create_working_tree_manager(self, db: Session, version_manager: Optional[VersionManager] = None) -> WorkingTreeManager:
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
        
        return self._create_service(ServiceType.WORKING_TREE_MANAGER, WorkingTreeManager, db, version_manager)
    
    def create_diff_generator(self, db: Session, version_manager: Optional[VersionManager] = None,
                             working_tree_manager: Optional[WorkingTreeManager] = None) -> DiffGenerator:
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
        
        return self._create_service(ServiceType.DIFF_GENERATOR, DiffGenerator, version_manager, working_tree_manager)
    
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
        return self._create_service(ServiceType.PIPELINE_FLAVOR_SERVICE, PipelineFlavorService)
    
    def create_llm_service(self, model_name: str = "gpt-3.5-turbo", temperature: float = 0) -> LLMService:
        """
        Create LLMService with optimized instantiation.
        
        Args:
            model_name: LLM model name
            temperature: Temperature setting for the model
            
        Returns:
            LLMService instance
        """
        service_key = f"{ServiceType.LLM_SERVICE.value}_{model_name}_{temperature}"
        return self._create_service_with_key(service_key, ServiceType.LLM_SERVICE, LLMService, model_name, temperature)
    
    def create_enrichment_service(self) -> EnrichmentService:
        """
        Create EnrichmentService with optimized instantiation.
        
        Returns:
            EnrichmentService instance
        """
        return self._create_service(ServiceType.ENRICHMENT_SERVICE, EnrichmentService)
    
    def create_schema_org_service(self) -> SchemaOrgService:
        """
        Create SchemaOrgService with optimized instantiation.
        
        Returns:
            SchemaOrgService instance
        """
        return self._create_service(ServiceType.SCHEMA_ORG_SERVICE, SchemaOrgService)
    
    def _create_service(self, service_type: ServiceType, service_class: Type[T], *args, **kwargs) -> T:
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
        return self._create_service_with_key(service_type.value, service_type, service_class, *args, **kwargs)
    
    def _create_service_with_key(self, service_key: str, service_type: ServiceType, service_class: Type[T], *args, **kwargs) -> T:
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
        start_time = time()
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
                    
                    logger.debug(f"Cache HIT for {service_key} (access #{entry.access_count}, age: {entry.age_seconds:.1f}s)")
                    return instance
                else:
                    # Cache expired
                    logger.debug(f"Cache EXPIRED for {service_key} (age: {entry.age_seconds:.1f}s)")
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
                creation_time_ms=creation_time_ms
            )
            
            self._cache[service_key] = entry
            metrics.record_creation(creation_time_ms)
            
            logger.debug(f"Cache MISS for {service_key} - created new entry (creation: {creation_time_ms:.2f}ms)")
            
            return instance
    
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
            logger.info(f"ServiceFactory [{self._factory_id}] cleaned up {len(expired_keys)} expired cache entries")
    
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
                    'access_count': entry.access_count,
                    'created_at': datetime.fromtimestamp(entry.created_at, timezone.utc).isoformat(),
                    'last_accessed': datetime.fromtimestamp(entry.last_accessed, timezone.utc).isoformat(),
                    'age_seconds': entry.age_seconds,
                    'creation_time_ms': entry.creation_time_ms
                }
            
            service_metrics = {}
            for service_type, metrics in self._metrics.items():
                service_metrics[service_type] = {
                    'total_created': metrics.total_created,
                    'cache_hits': metrics.total_cache_hits,
                    'cache_misses': metrics.total_cache_misses,
                    'cache_hit_rate_percent': metrics.cache_hit_rate,
                    'avg_creation_time_ms': metrics.avg_creation_time_ms,
                    'last_created_at': metrics.last_created_at.isoformat() if metrics.last_created_at else None,
                    'last_accessed_at': metrics.last_accessed_at.isoformat() if metrics.last_accessed_at else None
                }
            
            return {
                'factory_id': self._factory_id,
                'cache_ttl_seconds': self._cache_ttl,
                'cleanup_interval_seconds': self._cleanup_interval,
                'total_cache_entries': len(self._cache),
                'last_cleanup': datetime.fromtimestamp(self._last_cleanup, timezone.utc).isoformat(),
                'cache_entries': cache_info,
                'service_metrics': service_metrics,
                'generated_at': datetime.now(timezone.utc).isoformat()
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
            
            overall_hit_rate = (total_hits / (total_hits + total_misses)) * 100.0 if (total_hits + total_misses) > 0 else 0.0
            
            # Find best and worst performing services
            best_hit_rate = max(self._metrics.values(), key=lambda m: m.cache_hit_rate, default=None)
            worst_hit_rate = min(self._metrics.values(), key=lambda m: m.cache_hit_rate, default=None)
            
            return {
                'factory_id': self._factory_id,
                'overall_cache_hit_rate_percent': overall_hit_rate,
                'total_services_created': total_created,
                'total_cache_entries': len(self._cache),
                'best_performing_service': {
                    'type': best_hit_rate.service_type if best_hit_rate else None,
                    'hit_rate_percent': best_hit_rate.cache_hit_rate if best_hit_rate else 0.0
                },
                'worst_performing_service': {
                    'type': worst_hit_rate.service_type if worst_hit_rate else None,
                    'hit_rate_percent': worst_hit_rate.cache_hit_rate if worst_hit_rate else 0.0
                },
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
    
    def clear_cache(self):
        """Clear the service cache and reset metrics."""
        with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            
            # Reset metrics
            for metrics in self._metrics.values():
                metrics.total_cache_hits = 0
                metrics.total_cache_misses = 0
            
            logger.info(f"ServiceFactory [{self._factory_id}] cleared {cleared_count} cache entries and reset metrics")
    
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
                logger.info(f"ServiceFactory [{self._factory_id}] force cleanup removed {expired_count} expired entries")
            
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
                'factory_id': self._factory_id,
                'status': health,
                'issues': issues,
                'cache_size': len(self._cache),
                'last_cleanup_age_seconds': now - self._last_cleanup,
                'uptime_seconds': now - self._last_cleanup,  # Approximate since we don't track factory start time
                'checked_at': datetime.now(timezone.utc).isoformat()
            }


# Application-level service factory instance (initialized in app.py)
_service_factory: Optional[ServiceFactory] = None


def get_service_factory() -> ServiceFactory:
    """Get the application-level service factory instance."""
    if _service_factory is None:
        raise RuntimeError("Service factory not initialized. This should be initialized during application startup.")
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
    model_name: str = "gpt-3.5-turbo",
    temperature: float = 0
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


def get_enrichment_service_via_factory() -> EnrichmentService:
    """
    FastAPI dependency for EnrichmentService using optimized service factory.
    
    Returns:
        EnrichmentService instance
    """
    factory = get_service_factory()
    return factory.create_enrichment_service()


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


def get_working_tree_manager_via_factory(db: Session = Depends(get_db)) -> WorkingTreeManager:
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
