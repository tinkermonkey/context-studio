# RAG Pipeline API Specification

## Overview

The RAG (Retrieval-Augmented Generation) Pipeline API provides intelligent entity extraction from text using a four-layer architecture that combines knowledge graph lookups, LLM analysis, NLP gap detection, and web search for comprehensive concept recognition.

## Base URL

```
/api/rag
```

---

## Endpoints

### 1. Extract Entities

**POST** `/api/rag/extract`

Extracts entities and concepts from input text using the four-layer RAG pipeline.

#### Request Body

```json
{
  "text": "string (required, min length: 1)",
  "enable_trace": "boolean (optional, default: false)"
}
```

**Fields:**
- `text`: Input paragraph or paragraphs for entity extraction (cannot be empty or whitespace-only)
- `enable_trace`: Whether to capture detailed trace data for debugging (7-day retention)

#### Response

**Status:** `200 OK`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "entities": [
    {
      "text": "machine learning",
      "type": "CONCEPT",
      "confidence": 0.95,
      "source_layer": "llm",
      "sentence_index": 0,
      "metadata": {
        "kb_id": "Q1234",
        "definition": "A subset of AI...",
        "resolution_method": "llm_extraction"
      }
    }
  ],
  "metrics": {
    "kg_layer": {
      "execution_time_ms": 125.5,
      "entities_found": 5,
      "entities_deduplicated": 0
    },
    "nlp_layer": {
      "execution_time_ms": 85.2,
      "entities_found": 3,
      "entities_deduplicated": 1
    },
    "llm_layer": {
      "execution_time_ms": 2500.0,
      "entities_found": 8,
      "entities_deduplicated": 2
    },
    "web_layer": {
      "execution_time_ms": 1200.0,
      "entities_found": 2,
      "entities_deduplicated": 0
    },
    "total_execution_time_ms": 3910.7,
    "total_entities": 15,
    "total_sentences": 3
  },
  "trace_available": false
}
```

**Error Responses:**
- `400 Bad Request`: Invalid input (empty text, invalid parameters)
- `422 Unprocessable Entity`: Validation error (whitespace-only text)
- `500 Internal Server Error`: Pipeline execution failure

#### Entity Fields

- `text`: Extracted entity text
- `type`: Entity type (CONCEPT, PERSON, ORG, LOCATION, TECHNOLOGY, etc.)
- `confidence`: Confidence score (0.0 to 1.0)
- `source_layer`: Layer that extracted the entity ("kg", "nlp", "llm", "web")
- `sentence_index`: Sentence number where entity was found (0-indexed)
- `metadata`: Additional contextual information (optional)

#### Metrics Fields

Each layer provides:
- `execution_time_ms`: Time spent in this layer (milliseconds)
- `entities_found`: Number of entities discovered by this layer
- `entities_deduplicated`: Number of duplicates removed

---

### 2. Get Metrics

**GET** `/api/rag/metrics/{request_id}`

Retrieves performance metrics for a specific extraction request.

#### Path Parameters

- `request_id`: UUID of the extraction request

#### Response

**Status:** `200 OK`

```json
{
  "id": "metrics-uuid",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "input_text": "Machine learning is...",
  "layer_0": {
    "time_ms": 125,
    "count": 5
  },
  "layer_1": {
    "time_ms": 2500,
    "count": 8
  },
  "layer_2": {
    "time_ms": 85,
    "count": 3
  },
  "layer_3": {
    "time_ms": 1200,
    "count": 2
  },
  "total_time_ms": 3910,
  "timestamp": "2025-10-16T22:30:00Z"
}
```

**Error Responses:**
- `404 Not Found`: No metrics found for the given request_id

**Note:** Metrics are retained for 30 days.

---

### 3. Get Trace Data

**GET** `/api/rag/trace/{request_id}`

Retrieves detailed trace data for a specific extraction request (if trace was enabled).

#### Path Parameters

- `request_id`: UUID of the extraction request

#### Response

**Status:** `200 OK`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "traces": [
    {
      "id": "trace-uuid-1",
      "sentence_index": 0,
      "layer_name": "kg_context",
      "operation_type": "output",
      "trace_data": {
        "extracted_phrases": ["machine learning", "neural networks"],
        "kg_nodes_found": 5,
        "similarity_scores": [0.95, 0.88, 0.82, 0.79, 0.75]
      },
      "timestamp": "2025-10-16T22:30:00.123Z"
    },
    {
      "id": "trace-uuid-2",
      "sentence_index": 0,
      "layer_name": "llm_extraction",
      "operation_type": "output",
      "trace_data": {
        "entities_extracted": 8,
        "kg_context_size": 5,
        "token_usage": {"prompt_tokens": 150, "completion_tokens": 75}
      },
      "timestamp": "2025-10-16T22:30:02.650Z"
    }
  ]
}
```

**Error Responses:**
- `404 Not Found`: No trace data found (trace was not enabled or data was deleted)

**Note:** Trace data is retained for 7 days.

---

### 4. Get Trace by Layer

**GET** `/api/rag/trace/{request_id}/layer/{layer_name}`

Retrieves trace data for a specific layer of an extraction request.

#### Path Parameters

- `request_id`: UUID of the extraction request
- `layer_name`: Name of the layer ("kg_context", "llm_extraction", "spacy_gap", "concept_resolution")

#### Response

**Status:** `200 OK`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "layer_name": "kg_context",
  "traces": [
    {
      "id": "trace-uuid-1",
      "sentence_index": 0,
      "operation_type": "output",
      "trace_data": {
        "extracted_phrases": ["machine learning"],
        "kg_nodes_found": 5
      },
      "timestamp": "2025-10-16T22:30:00.123Z"
    }
  ]
}
```

**Error Responses:**
- `400 Bad Request`: Invalid layer name
- `404 Not Found`: No trace data found for this layer

**Valid Layer Names:**
- `kg_context`: Layer 0 - Knowledge graph context preparation
- `llm_extraction`: Layer 1 - LLM-based entity extraction
- `spacy_gap`: Layer 2 - spaCy gap detection
- `concept_resolution`: Layer 3 - Concept resolution via web search

---

### 5. Delete Trace Data

**DELETE** `/api/rag/trace/{request_id}`

Deletes trace data for a specific extraction request (for privacy/cleanup).

#### Path Parameters

- `request_id`: UUID of the extraction request

#### Response

**Status:** `200 OK`

```json
{
  "message": "Trace data deleted successfully",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "traces_deleted": 4
}
```

**Error Responses:**
- `404 Not Found`: No trace data found for the given request_id

---

### 6. Update Configuration

**POST** `/api/rag/config/update`

Updates RAG pipeline configuration parameters (timeouts, thresholds, etc.).

#### Request Body

```json
{
  "timeout_layer_0": 0.5,
  "timeout_layer_1": 30.0,
  "timeout_layer_2": 0.5,
  "timeout_layer_3": 30.0,
  "dedup_similarity_threshold": 0.90,
  "kg_top_k": 50,
  "tf_idf_threshold": 0.15
}
```

**Configuration Parameters:**

| Parameter | Type | Range | Default | Description |
|-----------|------|-------|---------|-------------|
| `timeout_layer_0` | float | > 0 | 0.5 | Layer 0 timeout (seconds) |
| `timeout_layer_1` | float | > 0 | 30.0 | Layer 1 timeout (seconds) |
| `timeout_layer_2` | float | > 0 | 0.5 | Layer 2 timeout (seconds) |
| `timeout_layer_3` | float | > 0 | 30.0 | Layer 3 timeout (seconds) |
| `dedup_similarity_threshold` | float | 0.0-1.0 | 0.90 | Entity deduplication threshold |
| `kg_top_k` | int | > 0 | 50 | Number of KG nodes to retrieve |
| `tf_idf_threshold` | float | 0.0-1.0 | 0.15 | TF-IDF threshold for gap filtering |

#### Response

**Status:** `200 OK`

```json
{
  "message": "Configuration updated successfully",
  "updated_config": {
    "timeout_layer_0": 0.5,
    "dedup_similarity_threshold": 0.90
  },
  "current_config": {
    "timeout_layer_0": 0.5,
    "timeout_layer_1": 30.0,
    "timeout_layer_2": 0.5,
    "timeout_layer_3": 30.0,
    "dedup_similarity_threshold": 0.90,
    "kg_top_k": 50,
    "tf_idf_threshold": 0.15
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid configuration keys or values (negative timeouts, threshold out of range, etc.)

---

## Architecture Overview

### Four-Layer Processing Pipeline

1. **Layer 0: KG Context Preparation** (target: <500ms)
   - Extracts noun phrases and named entities using spaCy
   - Generates embeddings and queries knowledge graph
   - Returns top-k most similar KG nodes for context

2. **Layer 1: LLM Extraction** (target: <30s)
   - Uses KG context to inform LLM entity extraction
   - Identifies concepts, relationships, and domain-specific entities
   - Provides high-confidence extractions with LLM reasoning

3. **Layer 2: spaCy Gap Detection** (target: <500ms)
   - Identifies noun phrases not recognized by KG or LLM
   - Prioritizes gaps based on syntactic role (CRITICAL, IMPORTANT, CONTEXTUAL)
   - Uses TF-IDF scoring to filter low-importance phrases

4. **Layer 3: Concept Resolution** (target: <30s)
   - Resolves gaps through KG similarity search
   - Falls back to web search for high-priority unresolved gaps
   - Provides definitions and confidence scores

### Graceful Degradation

- Each layer has independent timeout enforcement
- Pipeline continues if individual layers fail or timeout
- Empty results are returned for failed layers
- Total pipeline budget: 120 seconds maximum

### Deduplication

- Entities are deduplicated at 90% text similarity (configurable)
- Higher-priority layers take precedence (LLM > KG > Web > NLP)
- Deduplication occurs after all layers complete

---

## Performance Targets

| Input Size | Target Time | Max Time |
|------------|-------------|----------|
| Single sentence | <5s | 15s |
| 1 paragraph | 5-15s | 30s |
| 2-3 paragraphs | 10-30s | 60s |
| 4-5 paragraphs | 15-60s | 120s |

**Note:** Actual performance depends on:
- Knowledge graph size
- LLM response time
- Network latency for web searches
- Input text complexity

---

## Rate Limiting

- Web search: 5 queries/minute (configurable)
- Max web searches per request: 10 (configurable)

---

## Data Retention

- **Metrics**: 30 days
- **Traces**: 7 days
- Automatic cleanup runs daily
- Manual trace deletion available via DELETE endpoint

---

## Example Usage

### Basic Entity Extraction

```bash
curl -X POST http://localhost:8000/api/rag/extract \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Machine learning algorithms use neural networks to process data.",
    "enable_trace": false
  }'
```

### Extraction with Trace

```bash
curl -X POST http://localhost:8000/api/rag/extract \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Deep learning revolutionized computer vision and NLP.",
    "enable_trace": true
  }'
```

### Retrieve Trace Data

```bash
curl -X GET http://localhost:8000/api/rag/trace/550e8400-e29b-41d4-a716-446655440000
```

### Update Configuration

```bash
curl -X POST http://localhost:8000/api/rag/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "timeout_layer_1": 45.0,
    "dedup_similarity_threshold": 0.85
  }'
```

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server-side error

Error responses include a `detail` field with a human-readable error message:

```json
{
  "detail": "Text cannot be empty or whitespace only"
}
```

---

## See Also

- [RAG Data Model](./rag_data_model.md) - Database schema and data structures
- [RAG User Guide](./rag_user_guide.md) - Usage examples and best practices
