# Context Studio Local Server

Python server for the Context Studio (a React app built using Flowbite-React). This server is used to run the app locally during development and is deployed with the desktop app to serve the UX.

## Technology Stack

- **Language**: Python
- **Web Server**: uvicorn
- **API Framework**: FastAPI
- **Database**: SQLite with SQLiteVector for vector storage
- **Data Validation**: Pydantic
- **Test Framework**: pytest

## Code Structure

```text
/
├── .env                                          # Dev environment variables (not in git)
├── api                                           # API endpoints
├── app.py                                        # Main application file
├── config.py                                     # Configuration settings
├── database                                      # Database models and utilities
|   ├── __init__.py
|   ├── migrations                                # Database migrations
|       ├── migration_manager.py                  # Migration management script
|       ├── versions                              # Migration version scripts
|   ├── models.py                                 # Database models
|   ├── utils.py                                  # Database utilities
├── documentation                                 # API and data model documentation
|   ├── requirements.md                           # High level requirements
|   ├── api.md                                    # API documentation
|   ├── data_model.md                             # Data model documentation
|   ├── claudes_thoughts                          # Claude's thoughts and insights
├── embeddings                                    # Embedding generation utilities
|   ├── __init__.py
|   ├── generate_embeddings.py                    # Functions to generate embeddings
├── graph                                         # Graph data structure and utilities
├── nlp                                           # Natural Language Processing utilities
├── nlp_sandbox                                   # Experimental NLP POCs
├── requirements.txt                              # Python dependencies
├── README.md                                     # Project documentation
├── tests                                         # Unit tests
|   ├── __init__.py
|   ├── unit_tests                                # Unit tests for individual components
|   ├── integration_tests                         # Integration tests for API endpoints
|   ├── performance_tests                         # Performance tests for APIs
├── triage_scripts                                # Scripts for triaging fundamental issues
├── utils                                         # Utility functions
|   ├── __init__.py
|   ├── logger.py                                 # Logging utilities

```

## Code Style
- Don't create documentation files unless explicitly requested
- All markdown reports and summaries other than README.md should be placed in the `documentation/claudes_thoughts` directory
- Always place all import statements at the top of the file.
- Use snake_case for variable and function names.
- Use CamelCase for class names.
- Use triple double quotes for docstrings.

## Best Practices
- **Schema Management**: Use the migration manager for database migrations. Always create a migration script when modifying the database schema.
- **Code Quality**: Follow PEP 8 style guide for Python code.
- **Documentation**: Maintain clear and concise documentation for APIs and data models.
- **Testing**: Write unit tests for all critical functionalities using pytest. Write integration tests for API endpoints.
- **Environment Variables**: Use `.env` files for sensitive configurations and secrets.
- **Virtual Environment**: Use the `.venv` virtual environment when executing python commands, and activate it with `source .venv/bin/activate` before running the server or tests.

### Common pitfalls
- When comparing UUID values, always cast them to strings, as SQLite stores UUIDs as text.

### Testing
- Use `pytest` for running tests.
- To avoid having to set `PYTHON_PATH` for each test run, update the system path in the test files:
```python
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
