# Context Studio Local Server

The Context Studio local server is a Python-based backend application that serves as the data management layer for the Context Studio React Native app. It provides comprehensive dataset management, CRUD APIs for hierarchical taxonomical data, semantic search capabilities, and natural language processing features.

## Capabilities

### Data Management
- **Hierarchical Taxonomical Structure**: Manage Layers, Domains, Terms, and Term Relationships in a structured hierarchy
- **Multi-Dataset Support**: Create, switch between, and manage multiple independent datasets
- **CRUD Operations**: Full Create, Read, Update, Delete operations for all entity types
- **Vector Embeddings**: Automatic generation and storage of semantic embeddings for titles and definitions
- **Semantic Search**: Vector similarity search across all entities using sentence-transformers

### API Features
- **RESTful APIs**: Complete REST endpoints for all data operations
- **Pagination**: Built-in pagination support for large datasets
- **Real-time Processing**: Event-driven architecture with background processing
- **Data Validation**: Robust input validation using Pydantic models
- **OpenAPI Documentation**: Auto-generated API documentation

### Natural Language Processing
- **Text Analysis**: Integrated NLP pipeline for text processing and analysis
- **Entity Recognition**: Named entity recognition and linguistic analysis
- **Embedding Generation**: Semantic embeddings using sentence-transformers models
- **Graph Analysis**: Network analysis and relationship mapping

### Import/Export
- **CSV Import**: Bulk data import from CSV files
- **Data Export**: Export datasets in various formats
- **Schema Migration**: Database schema versioning and migration support

## Design

The application follows a modular architecture with clear separation of concerns:

- **API Layer**: FastAPI-based REST endpoints with automatic OpenAPI documentation
- **Data Layer**: SQLAlchemy ORM with SQLite database and sqlite-vec extension for vector operations
- **Service Layer**: Business logic for graph operations, NLP processing, and dataset management
- **Event System**: Asynchronous event processing for real-time updates and logging
- **Embedding System**: Semantic embedding generation and similarity search

The data model consists of four main entities:
- **Layers**: Top-level organizational units
- **Domains**: Sub-categories within layers
- **Terms**: Individual taxonomical entries with definitions
- **Term Relationships**: Directional relationships between terms with predicates

## Tech Stack

### Core Framework
- **Python 3.12+**: Core programming language
- **FastAPI**: Modern web framework for building APIs
- **Uvicorn**: ASGI server for serving the application
- **SQLAlchemy**: Object-relational mapping (ORM) framework
- **Pydantic**: Data validation and serialization

### Database & Storage
- **SQLite**: Lightweight, file-based database
- **sqlite-vec**: Vector similarity search extension for SQLite
- **Alembic**: Database migration management

### Natural Language Processing
- **spaCy**: Industrial-strength NLP library
- **sentence-transformers**: Semantic text embeddings
- **NLTK**: Natural language toolkit
- **scikit-learn**: Machine learning utilities

### Additional Libraries
- **pandas**: Data manipulation and analysis
- **networkx**: Graph analysis and visualization
- **pytest**: Testing framework
- **python-dotenv**: Environment variable management

## Developing

### Prerequisites
- Python 3.12 or higher
- Virtual environment (recommended)

### Setup

1. **Clone the repository and navigate to the local-server directory**
   ```bash
   cd context-studio/local-server
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables (optional)**
   ```bash
   cp .env.example .env  # If available
   # Edit .env with your configuration
   ```

### Running the Application

#### Development Mode
```bash
# Activate virtual environment
source .venv/bin/activate

# Run with auto-reload
python app.py

# Or specify custom host/port
python app.py --host 0.0.0.0 --port 8080
```

The server will start on `http://127.0.0.1:8000` by default with automatic reload enabled for development.

#### Production Mode
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

### API Documentation

Once the server is running, you can access:
- **Interactive API Documentation**: `http://localhost:8000/docs`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit_tests/
pytest tests/integration_tests/
pytest tests/performance_tests/

# Run with coverage
pytest --cov=.
```

### Database Management

The application automatically creates and manages SQLite databases. Each dataset is stored as a separate SQLite file.

#### Migrations
```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head
```

### Development Workflow

1. **Activate virtual environment**: Always use `source .venv/bin/activate` before development
2. **Code changes**: The server runs with auto-reload in development mode
3. **Testing**: Write and run tests for new features
4. **Database changes**: Create migrations for schema modifications
5. **Documentation**: Update API documentation as needed

### Updating the API Spec

The OpenAPI specification is automatically generated by FastAPI. To update the documented schema:

```bash
# Generate/update the OpenAPI JSON file
python utils/update_api_specs.py
```

This will create or update the `documentation/openapi.json` file with the current API schema.

### Project Structure

```
local-server/
├── api/                   # API endpoint implementations
├── database/              # Database models and utilities
├── dataset/               # Dataset management
├── embeddings/            # Vector embedding generation
├── graph/                 # Graph analysis and SPARQL services
├── nlp/                   # Natural language processing
├── tests/                 # Unit, integration, and performance tests
├── utils/                 # Utility functions and helpers
├── app.py                 # Main application entry point
├── config.py              # Configuration management
└── requirements.txt       # Python dependencies
```

### Troubleshooting

#### Common Issues

1. **Database initialization errors**: Ensure the `.venv` virtual environment is activated
2. **Import errors**: Verify all dependencies are installed with `pip install -r requirements.txt`
3. **Port conflicts**: Use `--port` argument to specify a different port
4. **Vector extension issues**: The sqlite-vec extension should install automatically with the requirements
5. **Git package installation failures**: If `pip install` fails when installing packages from git repositories (like concepcy) with an error about `.gitconfig`, this is typically due to a corrupted git configuration. Workaround:
   ```bash
   export GIT_CONFIG_GLOBAL=/tmp/gitconfig
   git config --global user.name "Context Studio"
   git config --global user.email "noreply@contextstudio.local"
   pip install -r requirements.txt
   ```

#### Logs

Application logs are written to:
- Console output (with color formatting in development)
- `logs/context_studio.log` (file-based logging)
- `logs/dataset_action_log.json` (structured dataset operation logs)

For debugging, check the log files or run with increased verbosity.