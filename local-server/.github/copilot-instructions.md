# Context Studio Local Server

Python server for the Context Studio, a React Native app built with Expo and Gluestack-UI V2. This server is used to run the app locally during development and is deployed with the desktop app to serve the UX.

## Technology Stack

- **Language**: Python
- **Web Server**: uvicorn
- **API Framework**: FastAPI
- **Database**: SQLite with SQLiteVector for vector storage
- **Data Validation**: Pydantic
- **Embeddings**: sentence-transformers
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
|   ├── models.py                                 # Database models
|   ├── utils.py                                  # Database utilities
├── documentation                                 # API and data model documentation
|   ├── requirements.md                           # High level requirements
|   ├── api.md                                    # API documentation
|   ├── data_model.md                             # Data model documentation
├── embeddings                                    # Embedding generation utilities
|   ├── __init__.py
|   ├── generate_embeddings.py                    # Functions to generate embeddings
├── requirements.txt                              # Python dependencies
├── README.md                                     # Project documentation
├── tests                                         # Unit tests
|   ├── __init__.py
|   ├── unit_tests                                # Unit tests for individual components
|       ├── test_layers.py                        # Unit tests for layer APIs
|       ├── test_domains.py                       # Unit tests for domain APIs
|       ├── test_terms.py                         # Unit tests for term APIs
|       ├── test_relationships.py                 # Unit tests for term relationship APIs
|   ├── integration_tests                         # Integration tests for API endpoints
|       ├── test_layers_integration.py            # Integration tests for layer APIs
|       ├── test_domains_integration.py           # Integration tests for domain APIs
|       ├── test_terms_integration.py             # Integration tests for term APIs
|       ├── test_relationships_integration.py     # Integration tests for term relationship APIs
|   ├── performance_tests                         # Performance tests for APIs
|       ├── test_layers_performance.py            # Performance tests for layer APIs
|       ├── test_domains_performance.py           # Performance tests for domain APIs
|       ├── test_terms_performance.py             # Performance tests for term APIs
|       ├── test_relationships_performance.py     # Performance tests for term relationship APIs
├── utils                                         # Utility functions
|   ├── __init__.py
|   ├── logger.py                                 # Logging utilities

```

## Code Style
- Always place all import statements at the top of the file.
- Use snake_case for variable and function names.
- Use CamelCase for class names.
- Use triple double quotes for docstrings.

## Best Practices
- **Code Quality**: Follow PEP 8 style guide for Python code.
- **Documentation**: Maintain clear and concise documentation for APIs and data models.
- **Testing**: Write unit tests for all critical functionalities using pytest. Write integration tests for API endpoints.
- **Environment Variables**: Use `.env` files for sensitive configurations and secrets.

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