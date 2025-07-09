# Context Studio Local Server

Python server for the Context Studio, a React Native app built with Expo and Gluestack-UI V2. This server is used to run the app locally during development and is deployed with the desktop app to serve the UX.

## Technology Stack

- **Language**: Python
- **API Framework**: FastAPI
- **Database**: SQLite with SQLiteVector for vector storage
- **Data Validation**: Pydantic
- **Embeddings**: sentence-transformers
- **Test Framework**: pytest

## Code Structure

```text
/
├── .env                          # Dev environment variables (not in git)
├── api                           # API endpoints
├── app.py                        # Main application file
├── config.py                     # Configuration settings
├── database                      # Database models and utilities
|   ├── __init__.py
|   ├── models.py                 # Database models
|   ├── utils.py                  # Database utilities
├── documentation                 # API and data model documentation
|   ├── requirements.md           # High level requirements
|   ├── api.md                    # API documentation
|   ├── data_model.md             # Data model documentation
├── embeddings                    # Embedding generation utilities
|   ├── __init__.py
|   ├── generate_embeddings.py    # Functions to generate embeddings
├── requirements.txt              # Python dependencies
├── README.md                     # Project documentation
├── tests                         # Unit tests
|   ├── __init__.py
├── utils                         # Utility functions
|   ├── __init__.py
|   ├── logger.py                 # Logging utilities

```

## Best Practices
- **Code Quality**: Follow PEP 8 style guide for Python code.
- **Documentation**: Maintain clear and concise documentation for APIs and data models.
- **Testing**: Write unit tests for all critical functionalities using pytest. Write integration tests for API endpoints.
- **Environment Variables**: Use `.env` files for sensitive configurations and secrets.