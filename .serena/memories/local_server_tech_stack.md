# Local Server Tech Stack & Conventions

## Tech Stack
- **Language**: Python 3.x
- **Web Server**: uvicorn
- **API Framework**: FastAPI  
- **Database**: SQLite with SQLiteVector for vector storage
- **Data Validation**: Pydantic
- **Test Framework**: pytest
- **ORM**: SQLAlchemy
- **Vector Operations**: sqlite-vec extension

## Code Style & Conventions
- **File Naming**: snake_case for files and variables
- **Class Naming**: CamelCase for class names  
- **Imports**: Always place all import statements at the top of the file
- **Docstrings**: Use triple double quotes for docstrings
- **Comments**: Don't create documentation files unless explicitly requested
- **Reports**: All markdown reports (except README.md) go in `documentation/claudes_thoughts/`

## Project Structure
```
local-server/
├── api/                    # API endpoints
├── app.py                  # Main application file
├── config.py              # Configuration settings
├── database/              # Database models and utilities
├── services/              # Business logic services
├── tests/                 # Test files (unit, integration, performance)
├── utils/                 # Utility functions
├── requirements.txt       # Python dependencies
└── pytest.ini           # Test configuration
```

## Testing Setup
- Test paths: `tests/`
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`
- Markers: integration, performance, slow, unit, fast
- Run with: `pytest`
- Configuration: `pytest.ini` with logging, asyncio mode, markers

## Common Pitfalls
- When comparing UUID values, always cast them to strings (SQLite stores UUIDs as text)
- Update system path in test files to avoid PYTHON_PATH issues:
```python
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```