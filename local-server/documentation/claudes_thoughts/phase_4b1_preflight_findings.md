# Phase 4B.1 Pre-flight Verification Findings

## Executive Summary

Pre-flight verification confirms the feasibility of Path 1 (rename ExtractionRun → IndividualExtractionRun with intermediate PipelineRun parent) with minimal breaking changes. Wave A's extraction infrastructure is well-isolated and supports clean migration.

## Current State

### 1. ExtractionRun Domain Shape

**Location**: `domain/extraction/entities.py` (line 148)

Dataclass fields:
- `id` (UUID string)
- `source_document_uri` (optional)
- `source_text_hash` (SHA256 audit)
- `pipeline_config_ref` (configuration slug)
- `model` (LLM model name)
- `temperature` (0.0–2.0)
- `tokens_used` (int)
- `duration_ms` (int)
- `triples_extracted` (int)
- `triples_committed` (int)
- `status` (ExtractionRunStatus: PENDING | COMPLETED | FAILED)

**Invariants enforced**:
- temperature must be 0.0–2.0
- tokens_used, duration_ms, triples_extracted, triples_committed >= 0
- triples_committed <= triples_extracted

**Key method**: `ExtractionRun.create(id, source_document_uri, source_text_hash, pipeline_config_ref, model, temperature)` → new run with PENDING status

No rollback mechanism (immutable once constructed; individual extracted triples are revertable via change_events).

### 2. Database Schema (Wave A)

**Inheritance hierarchy**:
```
batch_runs (base table)
├── import_runs (joined-table subclass)
└── extraction_runs (joined-table subclass)
```

**batch_runs** (`adapters/persistence/sqlite/models.py:720`):
- `id` (PK, String(36))
- `created_at` (DateTime with TZ)
- `created_by` (optional)
- `status` (String(20), indexed)
- `affected_entity_ids` (JSON list)
- `run_type` (String(20), discriminator with CHECK constraint: 'import' | 'extraction')

**extraction_runs** (joined-table, line 848):
- `id` (FK to batch_runs.id, PK)
- `source_document_uri` (Text, optional)
- `source_text_hash` (String(64))
- `pipeline_config_ref` (String(100))
- `model` (String(100))
- `temperature` (Float)
- `tokens_used` (Integer)
- `duration_ms` (Integer)
- `triples_extracted` (Integer)
- `triples_committed` (Integer)

**Constraints**:
- CHECK temperature >= 0.0 AND <= 2.0
- CHECK tokens_used, duration_ms, triples_extracted >= 0
- CHECK triples_committed <= triples_extracted

**change_events integration**:
- `change_events.batch_run_id` (FK to batch_runs.id) is populated by extraction flow
- Verified via grep: `batch_run_id` column exists and is indexed

### 3. Current API

**Endpoint**: `POST /api/extraction/extract` (line 254, `adapters/web/extraction_routes.py`)

**Request**: `ExtractTripleRequest`
- `text` (str)
- `ontology_id` (str)
- `options` (ExtractionOptions with model, temperature)

**Response**: `ExtractTripleResponse`
- `triples` (list[ExtractedTriple])
- `warnings` (list[str])
- `metadata` (ExtractionMetadata: model, tokens_used, duration_ms)

**Calling sequence**:
1. FastAPI route receives request
2. Calls `ExtractionService.extract_triples(text, ontology_id, model, temperature)`
3. Returns JSON response

**Error handling**:
- InvalidInputError → HTTP 400
- LayerExecutionError → HTTP 500
- ExtractionError → HTTP 400

### 4. API Callers

**Backend Tests**:
- `tests/integration/routes/test_extraction_routes.py` — multiple test cases for POST /api/extraction/extract
- Tests verify 200 response, structure, metadata, validation error handling

**Frontend**:
- `ux/documentation/openapi.json` — endpoint in OpenAPI spec
- `ux/src/api/types/index.ts` — generated types

**External/Harness**:
- Text2KGBench (Phase 4 Wave A harness) calls this endpoint as primary extraction path
- Verified via `phase-4-graph-extraction.md` references in issue description

### 5. Configuration Files

**Path**: `configs/extraction-default.json`

```json
{
  "provider": "anthropic",
  "model": "claude-opus-4-7",
  "temperature": 0.0,
  "max_tokens": 4096,
  "system_prompt": "You are a knowledge graph extraction assistant...",
  "user_prompt_template": "Extract triples from the following text...",
  "seed": null
}
```

**Schema**:
- `provider` (string) — "anthropic" (currently; could expand)
- `model` (string) — model identifier
- `temperature` (float) — 0.0-2.0
- `max_tokens` (int)
- `system_prompt` (string)
- `user_prompt_template` (string with `{ontology}` and `{text}` placeholders)
- `seed` (null | int)

**Usage**:
- Loaded at startup; referenced by `pipeline_config_ref` in extraction runs
- Migration path: **Option A** — keep in place, configuration registry reads them

### 6. Extraction Iteration Log

**Path**: `logs/extraction-iteration-log.md`

Wave A phase tracking document recording iterations and decisions.

**Migration path**: **Option A** — rename to `pipeline-iteration-log.md`, partition by pipeline type inside file

### 7. LLM Client Architecture

**Existing LLMProvider port** (`domain/pipeline/ports.py:59`):
```python
class LLMProvider(Protocol):
    def complete(
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        ...
```

**Current Implementations**:
- `adapters/llm/openai_provider.py` — OpenAI (GPT-4, GPT-4o, GPT-3.5-turbo, etc.)
- `adapters/llm/anthropic_provider.py` — Anthropic (Claude models)

**Router**: `adapters/llm/provider_router.py` — routes based on model identifier to appropriate provider

**Existing OpenRouter Plan**:
- Already documented at `documentation/claudes_thoughts/openrouter_implementation_plan.md`
- Not yet implemented
- Specifies adapter structure, API details, error handling

**Configuration**: Models are passed via `config.json` extraction config; LLM client is instantiated in app.py composition root

### 8. Python Version & Dependencies

**Target Python**: 3.11 (from pyproject.toml `target-version = ['py311']`)

**LangGraph Status**:
- NOT currently in `requirements.txt`
- Must be added with Python 3.11 compatibility
- Latest LangGraph (0.2.x) supports Python 3.11–3.12
- Recommended version pin: `langgraph>=0.2.0,<1.0.0`

**Other relevant dependencies**:
- `sqlalchemy[mypy]>=2.0` — for joined-table inheritance
- `anthropic`, `openai` — existing LLM clients
- `networkx>=3.1` — graph operations
- `duckdb`, `pyarrow` — for sync/remote operations

## Wave A Integration Decisions

### Path Selection: Path 1 (Rename)

**Rationale**:
- Cleaner long-term architecture (no dual structures)
- Minimal code changes once migration runs
- Aligns with Phase 3 precedent (BatchRun joined-table pattern)
- ExtractionRun name ambiguity resolved (individual vs. schema types)

**Implementation**:
1. Introduce `PipelineRun` as intermediate joined-table between `BatchRun` and subtypes
2. Migrate Wave A's `ExtractionRun` → `IndividualExtractionRun`
3. Alembic migration: rename `extraction_runs` table → `individual_extraction_runs`, add `pipeline_runs` base table
4. Update domain entity class name
5. Update repository queries
6. Regression test confirms Wave A behavior preserved

### Route Backwards Compatibility: Option B (Thin Proxy)

**Rationale**:
- Maintains existing API surface (no breaking changes for harness or frontend)
- Deprecation header signals future change
- Cleaner than aliasing under generic endpoint

**Implementation**:
```python
@router.post("/extraction/extract", deprecated=True)
async def extract_triples_legacy(request, service):
    """Deprecated: use POST /api/pipelines/individual-extraction/run instead."""
    # Delegate to new endpoint with Deprecation header
    return await extract_triples_new(...)
```

### Configuration Files: Option A (Keep in Place)

**Rationale**:
- Extraction configs are well-tested and stable
- Registry can load them at startup
- No need to re-author in alternate format
- Reduces migration complexity

**Implementation**:
- Configuration registry reads `configs/extraction-*.json` files
- Loads into PipelineConfigurationRegistry as Individual Extraction configurations
- No file format change required

### Iteration Log: Option A (Rename and Partition)

**Rationale**:
- Single source of truth for all pipeline iterations
- Easier to track cross-type dependencies and lessons learned
- Clean organization by pipeline type

**Implementation**:
- Rename `logs/extraction-iteration-log.md` → `logs/pipeline-iteration-log.md`
- Add top-level sections: `## Individual Extraction`, `## Schema Extraction`, etc.
- Wave A content stays under Individual Extraction section

## Change Events Integration

**Status**: Confirmed populated

`change_events.batch_run_id` is populated by Wave A's extraction flow and indexed (`idx_batch_run_id`).

Migration maintains this invariant: every PipelineRun has a batch_run_id in change_events.

## Migration Feasibility

**Alembic Strategy**:

1. **Create pipeline_runs joined-table base** (before renaming extraction_runs):
   ```sql
   CREATE TABLE pipeline_runs (
     id STRING(36) PRIMARY KEY,
     batch_run_id STRING(36) NOT NULL FK(batch_runs.id),
     pipeline_type STRING(20) NOT NULL,
     implementation_id STRING(100),
     configuration_ref STRING(100),
     input_summary JSON,
     output_summary JSON,
     llm_metadata JSON,
     CHECK (pipeline_type IN (...five types...))
   );
   ```

2. **Insert existing extraction_runs data into pipeline_runs + individual_extraction_runs**:
   ```sql
   INSERT INTO pipeline_runs SELECT ...;
   INSERT INTO individual_extraction_runs SELECT ...;
   ```

3. **Drop extraction_runs table** (or keep as view for compatibility)

4. **Update CHECK constraint on batch_runs.run_type**:
   ```sql
   -- Old: ('import', 'extraction')
   -- New: ('import', 'pipeline')
   ```

**Rollback**: Reverse migration documented in migration script comments.

## Summary

All pre-flight gates passed:
- ✅ ExtractionRun shape documented; no blocking dependencies
- ✅ Database schema well-structured for migration
- ✅ API has isolated callers (harness, tests, frontend types)
- ✅ Configuration files are stable and can be adopted by registry
- ✅ LLM client port exists and supports OpenRouter addition
- ✅ Python version compatible with LangGraph
- ✅ Change events integration confirmed

**Recommended decisions**: Path 1, Option B, Option A, Option A (all long-term clean paths)

**Proceeding with implementation** under these decisions.
