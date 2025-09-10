# Tasks to Complete When Finishing Development

## Code Quality Checks
1. **Linting**: Follow PEP 8 style guidelines - no specific linting command identified yet
2. **Type Checking**: No specific type checking command identified yet  
3. **Formatting**: No specific formatting command identified yet

## Testing
1. **Run Full Test Suite**: `pytest`
2. **Run Specific Test Categories**:
   - Unit tests: `pytest tests/unit_tests/`
   - Integration tests: `pytest tests/integration_tests/`
   - Performance tests: `pytest tests/performance_tests/`

## Database
1. **Schema Changes**: Create migration script using `python database/migrations/migration_manager.py`
2. **Test Database Operations**: Ensure all database operations work correctly

## Documentation
1. **Update API Documentation**: Update `documentation/api.md` if API changes were made
2. **Update Data Model Documentation**: Update `documentation/data_model.md` if models changed
3. **Create Thoughts Documentation**: Add insights to `documentation/claudes_thoughts/` if significant changes

## Environment
1. **Virtual Environment**: Ensure `.venv` is properly activated
2. **Dependencies**: Update `requirements.txt` if new packages were added

## Git Operations
1. **Stage Changes**: `git add .`
2. **Commit**: `git commit -m "descriptive message"`
3. **Push**: `git push` (if working on main branch or feature branch)

Note: Specific linting, formatting, and type checking commands should be identified by examining the project for configuration files like `.flake8`, `mypy.ini`, `black.toml`, etc.