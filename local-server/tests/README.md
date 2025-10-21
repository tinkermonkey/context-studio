# Context Studio Tests

This directory contains the test suite for the Context Studio back-end.

## Test Structure

```
tests/
├── conftest.py                 # pytest configuration and shared fixtures
├── unit_tests/                 # Fast unit tests for individual components
├── integration_tests/          # Integration tests for API endpoints and workflows
└── performance_tests/          # Performance and load tests
```

## Running Tests

**IMPORTANT**: Always run tests with the virtual environment activated to ensure all dependencies are available.

### Using the Test Runner Script (Recommended)

The easiest way to run tests is using the provided test runner script:

```bash
# Run all tests
./run_tests.sh

# Run specific test file
./run_tests.sh tests/integration_tests/test_config_phase2_integration.py

# Run specific test
./run_tests.sh tests/integration_tests/test_config_phase2_integration.py::TestFreshInstallationScenarios::test_fresh_install_creates_databases_successfully

# Run with additional pytest options
./run_tests.sh -v -s tests/unit_tests/
```

### Manual Test Execution

If you prefer to run tests manually:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
python -m pytest tests/

# Run specific test category
python -m pytest tests/unit_tests/
python -m pytest tests/integration_tests/
python -m pytest tests/performance_tests/

# Run with specific markers
python -m pytest -m unit          # Only unit tests
python -m pytest -m integration   # Only integration tests
python -m pytest -m "not slow"    # Exclude slow tests
```

## Common Issues

### "ModuleNotFoundError" or Import Errors

**Problem**: Tests fail with import errors like `ModuleNotFoundError: No module named 'aiohttp'` or `ModuleNotFoundError: No module named 'sqlalchemy'`.

**Cause**: Tests are being run without the virtual environment activated.

**Solution**: Always use the `./run_tests.sh` script or manually activate the virtual environment before running tests:
```bash
source .venv/bin/activate
python -m pytest tests/
```

### "unable to open database file" Error

**Problem**: Tests fail with `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file`.

**Cause**: This is usually a symptom of missing dependencies (the actual error occurs earlier during import).

**Solution**: Use the test runner script or activate the virtual environment as described above.

## Test Categories

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Fast unit tests (< 1s)
- `@pytest.mark.integration` - Integration tests (may be slower)
- `@pytest.mark.performance` - Performance benchmarks
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.asyncio` - Asynchronous tests

## Writing Tests

When writing new tests:

1. Add appropriate markers to categorize your tests
2. Use fixtures from `conftest.py` for common setup
3. Place tests in the appropriate directory (unit/integration/performance)
4. Follow the naming convention: `test_*.py` for files, `test_*` for functions
5. Include the path setup in integration tests:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent.parent.parent))
   ```

## Configuration

Test configuration is in `pytest.ini` at the project root. This includes:
- Test discovery patterns
- Markers definitions
- Warning filters
- Default options
