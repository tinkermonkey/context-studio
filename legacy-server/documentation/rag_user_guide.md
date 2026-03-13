# RAG Pipeline User Guide

## Introduction

The RAG (Retrieval-Augmented Generation) Pipeline is an intelligent entity extraction system that identifies concepts, technologies, and domain-specific terms from text. It combines knowledge graph lookups, LLM reasoning, NLP analysis, and web search to provide comprehensive entity recognition.

### Key Features

- **Four-Layer Architecture**: Progressive entity discovery through multiple specialized layers
- **Graceful Degradation**: Pipeline continues even if individual layers fail or timeout
- **High Accuracy**: 90%+ similarity-based deduplication ensures clean results
- **Performance Optimized**: 5-15s typical response time, <120s maximum
- **Comprehensive Observability**: Detailed metrics and traces for debugging
- **Configurable**: Adjustable timeouts, thresholds, and parameters

---

## Quick Start

### Basic Entity Extraction

```python
import requests

response = requests.post(
    "http://localhost:8000/api/rag/extract",
    json={
        "text": "Machine learning uses neural networks to process data efficiently.",
        "enable_trace": False
    }
)

result = response.json()
print(f"Found {result['metrics']['total_entities']} entities")
for entity in result['entities']:
    print(f"  - {entity['text']} ({entity['type']}) from {entity['source_layer']}")
```

**Output:**
```
Found 3 entities
  - machine learning (CONCEPT) from llm
  - neural networks (CONCEPT) from kg
  - data (CONCEPT) from nlp
```

---

## Understanding the Pipeline

### Layer 0: Knowledge Graph Context (KG)

**Purpose**: Retrieve relevant concepts from your knowledge graph

**Process:**
1. Extract noun phrases and named entities using spaCy
2. Generate embeddings for each phrase
3. Query knowledge graph for top-k most similar nodes
4. Return context for downstream layers

**When to Use:**
- You have a well-populated knowledge graph
- Input text relates to domains in your KG
- You want fastest possible entity recognition

**Performance**: Target <500ms (relaxed to <2s in test environments)

**Example Output:**
```json
{
  "entities": [
    {
      "text": "machine learning",
      "type": "CONCEPT",
      "confidence": 0.95,
      "source_layer": "kg",
      "metadata": {
        "kg_node_id": "kg-12345",
        "definition": "A subset of AI focused on learning from data"
      }
    }
  ]
}
```

### Layer 1: LLM Extraction

**Purpose**: Use LLM reasoning to identify entities with KG context

**Process:**
1. Format KG context nodes as prompt context
2. Send text + context to LLM for entity extraction
3. Parse and validate LLM response
4. Return high-confidence entities

**When to Use:**
- You need deeper semantic understanding
- Text contains complex or domain-specific concepts
- KG alone doesn't provide sufficient coverage

**Performance**: Target <30s

**Configuration:**
```python
# Uses pipeline flavor configuration
response = requests.post(
    "http://localhost:8000/api/rag/config/update",
    json={"timeout_layer_1": 45.0}  # Increase if LLM is slow
)
```

### Layer 2: spaCy Gap Detection (NLP)

**Purpose**: Identify noun phrases missed by KG and LLM

**Process:**
1. Extract all noun phrases using spaCy
2. Compare with KG + LLM results to find gaps
3. Prioritize gaps based on syntactic role:
   - **CRITICAL**: Subjects, objects (nsubj, dobj)
   - **IMPORTANT**: Complements, modifiers (nsubjpass, acomp)
   - **CONTEXTUAL**: Adjectives, low-importance modifiers
4. Filter using TF-IDF scores
5. Return high-priority gaps

**When to Use:**
- KG coverage is incomplete
- Text contains new or emerging concepts
- You want comprehensive entity extraction

**Performance**: Target <500ms (relaxed to <2s in test environments)

**Configuration:**
```python
response = requests.post(
    "http://localhost:8000/api/rag/config/update",
    json={"tf_idf_threshold": 0.20}  # Higher = stricter filtering
)
```

### Layer 3: Concept Resolution (Web Search)

**Purpose**: Resolve gaps through KG similarity search or web search

**Process:**
1. For each gap, search KG with full re-embedding
2. If no match (< threshold), perform web search for CRITICAL/IMPORTANT gaps
3. Extract definitions from web results
4. Return resolved concepts with confidence scores

**When to Use:**
- You need definitions for unknown concepts
- KG doesn't contain recent/emerging terms
- You want maximum coverage

**Performance**: Target <30s

**Rate Limiting:**
- 5 web searches per minute (configurable)
- Max 10 searches per request (configurable)

**Configuration:**
```python
# In RAG processor initialization
from rag.processors.web_search import RateLimitedWebSearchClient

web_client = RateLimitedWebSearchClient(
    rate_limit_per_minute=10,  # Increase rate limit
    max_attempts_per_session=20  # Allow more searches
)
```

---

## Common Use Cases

### Use Case 1: Extract Concepts from Research Paper

```python
import requests

# Multi-paragraph research abstract
text = """
Machine learning has revolutionized computer vision through deep neural networks.
Convolutional neural networks (CNNs) excel at image classification tasks, while
recurrent neural networks (RNNs) handle sequential data. Transfer learning enables
models pre-trained on large datasets like ImageNet to be fine-tuned for specific
tasks with limited training data. Recent advances in attention mechanisms and
transformer architectures have further improved performance across diverse domains.
"""

response = requests.post(
    "http://localhost:8000/api/rag/extract",
    json={
        "text": text,
        "enable_trace": False
    }
)

entities = response.json()['entities']

# Group by layer
by_layer = {}
for entity in entities:
    layer = entity['source_layer']
    if layer not in by_layer:
        by_layer[layer] = []
    by_layer[layer].append(entity['text'])

print("Entities by layer:")
for layer, texts in by_layer.items():
    print(f"  {layer}: {', '.join(texts)}")
```

**Expected Output:**
```
Entities by layer:
  kg: machine learning, deep neural networks, computer vision
  llm: CNNs, RNNs, transfer learning, attention mechanisms
  web: ImageNet, transformer architectures
```

### Use Case 2: Debug Performance Issues with Trace

```python
import requests
import json

response = requests.post(
    "http://localhost:8000/api/rag/extract",
    json={
        "text": "Quantum computing uses qubits for superposition and entanglement.",
        "enable_trace": True  # Enable detailed tracing
    }
)

request_id = response.json()['request_id']

# Retrieve trace data
trace_response = requests.get(f"http://localhost:8000/api/rag/trace/{request_id}")
traces = trace_response.json()['traces']

# Analyze Layer 1 (LLM) performance
for trace in traces:
    if trace['layer_name'] == 'llm_extraction':
        data = trace['trace_data']
        print(f"LLM Token Usage:")
        print(f"  Prompt tokens: {data['token_usage']['prompt_tokens']}")
        print(f"  Completion tokens: {data['token_usage']['completion_tokens']}")
        print(f"  KG context size: {data['kg_context_size']}")
        print(f"  Entities extracted: {data['entities_extracted']}")
```

### Use Case 3: Batch Processing with Timeouts

```python
import requests
import asyncio
import aiohttp

# Configure aggressive timeouts for batch processing
config_response = requests.post(
    "http://localhost:8000/api/rag/config/update",
    json={
        "timeout_layer_0": 0.3,  # 300ms
        "timeout_layer_1": 20.0,  # 20s
        "timeout_layer_2": 0.3,  # 300ms
        "timeout_layer_3": 20.0   # 20s
    }
)

async def extract_batch(texts):
    """Process multiple texts concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for text in texts:
            task = session.post(
                "http://localhost:8000/api/rag/extract",
                json={"text": text, "enable_trace": False}
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        return [await r.json() for r in responses]

# Process 10 paragraphs concurrently
paragraphs = [...]  # Your text data
results = asyncio.run(extract_batch(paragraphs))

for i, result in enumerate(results):
    print(f"Paragraph {i}: {result['metrics']['total_entities']} entities in {result['metrics']['total_execution_time_ms']}ms")
```

### Use Case 4: Monitor Performance Over Time

```python
import requests
from datetime import datetime, timedelta

# Get metrics for recent requests
# (In production, query operations.db directly)

recent_request_ids = [...]  # Collect from your logs

performance_data = []
for request_id in recent_request_ids:
    metrics_response = requests.get(f"http://localhost:8000/api/rag/metrics/{request_id}")
    if metrics_response.status_code == 200:
        metrics = metrics_response.json()
        performance_data.append({
            'total_time': metrics['total_time_ms'],
            'layer_0_time': metrics['layer_0']['time_ms'],
            'layer_1_time': metrics['layer_1']['time_ms'],
            'layer_2_time': metrics['layer_2']['time_ms'],
            'layer_3_time': metrics['layer_3']['time_ms'],
            'total_entities': sum([
                metrics['layer_0']['count'],
                metrics['layer_1']['count'],
                metrics['layer_2']['count'],
                metrics['layer_3']['count']
            ])
        })

# Analyze
import statistics
total_times = [d['total_time'] for d in performance_data]
print(f"Average total time: {statistics.mean(total_times):.2f}ms")
print(f"Median total time: {statistics.median(total_times):.2f}ms")
print(f"95th percentile: {statistics.quantiles(total_times, n=20)[18]:.2f}ms")
```

---

## Configuration Guide

### Performance Tuning

#### Optimize for Speed

```python
# Prioritize speed over coverage
response = requests.post(
    "http://localhost:8000/api/rag/config/update",
    json={
        "timeout_layer_0": 0.2,  # Very fast KG lookup
        "timeout_layer_1": 15.0,  # Shorter LLM timeout
        "timeout_layer_2": 0.2,  # Fast NLP
        "timeout_layer_3": 10.0,  # Limited web search time
        "kg_top_k": 20,  # Fewer KG nodes (faster)
        "tf_idf_threshold": 0.25  # Stricter gap filtering
    }
)
```

**Expected**: ~5-10s for typical inputs

#### Optimize for Accuracy

```python
# Prioritize accuracy and coverage
response = requests.post(
    "http://localhost:8000/api/rag/config/update",
    json={
        "timeout_layer_0": 1.0,  # More time for KG
        "timeout_layer_1": 45.0,  # More time for LLM reasoning
        "timeout_layer_2": 1.0,  # Thorough NLP analysis
        "timeout_layer_3": 45.0,  # More web searches
        "kg_top_k": 100,  # More KG context
        "tf_idf_threshold": 0.10,  # Less filtering
        "dedup_similarity_threshold": 0.95  # Stricter deduplication
    }
)
```

**Expected**: ~20-60s for typical inputs

### Deduplication Tuning

```python
# Aggressive deduplication (more merging)
response = requests.post(
    "http://localhost:8000/api/rag/config/update",
    json={"dedup_similarity_threshold": 0.85}
)
# "Machine Learning" and "machine learning" will merge
# "ML" and "Machine Learning" will merge

# Conservative deduplication (less merging)
response = requests.post(
    "http://localhost:8000/api/rag/config/update",
    json={"dedup_similarity_threshold": 0.95}
)
# Only exact/near-exact matches merge
# "ML" and "Machine Learning" stay separate
```

---

## Trace Interpretation

### Reading KG Context Traces

```json
{
  "layer_name": "kg_context",
  "trace_data": {
    "extracted_phrases": [
      {"text": "machine learning", "start": 0, "end": 16}
    ],
    "kg_nodes_found": 5,
    "similarity_scores": [0.95, 0.88, 0.82, 0.79, 0.75]
  }
}
```

**Interpretation:**
- `kg_nodes_found`: 5 → Good KG coverage
- `similarity_scores[0]`: 0.95 → Very high confidence match
- **Action**: If `similarity_scores` are all low (<0.7), consider expanding your KG

### Reading LLM Extraction Traces

```json
{
  "layer_name": "llm_extraction",
  "trace_data": {
    "entities_extracted": 8,
    "kg_context_size": 5,
    "token_usage": {
      "prompt_tokens": 450,
      "completion_tokens": 120
    }
  }
}
```

**Interpretation:**
- `entities_extracted`: 8 → LLM found many concepts
- `kg_context_size`: 5 → LLM had good context
- `prompt_tokens`: 450 → Moderate prompt size
- **Action**: If `prompt_tokens` > 1000, KG context may be too large (reduce `kg_top_k`)

### Reading Gap Detection Traces

```json
{
  "layer_name": "spacy_gap",
  "trace_data": {
    "gaps_detected": 3,
    "total_noun_phrases": 12,
    "filtered_by_tfidf": 2,
    "priority_distribution": {
      "CRITICAL": 0,
      "IMPORTANT": 2,
      "CONTEXTUAL": 1
    }
  }
}
```

**Interpretation:**
- `total_noun_phrases`: 12 → Many candidates found
- `filtered_by_tfidf`: 2 → TF-IDF filtered out low-value phrases
- `CRITICAL`: 0 → No critical gaps (good KG+LLM coverage)
- **Action**: If many gaps, consider expanding KG or adjusting `tf_idf_threshold`

### Reading Concept Resolution Traces

```json
{
  "layer_name": "concept_resolution",
  "trace_data": {
    "gaps_resolved": 2,
    "gaps_unresolved": 1,
    "web_searches_performed": 1,
    "cached_kg_hits": 0,
    "full_kg_hits": 1,
    "resolution_methods": {
      "FULL_KG": 1,
      "WEB_SEARCH": 1,
      "UNRESOLVED": 1
    }
  }
}
```

**Interpretation:**
- `gaps_resolved`: 2 out of 3 → Good resolution rate
- `web_searches_performed`: 1 → Limited web API usage
- `UNRESOLVED`: 1 → One gap couldn't be resolved (likely CONTEXTUAL priority)
- **Action**: If many `UNRESOLVED`, consider populating KG or increasing web search limits

---

## Best Practices

### 1. Start Without Trace, Enable for Debugging

```python
# Normal usage (faster, no storage overhead)
response = requests.post(url, json={"text": text, "enable_trace": False})

# Debugging (slower, stores trace data)
response = requests.post(url, json={"text": text, "enable_trace": True})
```

### 2. Monitor Timeout Rates

```python
# Check if layers are timing out frequently
metrics = response.json()['metrics']

if metrics['kg_layer']['execution_time_ms'] >= 500:
    print("WARNING: Layer 0 may have timed out")

if metrics['llm_layer']['execution_time_ms'] >= 30000:
    print("WARNING: Layer 1 may have timed out")
```

### 3. Batch Processing Strategy

```python
# Process in batches to avoid overwhelming the server
BATCH_SIZE = 10

for i in range(0, len(texts), BATCH_SIZE):
    batch = texts[i:i+BATCH_SIZE]
    results = await extract_batch(batch)
    # Process results
    await asyncio.sleep(5)  # Brief pause between batches
```

### 4. Clean Up Traces After Debugging

```python
# Delete trace data when no longer needed
requests.delete(f"http://localhost:8000/api/rag/trace/{request_id}")
```

### 5. Populate Knowledge Graph for Best Performance

- Add domain-specific terms to your KG
- Include definitions and embeddings
- Higher KG coverage → Faster, more accurate results

---

## Troubleshooting

### Problem: Very Slow Responses (>60s)

**Possible Causes:**
- LLM API is slow
- Too many web searches
- Large KG query

**Solutions:**
1. Reduce Layer 1 timeout: `timeout_layer_1: 20.0`
2. Reduce Layer 3 timeout: `timeout_layer_3: 15.0`
3. Reduce KG context: `kg_top_k: 30`
4. Enable trace to identify bottleneck

### Problem: Missing Expected Entities

**Possible Causes:**
- KG doesn't contain concepts
- LLM timeout
- Gap filtering too aggressive

**Solutions:**
1. Check trace data for gaps detected
2. Lower TF-IDF threshold: `tf_idf_threshold: 0.10`
3. Increase Layer 1 timeout: `timeout_layer_1: 45.0`
4. Populate KG with missing concepts

### Problem: Too Many Duplicate Entities

**Possible Causes:**
- Deduplication threshold too high
- Entities from different layers with slight variations

**Solutions:**
1. Lower threshold: `dedup_similarity_threshold: 0.85`
2. Check trace data to see which layers are producing duplicates

### Problem: High Token Usage (Cost)

**Possible Causes:**
- Too much KG context in LLM prompt
- Very long input text

**Solutions:**
1. Reduce KG context: `kg_top_k: 20`
2. Split long texts into smaller chunks
3. Check trace for `prompt_tokens` count

---

## API Reference

For complete API documentation, see:
- [RAG API Specification](./rag_api_specification.md)
- [RAG Data Model](./rag_data_model.md)

---

## Support and Feedback

For issues or questions:
1. Check trace data for debugging insights
2. Review metrics for performance bottlenecks
3. Adjust configuration parameters
4. Consult API documentation

Typical response times:
- **Single sentence**: <5s
- **1 paragraph**: 5-15s
- **2-3 paragraphs**: 10-30s
- **4-5 paragraphs**: 15-60s
- **Maximum**: 120s (hard limit)
