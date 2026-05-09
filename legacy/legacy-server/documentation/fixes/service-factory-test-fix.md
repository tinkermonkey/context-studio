# Service Factory Test Failure Fix

## Issue Summary

Integration tests were failing with the error:
```
RuntimeError: Service factory not initialized. This should be initialized during application startup.
```

## Root Cause

The issue was introduced in commit `49fad505dd1ada37c7df850ecd16561b8ddea873` (Oct 15, 2025) as part of issue #149.

### What Happened

1. **The Change**: The `client` fixture in `tests/integration_tests/conftest.py` was renamed to `minimal_reference_client`
2. **The Problem**: During this rename, a cleanup line was added:
   ```python
   set_service_factory(None)
   ```
3. **The Impact**: This cleanup polluted the global service factory state, causing subsequent tests that use the regular `client` fixture (from `tests/conftest.py`) to fail

### Why It Failed

The service factory is a module-level singleton stored in `services/service_factory.py`:

```python
_service_factory: Optional[ServiceFactory] = None

def get_service_factory() -> ServiceFactory:
    if _service_factory is None:
        raise RuntimeError(
            "Service factory not initialized..."
        )
    return _service_factory
```

When tests run in a session:
1. Session-scoped `test_service_factory` fixture sets the factory
2. `shared_client` fixture creates an app that also sets the factory via lifespan
3. BUT if `minimal_reference_client` runs and sets factory to `None`, it breaks all subsequent tests
4. Other tests making API requests would fail because dependency injection functions call `get_service_factory()`

### Why This Design

The change was likely made with good intentions - to clean up test state. However:
- Setting to `None` breaks the session-scoped factory
- Other tests in the same session depend on the factory being available
- The cleanup was too aggressive

## The Fix

Changed the cleanup in `minimal_reference_client` to restore the original factory instead of setting to `None`:

```python
# Save the current service factory to restore it later
try:
    original_factory = get_service_factory()
except RuntimeError:
    original_factory = None

# ... test code ...

# Restore the original service factory instead of setting to None
set_service_factory(original_factory)
```

### Why This Works

1. **Preserves Session State**: If a session-level factory exists, it's restored
2. **Handles No Factory**: If there was no factory originally, we restore `None`
3. **Test Isolation**: The fixture still cleans up its own factory
4. **No Side Effects**: Other tests continue to work with their expected factory

## Lessons Learned

1. **Global State is Tricky**: Fixtures that modify global state need to be careful about cleanup
2. **Session vs Function Scope**: Understand the interaction between different fixture scopes
3. **Always Restore, Never Destroy**: When modifying global state, restore the original value rather than clearing it
4. **Test in Context**: Changes to test fixtures should be tested with the full test suite, not in isolation

## Related Code

- **Service Factory Module**: `services/service_factory.py` (lines 1103-1118)
- **Main Conftest**: `tests/conftest.py` (session-scoped `test_service_factory` fixture)
- **Integration Conftest**: `tests/integration_tests/conftest.py` (`minimal_reference_client` fixture)
- **App Initialization**: `app.py` (lifespan context manager sets factory on startup)

## Testing

After this fix, all integration tests should pass. The fix:
- ✅ Preserves test isolation
- ✅ Maintains session-level factory availability
- ✅ Properly cleans up per-fixture state
- ✅ Doesn't break other tests

## Prevention

To prevent similar issues in the future:

1. **Code Review**: Changes to test fixtures that modify global state should be carefully reviewed
2. **Test Ordering**: Run full test suites, not just individual test files
3. **Documentation**: Document when fixtures modify global state
4. **Pattern**: Use the "save and restore" pattern for global state modifications
