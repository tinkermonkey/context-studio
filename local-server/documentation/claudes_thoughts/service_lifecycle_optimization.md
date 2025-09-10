# Service Lifecycle Optimization Patterns

This document outlines three design patterns for optimizing service lifecycle management and database connections in the Context Studio FastAPI application.

## Current Issues

The existing implementation has several performance and scalability issues:

1. **Per-Request Service Creation**: Each API request creates new service instances (NodeService, NodeLinkService)
2. **Inefficient Resource Usage**: Services and database sessions are created and destroyed for every request
3. **No Caching**: Repeated initialization overhead with no reuse of stateless operations
4. **Connection Management**: Uses NullPool which creates new connections per request

## Recommended Patterns

### Pattern 1: Service Registry (Recommended for Production)

**Best for**: Production environments with moderate to high load

**Implementation**: `services/service_registry.py` + `api/dependencies/structure_nodes_optimized.py`

```python
# Usage in API endpoints
from api.dependencies.structure_nodes_optimized import get_node_service

@router.post("/")
def create_node(
    structure_node: NodeCreate,
    node_service: NodeService = Depends(get_node_service)  # Optimized via registry
):
    # Service instance creation is optimized while maintaining per-request DB sessions
    pass
```

**Benefits**:
- Thread-safe singleton service management
- Maintains proper per-request database session isolation
- Reduces service instantiation overhead
- Simple to implement and maintain
- Compatible with existing service interfaces

**Trade-offs**:
- Services must remain stateless
- Minimal memory savings (mainly reduces object creation overhead)

### Pattern 2: Service Factory with Caching

**Best for**: Development environments or applications with complex service initialization

**Implementation**: `services/service_factory.py`

```python
# Usage with caching and metrics
from services.service_factory import get_node_service_via_factory

@router.post("/")
def create_node(
    structure_node: NodeCreate,
    node_service: NodeService = Depends(get_node_service_via_factory)  # Via factory
):
    # Service creation with intelligent caching and monitoring
    pass

# Monitor cache performance
factory = get_service_factory()
stats = factory.get_cache_stats()
print(f"Service cache stats: {stats}")
```

**Benefits**:
- Intelligent caching with TTL
- Cache performance monitoring
- Automatic cleanup of expired entries
- Thread-safe operations
- Extensible for complex service initialization patterns

**Trade-offs**:
- More complex than registry pattern
- Additional memory overhead for cache metadata
- May be overkill for simple services

### Pattern 3: Enhanced Database Manager with Service Context

**Best for**: Applications requiring optimized connection pooling and coordinated service-database operations

**Implementation**: `database/enhanced_utils.py`

```python
# Usage with enhanced pooling and service contexts
from database.enhanced_utils import get_enhanced_db, get_enhanced_db_with_service

@router.post("/")
def create_node(
    structure_node: NodeCreate,
    db: Session = Depends(get_enhanced_db)  # Enhanced pooling
):
    # Use service with optimized database connection
    node_service = NodeService(db)
    pass

# Or use coordinated service context
@router.post("/complex-operation")
def complex_operation():
    manager = get_enhanced_db_manager()
    with manager.get_service_context(NodeService) as (db, service):
        # Coordinated database and service lifecycle
        pass
```

**Benefits**:
- Optimized connection pooling (QueuePool vs NullPool)
- Service-database lifecycle coordination
- Connection pool monitoring
- Context managers for complex operations
- Better resource utilization

**Trade-offs**:
- More complex database configuration
- Requires careful testing with SQLite threading
- Larger change to existing architecture

## Implementation Recommendations

### Phase 1: Immediate Improvement (Service Registry)
Replace the current dependencies with the optimized service registry pattern:

```python
# Update api/dependencies/structure_nodes.py
from services.service_registry import get_service_registry

def get_node_service(db: Session = Depends(get_db)) -> NodeService:
    registry = get_service_registry()
    return registry.get_node_service(db)
```

### Phase 2: Enhanced Monitoring (Service Factory)
For applications requiring performance monitoring:

```python
# Add cache monitoring endpoint
@router.get("/admin/service-stats")
def get_service_stats():
    factory = get_service_factory()
    return factory.get_cache_stats()
```

### Phase 3: Full Optimization (Enhanced Database Manager)
For high-performance requirements:

```python
# Update app.py initialization
from database.enhanced_utils import get_enhanced_db_manager

# In lifespan context
manager = get_enhanced_db_manager()
app.state.db_manager = manager

# Monitor connection pool
pool_stats = manager.get_connection_pool_status()
```

## Performance Impact Estimates

| Pattern | Service Creation Overhead | Memory Usage | Complexity | Compatibility |
|---------|---------------------------|--------------|------------|---------------|
| Current | High (per-request) | High | Low | N/A |
| Registry | Low (singleton classes) | Medium | Low | High |
| Factory | Low (with caching) | Medium+ | Medium | High |
| Enhanced | Low (with pooling) | Low | High | Medium |

## Migration Path

1. **Start with Service Registry** - Drop-in replacement with immediate benefits
2. **Add monitoring** - Service Factory for performance insights
3. **Optimize connections** - Enhanced Database Manager for high-load scenarios

Each pattern is designed to be incrementally adoptable without breaking existing functionality.
