# Service Factory and Database Manager Testing Migration Guide

This guide provides step-by-step instructions for migrating existing tests to work with the new service factory and database manager architecture.

## Overview of Changes

### What Changed
1. **Service Factory Pattern**: Services are now created through a `ServiceFactory` that provides caching and performance monitoring
2. **Enhanced Database Manager**: Database connections use an optimized `DatabaseManager` with connection pooling and health monitoring
3. **New Dependency Injection**: FastAPI endpoints now use factory-based dependency injection functions

### Why These Changes Matter for Testing
- **Service Caching**: Services may be cached between requests, affecting test isolation
- **Performance Metrics**: Service creation and database operations are now tracked
- **Resource Management**: More sophisticated cleanup is required
- **Connection Pooling**: Database connections are managed differently

## High Priority Migration Tasks

### ✅ 1. Updated `conftest.py` with New Fixtures

Added the following fixtures to support the new architecture:

```python
@pytest.fixture(scope="session")
def test_service_factory():
    """Test-optimized service factory with shorter TTL."""
    
@pytest.fixture(scope="session") 
def test_database_manager():
    """Managed database manager instance."""

@pytest.fixture(autouse=True, scope="function")
def reset_service_factory_cache(test_service_factory):
    """Auto-reset cache between tests for isolation."""

@pytest.fixture(scope="function")
def optimized_db_session(shared_app, test_database_manager):
    """Database session using DatabaseManager."""
```

### ✅ 2. Created Service Factory Unit Tests

Created comprehensive unit tests in `tests/unit_tests/test_service_factory.py`:
- Service creation and caching behavior
- Metrics accuracy and performance tracking
- Cache expiration and cleanup
- Thread safety
- Error handling
- Performance optimization

### ✅ 3. Created Database Manager Unit Tests

Created comprehensive unit tests in `tests/unit_tests/test_database_manager.py`:
- Connection pooling strategies (NullPool, StaticPool, QueuePool)
- Health monitoring and performance metrics
- Resource cleanup and lifecycle management
- Engine optimization and configuration
- Thread safety and concurrent operations

### ✅ 4. Updated Performance Tests

Modified `tests/performance_tests/test_scale_performance.py` to:
- Initialize performance-optimized service factory
- Reset service metrics for clean performance measurements
- Monitor service factory statistics during performance tests
- Include database manager integration

## Medium Priority Migration Tasks

### ✅ 5. Created Integration Test Templates

Created `tests/integration_tests/test_service_factory_integration.py` with:
- Templates for migrating existing integration tests
- Examples of service factory performance monitoring
- Database manager integration patterns
- Error handling with new architecture

### ✅ 6. Updated Sample Integration Test

Updated `tests/integration_tests/test_layers_integration.py` to demonstrate:
- Using `test_service_factory` fixture
- Monitoring service creation and caching
- Maintaining test isolation with automatic cache reset

## Migration Steps for Existing Tests

### Step 1: Update Test Imports and Fixtures

**Before:**
```python
def test_example(client, db_session):
    # Test code
```

**After:**
```python
def test_example(client, test_service_factory, optimized_db_session):
    # Service factory cache is auto-reset between tests
    baseline_stats = test_service_factory.get_cache_stats()
    
    # Test code
    
    # Optional: Monitor service usage
    final_stats = test_service_factory.get_cache_stats()
```

### Step 2: Update Direct Service Instantiation

**Before:**
```python
from services.node_service import NodeService
from graph.graph_service import GraphService

def test_service_logic(db_session):
    graph_service = GraphService(db_session)
    node_service = NodeService(db=db_session, graph_service=graph_service)
    result = node_service.create_layer(...)
```

**After:**
```python
def test_service_logic(optimized_db_session, test_service_factory):
    node_service = test_service_factory.create_node_service(optimized_db_session)
    result = node_service.create_layer(...)
```

### Step 3: Add Service Factory Monitoring (Optional)

For tests that want to verify performance benefits:

```python
def test_with_performance_monitoring(client, test_service_factory):
    # Record baseline
    baseline = test_service_factory.get_performance_summary()
    
    # Perform operations
    for i in range(5):
        response = client.post("/api/structure_nodes/", json=test_data)
        assert response.status_code == 201
    
    # Check performance
    final = test_service_factory.get_performance_summary()
    hit_rate = final["overall_cache_hit_rate_percent"]
    
    # Should have some caching after first operation
    assert hit_rate > 0
```

### Step 4: Update Mock Strategies

**Before:**
```python
@patch('services.node_service.NodeService')
def test_with_mocks(mock_service, client):
    mock_service.return_value.create_layer.return_value = mock_result
```

**After (Option 1: Mock at Factory Level):**
```python
@patch('services.service_factory.get_service_factory')
def test_with_factory_mock(mock_get_factory, client):
    mock_factory = Mock()
    mock_service = Mock()
    mock_factory.create_node_service.return_value = mock_service
    mock_service.create_layer.return_value = mock_result
    mock_get_factory.return_value = mock_factory
```

**After (Option 2: Mock Service Class - Recommended):**
```python
@patch.object(NodeService, 'create_layer')
def test_with_service_mock(mock_create, client):
    mock_create.return_value = mock_result
    # Factory creates real service instances, but methods are mocked
```

## Testing Patterns and Best Practices

### 1. Test Isolation with Service Factory

The `reset_service_factory_cache` fixture automatically ensures test isolation:

```python
def test_isolated_operation(client, test_service_factory):
    # Cache is automatically cleared before this test
    stats = test_service_factory.get_cache_stats()
    assert len(stats["cache_entries"]) == 0
    
    # Perform test operations
    # Cache will be cleared again after this test
```

### 2. Performance Testing with Service Factory

```python
def test_performance_benefits(client, test_service_factory):
    import time
    
    # Reset for clean measurement
    test_service_factory.clear_cache()
    
    start_time = time.time()
    
    # Perform multiple similar operations
    for i in range(10):
        response = client.post("/api/structure_nodes/", json=similar_data)
        assert response.status_code == 201
    
    end_time = time.time()
    
    # Check caching effectiveness
    stats = test_service_factory.get_performance_summary()
    hit_rate = stats["overall_cache_hit_rate_percent"]
    
    print(f"Operations took {end_time - start_time:.3f}s with {hit_rate:.1f}% cache hit rate")
    
    # Should have reasonable hit rate for similar operations
    assert hit_rate > 50
```

### 3. Database Manager Testing

```python
def test_with_database_manager(optimized_db_session, test_database_manager):
    # Session uses optimized database manager
    db = optimized_db_session
    
    # Perform database operations
    from sqlalchemy import text
    result = db.execute(text("SELECT COUNT(*) FROM structure_nodes")).scalar()
    
    # Check database manager health
    health = test_database_manager.perform_health_check()
    assert health["overall_status"] == "healthy"
    
    # Check performance metrics
    metrics = test_database_manager._get_metrics_summary()
    assert metrics["total_queries_executed"] > 0
```

### 4. Error Handling with New Architecture

```python
def test_error_handling_with_factory(client, test_service_factory):
    # Make request that should fail
    response = client.post("/api/structure_nodes/", json=invalid_data)
    assert response.status_code == 422
    
    # Service factory should still be functional after errors
    stats = test_service_factory.get_cache_stats()
    health = test_service_factory.get_health_status()
    
    assert health["status"] == "healthy"
    assert isinstance(stats, dict)
```

## Migration Checklist

### For Unit Tests:
- [ ] Update imports to include service factory fixtures
- [ ] Replace direct service instantiation with factory methods
- [ ] Add service factory monitoring where beneficial
- [ ] Update mocking strategies for factory pattern
- [ ] Test service caching behavior where relevant

### For Integration Tests:
- [ ] Add `test_service_factory` fixture to test parameters
- [ ] Use automatic cache reset for test isolation
- [ ] Monitor service factory performance in key tests
- [ ] Use `optimized_db_session` for direct database operations
- [ ] Update cleanup procedures for new resource management

### For Performance Tests:
- [ ] Initialize performance-optimized service factory
- [ ] Reset service metrics for clean measurements
- [ ] Monitor cache hit rates and service creation times
- [ ] Include database manager performance metrics
- [ ] Test with realistic service caching scenarios

## Troubleshooting Common Issues

### Issue 1: Tests Interfering with Each Other
**Symptom**: Tests pass individually but fail when run together
**Solution**: Ensure `test_service_factory` fixture is included and `reset_service_factory_cache` is working

### Issue 2: Service Factory Not Being Used
**Symptom**: Service factory cache remains empty during tests
**Solution**: Check that dependency injection is using factory-based functions, not direct instantiation

### Issue 3: Database Manager Connection Issues
**Symptom**: Database connection errors in tests
**Solution**: Use `optimized_db_session` fixture and ensure proper cleanup with `test_database_manager`

### Issue 4: Performance Tests Showing No Caching
**Symptom**: Cache hit rate remains 0% in performance tests
**Solution**: Ensure multiple similar operations and that cache TTL is longer than test duration

### Issue 5: Mock Strategies Not Working
**Symptom**: Mocks not being called or applied
**Solution**: Update mocking to work at service class level rather than factory level

## Next Steps

### Low Priority Tasks (Future Work):
1. **Service Factory Performance Benchmarking**: Create dedicated benchmarks for service factory performance
2. **Database Manager Health Monitoring Tests**: Add comprehensive health check testing
3. **Multi-threading Service Factory Tests**: Test factory behavior under concurrent access
4. **Service Factory Configuration Testing**: Test different cache TTL and cleanup interval settings
5. **Integration with CI/CD**: Add service factory metrics to continuous integration reports

### Monitoring and Maintenance:
- Monitor service factory cache hit rates in CI/CD pipelines
- Track database manager performance metrics over time
- Set up alerts for service factory health issues
- Regularly review and optimize service caching strategies

This migration guide ensures that your test suite takes full advantage of the new service factory and database manager architecture while maintaining reliability and performance.
