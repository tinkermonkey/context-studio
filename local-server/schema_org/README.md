# Schema.org Module

This module handles downloading, parsing, and populating a local SQLite database with Schema.org ontology data for semantic search and reference.

## Features

- **Automatic Download**: Fetches Schema.org JSON-LD data from configured source URL
- **Rebuild Strategy**: Uses rebuild-only approach (no migrations, backup/restore)
- **Vector Search**: Semantic search using sqlite-vec extension with text embeddings
- **Performance Monitoring**: Comprehensive metrics tracking for imports and searches
- **Error Handling**: Clear, actionable error messages with resolution guidance

## Configuration

See [CONFIGURATION.md](./CONFIGURATION.md) for detailed configuration options including:

- Batch size tuning (memory vs. performance trade-offs)
- Embedding model settings
- Source URL configuration
- Performance benchmarks and recommendations

## Environment Variables

- `SCHEMA_ORG_METRICS_LOGGING`: Enable/disable metrics logging (default: `true`)
- `SCHEMA_ORG_AUTO_INITIALIZE`: Auto-populate database on startup (default: configured in settings)
- `SCHEMA_ORG_SOURCE_URL`: Source URL for Schema.org JSON-LD (default: configured in settings)
- `SCHEMA_ORG_DB_PATH`: Path to SQLite database file (default: configured in settings)

## Requirements

- **sqlite-vec**: Required for vector search functionality
  - Install: `pip install sqlite-vec`
  - Already included in `requirements.txt`
- **psutil**: Required for memory profiling during imports
  - Install: `pip install psutil`
  - Already included in `requirements.txt`

## Usage

### Basic Usage

```python
from schema_org.manager import SchemaOrgManager

# Initialize manager
manager = SchemaOrgManager()
manager.initialize()

# Refresh data (download and rebuild database)
result = manager.refresh_data(force=True)
if result["success"]:
    print(f"Import metrics: {result['metrics']}")
```

### Search

```python
from schema_org.service import SchemaOrgService

service = SchemaOrgService()

# Semantic search
results = service.semantic_search("person", threshold=0.7, limit=10)
for entity in results:
    print(f"{entity['type']}: {entity['label']}")
```

## Architecture

- **manager.py**: Database lifecycle management (download, parse, populate, rebuild)
- **service.py**: Search API (semantic vector search)
- **models.py**: SQLAlchemy ORM models for entities and properties
- **errors.py**: Custom exception classes
- **metrics.py**: Performance monitoring and metrics tracking
- **api.py**: FastAPI REST endpoints

## Performance

- **Memory Usage**: Typically <100MB for full Schema.org import (configurable batch sizes)
- **Search Latency**: <50ms for interactive semantic search queries
- **Import Duration**: ~2-5 minutes for full Schema.org dataset (varies by network and hardware)

See [CONFIGURATION.md](./CONFIGURATION.md) for detailed performance tuning guidance.

## Error Handling

The module provides clear, actionable error messages:

- **Missing sqlite-vec**: Installation instructions provided
- **Malformed JSON**: Line/column numbers and resolution steps
- **Download failures**: Network and URL configuration guidance
- **Database errors**: Specific error context and debugging tips

## Testing

```bash
# Unit tests
pytest local-server/tests/unit_tests/test_phase5_cleanup.py

# Performance tests
pytest local-server/tests/performance_tests/test_baseline_validation.py
```

## Monitoring

Import and search metrics are logged automatically when `SCHEMA_ORG_METRICS_LOGGING=true`:

- Import: duration, entity/property counts, embedding statistics, peak memory
- Search: query time, result counts, search type

Use DEBUG log level for detailed metrics, INFO for summary metrics.
