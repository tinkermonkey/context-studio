# RAG Pipeline Data Model

## Overview

The RAG pipeline stores observability data in the `operations.db` database for performance monitoring, debugging, and analytics. Two main tables track metrics and detailed trace information with automatic retention policies.

---

## Database: operations.db

### Table: rag_processing_metrics

Stores aggregated performance metrics for each RAG extraction request (30-day retention).

#### Schema

```sql
CREATE TABLE rag_processing_metrics (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    sentence_text TEXT NOT NULL,
    layer_0_time_ms INTEGER,
    layer_0_count INTEGER,
    layer_1_time_ms INTEGER,
    layer_1_count INTEGER,
    layer_2_time_ms INTEGER,
    layer_2_count INTEGER,
    layer_3_time_ms INTEGER,
    layer_3_count INTEGER,
    total_time_ms INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    retention_days INTEGER DEFAULT 30 NOT NULL
);
```

#### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `id` | TEXT | UUID primary key for this metrics record |
| `request_id` | TEXT | UUID of the extraction request (from API response) |
| `sentence_text` | TEXT | Input text (truncated to 500 chars for storage) |
| `layer_0_time_ms` | INTEGER | Layer 0 (KG context) execution time in milliseconds |
| `layer_0_count` | INTEGER | Number of entities/nodes found in Layer 0 |
| `layer_1_time_ms` | INTEGER | Layer 1 (LLM extraction) execution time in milliseconds |
| `layer_1_count` | INTEGER | Number of entities extracted by LLM |
| `layer_2_time_ms` | INTEGER | Layer 2 (spaCy gap detection) execution time in milliseconds |
| `layer_2_count` | INTEGER | Number of gaps detected in Layer 2 |
| `layer_3_time_ms` | INTEGER | Layer 3 (concept resolution) execution time in milliseconds |
| `layer_3_count` | INTEGER | Number of concepts resolved in Layer 3 |
| `total_time_ms` | INTEGER | Total pipeline execution time in milliseconds |
| `timestamp` | DATETIME | When the extraction was performed (UTC) |
| `retention_days` | INTEGER | Retention period (default: 30 days) |

#### Indexes

```sql
CREATE INDEX idx_rag_metrics_request_id ON rag_processing_metrics(request_id);
CREATE INDEX idx_rag_metrics_timestamp ON rag_processing_metrics(timestamp);
```

#### Example Record

```json
{
  "id": "m-550e8400-e29b-41d4-a716-446655440000",
  "request_id": "r-123e4567-e89b-12d3-a456-426614174000",
  "sentence_text": "Machine learning uses neural networks...",
  "layer_0_time_ms": 125,
  "layer_0_count": 5,
  "layer_1_time_ms": 2500,
  "layer_1_count": 8,
  "layer_2_time_ms": 85,
  "layer_2_count": 3,
  "layer_3_time_ms": 1200,
  "layer_3_count": 2,
  "total_time_ms": 3910,
  "timestamp": "2025-10-16T22:30:00.000Z",
  "retention_days": 30
}
```

---

### Table: rag_observability_trace

Stores detailed trace data for each layer of the pipeline (7-day retention).

#### Schema

```sql
CREATE TABLE rag_observability_trace (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    sentence_index INTEGER NOT NULL,
    layer_name TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    trace_data TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    retention_days INTEGER DEFAULT 7 NOT NULL
);
```

#### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `id` | TEXT | UUID primary key for this trace record |
| `request_id` | TEXT | UUID of the extraction request (links to metrics) |
| `sentence_index` | INTEGER | Index of sentence being processed (0-based, -1 for paragraph-level) |
| `layer_name` | TEXT | Name of processing layer (see Layer Names below) |
| `operation_type` | TEXT | Type of operation (see Operation Types below) |
| `trace_data` | TEXT | JSON-encoded trace details (structure varies by layer) |
| `timestamp` | DATETIME | When this trace was recorded (UTC) |
| `retention_days` | INTEGER | Retention period (default: 7 days) |

#### Layer Names

| Layer Name | Description |
|------------|-------------|
| `kg_context` | Layer 0: Knowledge graph context preparation |
| `llm_extraction` | Layer 1: LLM-based entity extraction |
| `spacy_gap` | Layer 2: spaCy gap detection |
| `concept_resolution` | Layer 3: Concept resolution via web search |

#### Operation Types

| Operation Type | Description |
|----------------|-------------|
| `input` | Input data to the layer |
| `output` | Output data from the layer |
| `error` | Error information if layer failed |
| `timeout` | Timeout information if layer exceeded limit |

#### Indexes

```sql
CREATE INDEX idx_rag_trace_request_id ON rag_observability_trace(request_id);
CREATE INDEX idx_rag_trace_layer ON rag_observability_trace(layer_name);
CREATE INDEX idx_rag_trace_timestamp ON rag_observability_trace(timestamp);
```

#### Example Records

**Layer 0 (KG Context) Trace:**
```json
{
  "id": "t-550e8400-e29b-41d4-a716-446655440001",
  "request_id": "r-123e4567-e89b-12d3-a456-426614174000",
  "sentence_index": 0,
  "layer_name": "kg_context",
  "operation_type": "output",
  "trace_data": {
    "extracted_phrases": [
      {"text": "machine learning", "start": 0, "end": 16},
      {"text": "neural networks", "start": 23, "end": 38}
    ],
    "kg_nodes_found": 5,
    "similarity_scores": [0.95, 0.88, 0.82, 0.79, 0.75],
    "total_sentences": 1
  },
  "timestamp": "2025-10-16T22:30:00.123Z",
  "retention_days": 7
}
```

**Layer 1 (LLM Extraction) Trace:**
```json
{
  "id": "t-550e8400-e29b-41d4-a716-446655440002",
  "request_id": "r-123e4567-e89b-12d3-a456-426614174000",
  "sentence_index": 0,
  "layer_name": "llm_extraction",
  "operation_type": "output",
  "trace_data": {
    "entities_extracted": 8,
    "kg_context_size": 5,
    "token_usage": {
      "prompt_tokens": 150,
      "completion_tokens": 75
    },
    "execution_id": "llm-exec-12345"
  },
  "timestamp": "2025-10-16T22:30:02.650Z",
  "retention_days": 7
}
```

**Layer 2 (spaCy Gap) Trace:**
```json
{
  "id": "t-550e8400-e29b-41d4-a716-446655440003",
  "request_id": "r-123e4567-e89b-12d3-a456-426614174000",
  "sentence_index": 0,
  "layer_name": "spacy_gap",
  "operation_type": "output",
  "trace_data": {
    "gaps_detected": 3,
    "total_noun_phrases": 12,
    "filtered_by_tfidf": 2,
    "priority_distribution": {
      "CRITICAL": 0,
      "IMPORTANT": 2,
      "CONTEXTUAL": 1
    }
  },
  "timestamp": "2025-10-16T22:30:02.735Z",
  "retention_days": 7
}
```

**Layer 3 (Concept Resolution) Trace:**
```json
{
  "id": "t-550e8400-e29b-41d4-a716-446655440004",
  "request_id": "r-123e4567-e89b-12d3-a456-426614174000",
  "sentence_index": 0,
  "layer_name": "concept_resolution",
  "operation_type": "output",
  "trace_data": {
    "gaps_resolved": 2,
    "gaps_unresolved": 1,
    "web_searches_performed": 1,
    "cached_kg_hits": 0,
    "full_kg_hits": 1,
    "resolution_methods": {
      "CACHED_KG": 0,
      "FULL_KG": 1,
      "WEB_SEARCH": 1,
      "UNRESOLVED": 1
    }
  },
  "timestamp": "2025-10-16T22:30:03.950Z",
  "retention_days": 7
}
```

---

## Data Flow

```
┌─────────────────────────────────────┐
│   RAG Extraction Request            │
│   POST /api/rag/extract             │
└──────────────┬──────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│   RAG Pipeline Service               │
│   - Processes through 4 layers       │
│   - Collects metrics & traces        │
└──────────────┬───────────────────────┘
               │
               ├──────────────────────┐
               │                      │
               ▼                      ▼
┌────────────────────────┐   ┌──────────────────────┐
│ rag_processing_metrics │   │ rag_observability_   │
│                        │   │ trace (if enabled)   │
│ - 1 record per request │   │ - 4 records per      │
│ - 30-day retention     │   │   request (1 per     │
│ - Aggregate metrics    │   │   layer)             │
└────────────────────────┘   │ - 7-day retention    │
                             │ - Detailed traces    │
                             └──────────────────────┘
```

---

## Retention and Cleanup

### Automatic Cleanup

- **Scheduler**: `RAGCleanupScheduler` runs every 24 hours (configurable)
- **Metrics Cleanup**: Deletes records older than 30 days
- **Trace Cleanup**: Deletes records older than 7 days
- **Query**:
  ```sql
  DELETE FROM rag_processing_metrics
  WHERE timestamp < datetime('now', '-30 days');

  DELETE FROM rag_observability_trace
  WHERE timestamp < datetime('now', '-7 days');
  ```

### Manual Cleanup

- **API Endpoint**: `DELETE /api/rag/trace/{request_id}`
- **Purpose**: Immediate deletion of trace data for privacy/compliance
- **Does Not Delete**: Metrics data (metrics always retained for 30 days)

---

## Query Patterns

### Get Metrics for a Request

```sql
SELECT * FROM rag_processing_metrics
WHERE request_id = ?;
```

### Get All Traces for a Request

```sql
SELECT * FROM rag_observability_trace
WHERE request_id = ?
ORDER BY sentence_index, timestamp;
```

### Get Traces for Specific Layer

```sql
SELECT * FROM rag_observability_trace
WHERE request_id = ? AND layer_name = ?
ORDER BY sentence_index, timestamp;
```

### Performance Analytics (Last 7 Days)

```sql
SELECT
  DATE(timestamp) as date,
  AVG(total_time_ms) as avg_total_time,
  AVG(layer_0_time_ms) as avg_layer_0,
  AVG(layer_1_time_ms) as avg_layer_1,
  AVG(layer_2_time_ms) as avg_layer_2,
  AVG(layer_3_time_ms) as avg_layer_3,
  SUM(layer_0_count + layer_1_count + layer_2_count + layer_3_count) as total_entities
FROM rag_processing_metrics
WHERE timestamp >= datetime('now', '-7 days')
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

### Timeout Analysis

```sql
SELECT
  COUNT(*) as total_requests,
  SUM(CASE WHEN layer_0_time_ms >= 500 THEN 1 ELSE 0 END) as layer_0_timeouts,
  SUM(CASE WHEN layer_1_time_ms >= 30000 THEN 1 ELSE 0 END) as layer_1_timeouts,
  SUM(CASE WHEN layer_2_time_ms >= 500 THEN 1 ELSE 0 END) as layer_2_timeouts,
  SUM(CASE WHEN layer_3_time_ms >= 30000 THEN 1 ELSE 0 END) as layer_3_timeouts
FROM rag_processing_metrics
WHERE timestamp >= datetime('now', '-7 days');
```

---

## Storage Estimates

### Metrics Storage

- **Record Size**: ~200 bytes per record
- **Daily Volume**: Depends on usage (example: 1000 requests/day)
- **30-day Storage**: 1000 requests/day × 30 days × 200 bytes ≈ 6 MB

### Trace Storage

- **Record Size**: ~500-2000 bytes per record (varies by trace content)
- **Records per Request**: 4 (one per layer)
- **Daily Volume**: Example: 100 traced requests/day × 4 records × 1000 bytes ≈ 400 KB/day
- **7-day Storage**: 400 KB/day × 7 days ≈ 2.8 MB

**Total Estimated Storage**: ~10 MB for typical usage patterns (scales linearly with request volume)

---

## Pydantic Models

The RAG pipeline uses Pydantic models for request/response validation:

### RAGExtractionRequest

```python
class RAGExtractionRequest(BaseModel):
    """Request model for RAG entity extraction."""
    text: str = Field(min_length=1, description="Input text for extraction")
    enable_trace: bool = Field(default=False, description="Enable detailed tracing")

    @field_validator('text')
    def validate_not_whitespace(cls, v):
        if not v.strip():
            raise ValueError("Text cannot be empty or whitespace only")
        return v
```

### ExtractedEntity

```python
class ExtractedEntity(BaseModel):
    """Extracted entity from RAG pipeline."""
    text: str = Field(min_length=1)
    type: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_layer: str  # "kg", "nlp", "llm", "web"
    sentence_index: int = Field(ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### LayerMetrics

```python
class LayerMetrics(BaseModel):
    """Performance metrics for a single layer."""
    execution_time_ms: float = Field(ge=0.0)
    entities_found: int = Field(ge=0)
    entities_deduplicated: int = Field(default=0, ge=0)
```

### ProcessingMetrics

```python
class ProcessingMetrics(BaseModel):
    """Aggregate pipeline metrics."""
    kg_layer: LayerMetrics
    nlp_layer: LayerMetrics
    llm_layer: LayerMetrics
    web_layer: LayerMetrics
    total_execution_time_ms: float = Field(ge=0.0)
    total_entities: int = Field(ge=0)
    total_sentences: int = Field(ge=0)
```

### RAGExtractionResponse

```python
class RAGExtractionResponse(BaseModel):
    """Response model for RAG entity extraction."""
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    entities: List[ExtractedEntity] = Field(default_factory=list)
    metrics: ProcessingMetrics
    trace_available: bool = Field(default=False)
```

---

## See Also

- [RAG API Specification](./rag_api_specification.md) - API endpoints and usage
- [RAG User Guide](./rag_user_guide.md) - Usage examples and best practices
