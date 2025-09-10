# Code Style and Conventions

## Python Style
- Follow PEP 8 style guide
- Use snake_case for variable and function names
- Use CamelCase for class names
- Use triple double quotes for docstrings
- Place all import statements at the top of the file

## Documentation
- Don't create documentation files unless explicitly requested
- All markdown reports and summaries other than README.md should be placed in `documentation/claudes_thoughts` directory
- Maintain clear and concise documentation for APIs and data models

## Database
- Use the migration manager for database migrations
- Always create a migration script when modifying the database schema
- When comparing UUID values, always cast them to strings (SQLite stores UUIDs as text)

## Testing
- Write unit tests for all critical functionalities using pytest
- Write integration tests for API endpoints
- Update system path in test files to avoid PYTHON_PATH issues:
  ```python
  import sys
  import os
  sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  ```

## Environment
- Use `.env` files for sensitive configurations and secrets
- Use `.venv` virtual environment when executing python commands
- Activate with `source .venv/bin/activate` before running server or tests