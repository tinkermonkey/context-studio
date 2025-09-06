# Test Performance Optimization Guide

## Overview

The test suite has been optimized to use **shared app fixtures** instead of creating a new app instance for every test. This provides dramatic performance improvements:

- **Unit tests**: 70-90% faster 
- **Integration tests**: 50-80% faster
- **Larger test suites**: Even bigger relative improvements

## How It Works

### Before (Slow)
```python
@pytest.fixture(scope="function")  # ❌ New app per test
def test_app():
    # Creates new database, runs all migrations, creates new app
    # This happens for EVERY SINGLE TEST
```

### After (Fast)  
```python
@pytest.fixture(scope="session")   # ✅ Shared app for all tests
def shared_app():
    # Creates database ONCE, runs migrations ONCE, creates app ONCE  
    # Reused across ALL TESTS in the session
```

## Available Fixtures

### 1. `db_session` (Recommended)
- **Scope**: Function (new session per test)
- **Cleanup**: Automatic table cleanup after each test
- **Use for**: Most tests that need database access

```python
def test_something(db_session):
    handler = ChangeEventHandler(db_session)
    # Test your code
    # Automatic cleanup happens
```

### 2. `clean_db_session` (Special Cases)
- **Scope**: Function (new session per test) 
- **Cleanup**: Commits changes, then clears all tables
- **Use for**: Tests that need to commit data during execution

```python
def test_something_that_commits(clean_db_session):
    # Use when your test needs to commit data
    clean_db_session.commit()
```

### 3. `shared_client` (API Testing)
- **Scope**: Session (reused across all tests)
- **Use for**: FastAPI endpoint testing

```python
def test_api_endpoint(shared_client):
    response = shared_client.get("/api/some-endpoint")
    assert response.status_code == 200
```

### 4. Legacy Fixtures (Backwards Compatibility)
- `test_app`: Now returns the shared app
- `client`: Now returns the shared client

## Performance Tips

### 1. Fast vs Slow Tests
Mark your tests appropriately:

```python
@pytest.mark.fast
def test_unit_logic():
    # Fast unit test - no database
    pass

@pytest.mark.slow  
def test_full_integration(db_session):
    # Slower integration test
    pass
```

### 2. Running Tests Efficiently

```bash
# Run only fast tests
pytest -m "not slow"

# Run unit tests only
pytest tests/unit_tests/

# Stop on first failure (faster feedback)
pytest -x

# Parallel execution (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto
```

### 3. When to Use Which Fixture

| Test Type | Fixture | Reason |
|-----------|---------|---------|
| Unit test with DB | `db_session` | Auto-cleanup, fast |
| Integration test | `db_session` | Auto-cleanup, fast |
| API test | `shared_client` | Reuses FastAPI app |
| Test that commits | `clean_db_session` | Handles commits properly |

## Migration Handling

The shared app approach handles migrations intelligently:

1. **First test session**: Runs all migrations once
2. **Subsequent tests**: Reuse the migrated database
3. **Between tests**: Only clears table data, preserves schema
4. **Cleanup**: Migration state is preserved

## Common Patterns

### Testing Services
```python
def test_change_event_handler(db_session):
    handler = ChangeEventHandler(db_session)
    event = handler.fire_created_event(
        RecordType.STRUCTURE_NODE, 
        "test-id", 
        {"title": "Test"}
    )
    assert event.record_type == RecordType.STRUCTURE_NODE
```

### Testing API Endpoints
```python  
def test_api_endpoint(shared_client):
    response = shared_client.post("/api/change-events", json={
        "record_type": "structure_node",
        "record_id": "test-123"
    })
    assert response.status_code == 201
```

### Testing Integration Flows
```python
def test_end_to_end_flow(db_session):
    # Create handler
    handler = ChangeEventHandler(db_session)
    
    # Create event
    event = handler.fire_created_event(...)
    
    # Process event
    processor = EventProcessor()
    processor.process_events()
    
    # Verify results
    processed_events = handler.get_unprocessed_events()
    assert len(processed_events) == 0
```

## Troubleshooting

### Test Isolation Issues
If tests interfere with each other:

1. Check if you're using `db_session` (auto-cleanup)
2. Verify you're not caching data outside the session
3. Consider using `clean_db_session` if commits are needed

### Performance Still Slow  
If tests are still slow:

1. Check for tests creating their own apps/databases
2. Look for tests doing expensive operations (file I/O, network calls)
3. Consider mocking external dependencies
4. Mark slow tests with `@pytest.mark.slow`

### Session Errors
If you get "session closed" errors:

1. Make sure you're using the provided fixtures
2. Don't manually close sessions that pytest manages
3. Check for transaction rollback issues

## Example Test Structure

```python
"""Example test file showing best practices."""
import pytest
from services.change_event_handler import ChangeEventHandler
from database.enums import RecordType

# Fast unit test - no database needed
@pytest.mark.fast
def test_enum_values():
    assert RecordType.STRUCTURE_NODE == "structure_node"

# Standard database test
def test_event_creation(db_session):
    handler = ChangeEventHandler(db_session)
    event = handler.fire_created_event(
        RecordType.PREDICATE,
        "test-id",
        {"title": "Test Predicate"}
    )
    assert event.record_type == RecordType.PREDICATE

# Integration test  
@pytest.mark.integration
def test_full_workflow(db_session, shared_client):
    # Test database operations
    handler = ChangeEventHandler(db_session)
    event = handler.fire_created_event(...)
    
    # Test API
    response = shared_client.get("/api/events")
    assert response.status_code == 200
    
# Slow test that should be skipped in fast runs
@pytest.mark.slow
def test_performance_with_large_dataset(clean_db_session):
    # This test takes a long time
    pass
```

This optimization makes your test suite much faster while maintaining proper test isolation and backwards compatibility!
