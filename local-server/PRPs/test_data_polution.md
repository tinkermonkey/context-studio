# Test Data Pollution Problem

This application uses multiple sqlite database files and a config file, and since it's under active development, I'm running into the problem that my local files are frequently being polluted with test artifacts:

- Testing the configuration APIs changes the configuration in my `config.json` file so when I launch the server to test the ux, it's configured wrong
- Testing the APIs inserts data into the active dataset which is loaded by default, or the separate pipeline definition database

## Root Cause Analysis

After examining the codebase, the pollution manifests due to several architectural patterns:

### Configuration Pollution Sources
1. **Global Configuration Manager**: The `ConfigurationManager` in `config.py` uses a singleton pattern with persistent file storage
2. **Configuration API**: The `/api/config` endpoints directly modify the shared `config.json` file via `config_manager.set()` and `config_manager.save()`
3. **No Test Isolation**: Tests calling configuration APIs write directly to the production config file
4. **Shared State**: The global `_config_manager` instance persists configuration changes across test runs

### Database Pollution Sources
1. **Dataset Manager**: The `DatasetManager` manages multiple database connections, with the "default" dataset often pointing to production files
2. **Shared Database URLs**: Without explicit test configuration, database URLs point to production files (`local.db`, `schemaorg.db`, etc.)
3. **Connection Pooling**: The `DatabaseManager` maintains persistent connections that can leak data between tests
4. **Migration State**: Tests that trigger migrations may modify schema in production databases

## Current Test Infrastructure Analysis

The codebase has good test isolation patterns in `conftest.py`:
- ✅ Uses temporary databases (`tempfile.NamedTemporaryFile`)
- ✅ Applies migrations to test databases
- ✅ Clears data between tests via table deletion
- ✅ Uses session-scoped shared app for performance
- ✅ Auto-cleanup of temporary files

However, there are gaps:
- ❌ Configuration tests still modify production `config.json`
- ❌ Some integration tests may bypass the isolated test setup
- ❌ No configuration isolation mechanism

## Common Patterns for Test Isolation

### 1. Environment Variable Overrides
```python
# Set test-specific config file path
os.environ['CONFIG_FILE'] = '/tmp/test_config.json'
```

### 2. Dependency Injection with Test Doubles
```python
# Override config manager in tests
@pytest.fixture
def test_config_manager():
    return MockConfigManager()

# Use dependency injection
def get_config_manager_dependency():
    return get_config_manager()
```

### 3. Temporary Configuration Files
```python
@pytest.fixture
def test_config_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(default_config, f)
        yield f.name
    os.unlink(f.name)
```

### 4. Context Managers for Resource Isolation
```python
@contextmanager
def isolated_config():
    original_manager = config._config_manager
    try:
        config._config_manager = TestConfigManager()
        yield config._config_manager
    finally:
        config._config_manager = original_manager
```

### 5. Database URL Environment Overrides
```python
# Force test database URLs
os.environ['DATABASE_URL'] = 'sqlite:///test.db'
os.environ['SCHEMA_ORG_DB_PATH'] = 'test_schema.db'
```

## Recommended Solution Path

### Phase 1: Configuration Isolation (High Priority)
1. **Add Configuration File Override Support**
   - Modify `ConfigurationManager.__init__()` to accept config file path
   - Support `CONFIG_FILE` environment variable
   - Update all tests to use temporary config files

2. **Create Test Configuration Fixture**
   ```python
   @pytest.fixture(scope="function")
   def test_config_manager():
       with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
           json.dump(Settings().model_dump(), f)
           f.flush()
           yield ConfigurationManager(f.name)
   ```

3. **Override Global Config Manager in Tests**
   - Use dependency injection or monkey patching
   - Ensure all API tests use isolated config

### Phase 2: Enhanced Database Isolation (Medium Priority)
1. **Improve Database URL Validation**
   - Add checks to prevent production database access in tests
   - Use test-specific database naming patterns

2. **Enhanced Cleanup**
   - Add cleanup fixtures for any remaining global state
   - Implement better teardown for connection pools

### Phase 3: CI/CD Integration (Low Priority)
1. **Test Environment Detection**
   - Auto-detect test runs and force isolation
   - Add warnings for production file access during tests

2. **Performance Optimization**
   - Consider in-memory databases for unit tests
   - Optimize shared fixtures for integration tests

## Implementation Priority

1. **Immediate (Next Sprint)**:
   - Configuration isolation fixtures
   - Environment variable support in ConfigurationManager
   - Update configuration API tests

2. **Short Term (1-2 Sprints)**:
   - Enhanced database isolation
   - Production access prevention
   - Documentation updates

3. **Long Term (Future)**:
   - Performance optimizations
   - Advanced test infrastructure
   - Monitoring for pollution detection

## Files That Need Modification

1. `config.py` - Add config file path parameter support
2. `tests/conftest.py` - Add configuration isolation fixtures  
3. `api/config.py` - Support dependency injection for config manager
4. Individual test files - Update to use isolated configuration
5. `database/utils.py` - Add production access guards

This solution maintains the existing good test patterns while addressing the specific pollution issues identified.

## Developer Testing Guidelines

### ⚠️ Current Issue
Configuration API tests modify the production `config.json` file, polluting the development environment.

### Safe Testing
```bash
# Safe - use isolated databases
pytest tests/unit_tests/
pytest tests/integration_tests/test_terms_integration.py

# Risky - modifies config.json
pytest tests/unit_tests/test_configuration_notifications.py
```

### Quick Recovery
```bash
# Backup before risky tests
cp config.json config.json.backup

# Restore after tests
cp config.json.backup config.json
# OR reset via API
curl -X POST http://localhost:8001/api/config/reset

# Nuclear option if corrupted
git checkout config.json && rm -f *.db
```

### What's Safe vs Risky
- ✅ **Safe**: Unit tests, database integration tests, read-only API tests
- ❌ **Avoid**: Configuration API tests, tests calling `/api/config/` endpoints

**Rule of thumb**: If testing configuration features, backup `config.json` first.