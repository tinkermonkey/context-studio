# Suggested Commands for Context Studio Local Server

## Environment Setup
```bash
source .venv/bin/activate  # Activate virtual environment
```

## Running the Application
```bash
python app.py              # Start the FastAPI server with uvicorn
```

## Testing
```bash
pytest                     # Run all tests
pytest tests/unit_tests/   # Run unit tests only
pytest tests/integration_tests/  # Run integration tests only
pytest tests/performance_tests/  # Run performance tests only
pytest -m unit            # Run tests marked as unit tests
pytest -m integration     # Run tests marked as integration tests
pytest -m performance     # Run tests marked as performance tests
```

## Database Operations
```bash
python database/migrations/migration_manager.py  # Manage database migrations
```

## Development Utilities
```bash
python -m pip install -r requirements.txt  # Install dependencies
python -c "import sys; print(sys.path)"    # Check Python path
```

## Common Git Operations (macOS/Darwin)
```bash
git status                 # Check repository status
git add .                  # Stage all changes
git commit -m "message"    # Commit changes
git push                   # Push to remote
git pull                   # Pull from remote
```

## File Operations (macOS/Darwin)
```bash
ls -la                     # List files with details
find . -name "*.py"        # Find Python files
grep -r "pattern" .        # Search for pattern in files
cd directory_name          # Change directory
```