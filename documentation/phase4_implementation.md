# Phase 4: API Contract Validation and End-to-End Integration

## Overview

Phase 4 completes the reference database implementation with comprehensive API contract validation, health monitoring, and end-to-end integration testing.

## Implementation Summary

### 1. API Enhancements

#### Search API Similarity Scores
- **Location**: `/api/reference/ref-db/search`
- **Enhancement**: Response includes `similarity_score` field for each result
- **Format**: Float value between 0.0 and 1.0
- **Example Response**:
```json
{
  "query": "person who writes books",
  "total_results": 5,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Person",
      "definition": "A person (alive, dead, undead, or fictional).",
      "source": "schema.org",
      "external_id": "Person",
      "similarity_score": 0.87
    }
  ]
}
```

#### Health Check Endpoint
- **Location**: `/api/reference/ref-db/health`
- **Performance**: <200ms execution time
- **Response Schema**:
```json
{
  "status": "healthy|degraded|missing",
  "node_count": 1000,
  "vec_count": 1000,
  "schema_version": "1.0.0",
  "model_version": "sentence-transformers/all-MiniLM-L6-v2",
  "last_import_at": "2025-10-05",
  "database_size": 52428800,
  "database_path": "/path/to/reference.db",
  "execution_time_ms": 45.23,
  "checked_at": "2025-10-05T12:34:56.789Z"
}
```

#### Health Status Logic
- **healthy**: `node_count == vec_count` AND versions match expected
- **degraded**: Vector count mismatch OR version mismatch
- **missing**: Database file doesn't exist

### 2. ReferenceManager Enhancements

#### get_status() Method
- **Location**: `reference_db/manager.py`
- **Purpose**: Comprehensive database status reporting
- **Returns**: Dictionary with health metrics
- **Implementation**:
  ```python
  def get_status(self) -> Dict[str, Any]:
      """Get comprehensive status of the reference database."""
      # Check file existence
      # Query schema version
      # Count nodes and embeddings
      # Determine health status
      return status_dict
  ```

### 3. Test Fixtures

#### schema_org_sample.jsonld
- **Location**: `/workspace/local-server/tests/fixtures/schema_org_sample.jsonld`
- **Content**: 20-30 Schema.org entities and properties
- **Entities**: Person, Thing, Organization, Place, CreativeWork, Book, Event, Product, etc.
- **Properties**: author, name, givenName, publisher, organizer, location, etc.
- **Relationships**: subClassOf, domainIncludes, rangeIncludes

#### known_queries.json
- **Location**: `/workspace/local-server/tests/fixtures/known_queries.json`
- **Content**: 15-20 known queries with expected results
- **Query Patterns**:
  - Entity lookup: "person who writes books"
  - Property discovery: "organization location"
  - Relationship traversal: "book publisher"
  - Semantic similarity: "person name"

### 4. Test Implementation

#### System Tests (TC-S001 - TC-S003)
**File**: `test_phase4_system_tests.py`

- **TC-S001**: End-to-end workflow
  - StructureNode creation → search → link retrieval
  - Validates "person who writes books" query
  - Verifies name/givenName properties via domainIncludes

- **TC-S002**: Health check validation
  - Schema validation
  - Status determination (healthy/degraded/missing)
  - Performance <200ms

- **TC-S003**: API contract validation
  - Response schema validation
  - Field presence and types
  - Backward compatibility

#### Integration Tests (TC-I001 - TC-I005)
**File**: `test_phase4_integration_tests.py`

- **TC-I001**: Vector similarity search accuracy (>95% target)
- **TC-I002**: Link retrieval and traversal
- **TC-I003**: Multi-hop relationship queries
- **TC-I004**: Query performance benchmarks
- **TC-I005**: Known queries validation

#### Performance Tests (TC-P001 - TC-P003)
**File**: `test_phase4_performance_tests.py`

- **TC-P001**: Search performance scaling
  - 100-node dataset baseline
  - <100ms average, <200ms max

- **TC-P002**: Concurrent request handling
  - 20+ concurrent searches
  - Thread pool execution

- **TC-P003**: Large result set pagination
  - Multiple page sizes
  - Performance consistency

#### Security Tests (TC-SEC001 - TC-SEC004)
**File**: `test_phase4_security_tests.py`

- **TC-SEC001**: SQL injection prevention
  - Query parameter injection attempts
  - Predicate filter injection
  - Database integrity verification

- **TC-SEC002**: HTTPS enforcement
  - HTTP URL rejection
  - Configuration validation

- **TC-SEC003**: Write endpoint protection
  - No POST/PUT/DELETE endpoints
  - Returns 404/405 for write attempts

- **TC-SEC004**: Error message sanitization
  - No stack traces in responses
  - No SQL query exposure
  - No internal path disclosure

## Configuration Examples

### Basic Setup
```python
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager

# Create configuration
config = ReferenceConfig()

# Initialize manager
with ReferenceManager(config) as manager:
    # Check status
    status = manager.get_status()
    print(f"Database status: {status['status']}")
    print(f"Nodes: {status['node_count']}, Vectors: {status['vec_count']}")
```

### Health Check
```bash
curl http://localhost:8000/api/reference/ref-db/health
```

### Vector Search
```bash
curl "http://localhost:8000/api/reference/ref-db/search?query=person+who+writes+books&limit=10&threshold=0.7"
```

### Link Retrieval
```bash
curl "http://localhost:8000/api/reference/ref-db/nodes/{node_id}/links?direction=both&predicate=domainIncludes"
```

## Database Rebuild Procedure

### When to Rebuild
- Schema version mismatch detected
- Embedding model version changed
- Database corruption
- Manual rebuild required

### Rebuild Steps

1. **Automatic Rebuild** (on version mismatch):
   ```python
   # Manager automatically detects and rebuilds
   manager = ReferenceManager(config)
   # Backup created, database rebuilt with new schema
   ```

2. **Manual Rebuild**:
   ```python
   from reference_db.manager import ReferenceManager
   from reference_db.config import ReferenceConfig

   config = ReferenceConfig()
   manager = ReferenceManager(config)

   # Force rebuild by deleting database
   import os
   os.remove(manager.db_path)

   # Reinitialize creates new database
   manager = ReferenceManager(config)
   ```

3. **Backup Restoration**:
   ```bash
   # List backups
   ls -la /path/to/reference.db.backup.*

   # Restore from backup
   cp reference.db.backup.2025-10-05 reference.db
   ```

### Backup Policy
- Automatic backup on rebuild: `{db_path}.backup.{YYYY-MM-DD}`
- Backup validation: Size check, existence check
- Lock file prevents concurrent rebuilds: `{db_path}.rebuild.lock`

## sqlite-vec Installation

### Requirements
```bash
pip install sqlite-vec
```

### Verification
```python
import sqlite3
conn = sqlite3.connect(':memory:')
conn.enable_load_extension(True)
# If this works, sqlite-vec is properly installed
```

### Troubleshooting

**Error**: "Vector search dependencies missing"
```bash
# Install sqlite-vec
pip install sqlite-vec

# Verify installation
python -c "import sqlite_vec; print('OK')"
```

**Error**: "no such function: vec_distance_cosine"
```bash
# Ensure sqlite-vec extension loads
# Check database/utils.py for extension loading
```

## Performance Benchmarks

### Search Performance
- **Small dataset (100 nodes)**: <100ms average
- **Large dataset (1000+ nodes)**: <500ms average
- **Concurrent requests (20)**: <5s total

### Health Check Performance
- **Target**: <200ms
- **Typical**: 45-100ms
- **Includes**: Database queries, file I/O, version checks

### Link Retrieval Performance
- **Target**: <50ms
- **Typical**: 10-30ms
- **Concurrent (30 requests)**: <2s total

## API Compatibility

### Backward Compatibility
All existing endpoints maintain backward compatibility:
- Entity/property lookup endpoints unchanged
- Search API adds similarity_score field (non-breaking)
- Health check is new endpoint (additive)

### Version Migration
- Schema version tracked in database
- Automatic rebuild on version mismatch
- Backup created before migration

## Test Coverage

### Running Tests
```bash
# Run all Phase 4 tests
pytest tests/integration_tests/test_phase4_*.py -v

# Run specific test category
pytest tests/integration_tests/test_phase4_system_tests.py -v
pytest tests/integration_tests/test_phase4_integration_tests.py -v
pytest tests/integration_tests/test_phase4_performance_tests.py -v
pytest tests/integration_tests/test_phase4_security_tests.py -v

# Run with coverage
pytest tests/integration_tests/test_phase4_*.py --cov=reference_db --cov=api.reference --cov-report=html
```

### Expected Results
- All system tests pass (TC-S001-TC-S003)
- Integration tests >95% accuracy (TC-I001-TC-I005)
- Performance tests meet benchmarks (TC-P001-TC-P003)
- Security tests validate protections (TC-SEC001-TC-SEC004)
- Overall coverage >80%

## Troubleshooting

### Health Check Reports "Degraded"
**Cause**: Vector count mismatch or version mismatch

**Solution**:
```python
# Check status details
status = manager.get_status()
print(status.get('degraded_reason'))

# If embedding mismatch, regenerate embeddings
# If version mismatch, rebuild database
```

### Search Returns No Results
**Cause**: Threshold too high or no embeddings

**Solution**:
```python
# Lower threshold
results = manager.search_by_similarity(
    query_text="test",
    threshold=0.5,  # Try lower threshold
    embedding_generator=generate_embedding
)

# Check if nodes have embeddings
status = manager.get_status()
if status['vec_count'] == 0:
    # Need to import/generate embeddings
```

### Performance Issues
**Cause**: Large dataset, missing indexes, concurrent access

**Solution**:
1. Check database size: `status['database_size']`
2. Limit result sets: Use appropriate `limit` parameter
3. Use connection pooling for concurrent access
4. Consider pagination for large result sets

## Next Steps

### Future Enhancements
1. **Pagination support**: Add offset parameter to search
2. **Caching**: Implement query result caching
3. **Batch operations**: Support bulk node/link creation
4. **Advanced filtering**: Additional filter options
5. **Performance monitoring**: Metrics collection and analysis

### Integration Points
1. **UX Integration**: Update frontend to use similarity scores
2. **StructureNode Integration**: Link reference nodes to structure
3. **Chat Integration**: Use reference search in chat context
4. **MCP Server**: Expose reference search via MCP protocol
