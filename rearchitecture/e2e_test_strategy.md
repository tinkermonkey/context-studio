# Context Studio: Back-End E2E Test Strategy

## Module-Level Verification with Real Services

**Date:** 2026-03-13
**Companion Documents:** `architecture_design.md`, `transformation_roadmap.md`
**Scope:** Back-end only. No UX. Real external services (LLM, NLP, reference APIs).

---

## 1. What This Document Covers

Unit and integration tests are handled by the existing SDLC. This document defines the **end-to-end test strategy for the back-end**, focused on answering one question per phase: *"Does this actually work when everything is wired together with real services?"*

The tests described here sit between integration tests (which mock external services) and full UX E2E tests (which add browser complexity). They exercise complete back-end workflows through the FastAPI HTTP API using real databases, real embeddings, real NLP pipelines, real LLM calls, and real reference API queries.

### Testing Pyramid Position

```
        ╱╲
       ╱  ╲         UX E2E (Playwright/Cypress — not in scope)
      ╱────╲
     ╱      ╲       ◄── THIS DOCUMENT: Back-end E2E
    ╱────────╲           Real services, real DB, HTTP API boundary
   ╱          ╲
  ╱────────────╲     Integration (mocked externals, real DB)
 ╱              ╲
╱────────────────╲   Unit (no I/O, no DB)
```

### Principles

1. **Real services, not mocks.** Tests authenticate against real LLM providers, reference APIs, and the NLP pipeline. The config provides valid API keys.
2. **HTTP boundary.** All tests interact through `TestClient` or actual HTTP calls — never by importing domain services directly.
3. **Full database lifecycle.** Tests use real SQLite databases with migrations, not in-memory shortcuts.
4. **Workflow-oriented.** Each test exercises a complete user-meaningful workflow, not an isolated operation.
5. **Tolerant of latency.** External services are slow. Tests use generous timeouts and polling patterns, not `time.sleep`.
6. **Deterministic where possible.** Use stable, well-known inputs that produce predictable outputs from external services.
7. **Self-cleaning.** Each test suite creates its own dataset/database and tears it down after.

---

## 2. Test Infrastructure

### 2.1 E2E Test Configuration

```python
# tests/e2e/conftest.py

import pytest
from fastapi.testclient import TestClient
from app import create_app

@pytest.fixture(scope="module")
def e2e_app(tmp_path_factory):
    """
    Create a fully initialized app with real services.
    Module-scoped so all tests in a file share the same app/database.
    """
    db_dir = tmp_path_factory.mktemp("e2e_db")

    app = create_app()
    # App uses real config.json with valid API keys
    # Database created at tmp path with full migrations

    with TestClient(app) as client:
        yield client

    # Cleanup: databases deleted when tmp_path_factory cleans up


@pytest.fixture(scope="module")
def e2e_client(e2e_app):
    """HTTP client for making API calls."""
    return e2e_app
```

### 2.2 Polling Helper

External services introduce latency. Instead of `time.sleep`, use a polling pattern:

```python
# tests/e2e/helpers.py

import time

def poll_until(predicate, timeout_seconds=30, interval=0.5, description="condition"):
    """
    Poll a predicate function until it returns True or timeout.

    Args:
        predicate: Callable that returns (success: bool, result: Any)
        timeout_seconds: Maximum wait time
        interval: Seconds between polls
        description: What we're waiting for (for error messages)

    Returns:
        The result from the last predicate call

    Raises:
        TimeoutError if predicate never returns True
    """
    deadline = time.time() + timeout_seconds
    last_result = None
    while time.time() < deadline:
        success, last_result = predicate()
        if success:
            return last_result
        time.sleep(interval)
    raise TimeoutError(
        f"Timed out after {timeout_seconds}s waiting for {description}. "
        f"Last result: {last_result}"
    )
```

### 2.3 Stable Test Data

E2E tests use well-known domain concepts that produce stable results from external services:

```python
# tests/e2e/test_data.py

# Concepts that ConceptNet, DBpedia, and Wikidata all recognize well
STABLE_CONCEPTS = {
    "taxonomy": {"title": "Computer Science", "definition": "The study of computation and information"},
    "scheme": {"title": "Data Management", "definition": "Technologies and methods for storing and retrieving data"},
    "classes": [
        {"title": "Database", "definition": "An organized collection of structured information"},
        {"title": "Relational Database", "definition": "A database based on the relational model of data"},
        {"title": "SQL", "definition": "Structured Query Language for managing relational databases"},
        {"title": "Index", "definition": "A data structure that improves the speed of data retrieval"},
    ],
    "relationships": [
        # (source_title, target_title, predicate_identifier)
        ("Relational Database", "Database", "is_a"),
        ("SQL", "Relational Database", "used_by"),
        ("Index", "Database", "part_of"),
    ],
}
```

### 2.4 Test Markers

```python
# pytest markers for controlling E2E test execution

# Run all E2E tests
# pytest -m e2e

# Run only tests that need LLM access
# pytest -m "e2e and llm"

# Run only tests that don't need external APIs (database + embedding only)
# pytest -m "e2e and not external_api"

@pytest.mark.e2e
@pytest.mark.llm          # Requires real LLM API keys
@pytest.mark.reference     # Requires real reference API access
@pytest.mark.nlp           # Requires spaCy models downloaded
@pytest.mark.slow          # Takes > 30 seconds
```

---

## 3. Phase 0 E2E Tests: Foundation Verification

**Goal:** Verify the skeleton structure doesn't break existing functionality. These tests establish the E2E baseline that all future phases must maintain.

### Test Suite: `tests/e2e/test_phase0_baseline.py`

```
test_baseline_taxonomy_lifecycle
    Create taxonomy → create concept scheme → create classes →
    create relationships → verify graph builds → verify search works →
    delete in reverse order → verify clean state

test_baseline_embedding_generation
    Create class with title and definition →
    verify title_embedding is non-null →
    verify definition_embedding is non-null →
    create second class with similar title →
    search by semantic similarity → verify first class ranks high

test_baseline_change_event_tracking
    Record initial event count →
    create taxonomy + scheme + 3 classes + 2 relationships →
    verify event count increased by 7 →
    verify each event has correct record_type and event_type →
    verify events are ordered chronologically

test_baseline_predicate_management
    Create property definition →
    create relationship using that property →
    verify relationship references correct property →
    attempt duplicate property → verify rejected →
    delete property → verify cascade behavior
```

**What these prove:** The existing system works end-to-end through the HTTP API with real database, real embeddings, and real event processing. This is the regression gate for every subsequent phase.

**External services used:** Embedding model only (local SentenceTransformer). No LLM or reference APIs needed.

---

## 4. Phase 1 E2E Tests: Terminology Migration Verification

**Goal:** Verify the renamed database schema, models, and API routes work identically to the baseline.

### Test Suite: `tests/e2e/test_phase1_terminology.py`

```
test_new_api_routes_match_old_behavior
    Execute every operation from test_baseline_taxonomy_lifecycle
    using NEW route paths (/api/classes/ instead of /api/structure_nodes/) →
    verify identical response shapes (modulo renamed fields) →
    verify data visible through BOTH old and new routes

test_old_routes_still_work
    Execute every operation from test_baseline_taxonomy_lifecycle
    using OLD route paths →
    verify still works (deprecated but functional) →
    verify deprecation headers present in responses

test_database_migration_data_integrity
    Pre-populate database with known data using OLD schema →
    run migration 019 →
    read all data through NEW API routes →
    verify every record survived migration →
    verify node_type values are renamed (layer→taxonomy, domain→concept_scheme, term→class) →
    verify all relationships intact →
    verify all embeddings preserved →
    verify all change events preserved

test_migration_rollback
    Pre-populate database with known data →
    run migration 019 forward →
    verify data accessible →
    run migration 019 backward →
    verify data accessible through OLD routes →
    verify no data loss

test_dual_terminology_coexistence
    Create entity through NEW route →
    read through OLD route → verify visible →
    create entity through OLD route →
    read through NEW route → verify visible →
    verify both share the same database rows

test_renamed_enum_values_in_queries
    Create one entity of each type (taxonomy, concept_scheme, class) →
    filter by node_type using NEW values → verify correct results →
    filter by node_type using OLD values → verify still works (during transition) →
    verify search/list operations use correct enum values
```

**What these prove:** The terminology migration is complete and backward-compatible. No data loss. Both old and new APIs work.

**External services used:** Embedding model only.

---

## 5. Phase 2 E2E Tests: Ontology Domain Core

**Goal:** Verify the extracted domain core produces identical behavior when wired through the hexagonal architecture. This is the critical phase — business logic has moved, and adapters are new.

### Test Suite: `tests/e2e/test_phase2_ontology_core.py`

```
test_class_crud_through_new_architecture
    Create taxonomy → create concept scheme →
    create class with title, definition, and parent →
    verify embedding generated →
    update class title → verify embedding regenerated →
    update class definition → verify definition embedding regenerated →
    read class → verify all fields correct →
    delete class → verify gone → verify change events recorded

test_subclass_hierarchy_validation
    Create class "Database" →
    create class "Relational Database" with parent_class_id → Database →
    create class "SQL Database" with parent_class_id → Relational Database →
    create class "Embedded SQL Database" with parent_class_id → SQL Database →
    verify 4-level deep hierarchy traversable →
    attempt to set "Database" parent_class_id → "Embedded SQL Database" →
    verify circular reference rejected with appropriate error →
    verify no partial state change (Database still has no parent)

test_concept_scheme_membership_vs_subclass
    Create scheme "Data Stores" →
    create class "Database" in "Data Stores" →
    create class "Relational Database" in "Data Stores" with parent → Database →
    verify both classes belong to same concept_scheme →
    verify subclass relationship is separate from scheme membership →
    list classes by scheme → returns both →
    list children of Database → returns only Relational Database →
    move "Relational Database" to different scheme →
    verify subclass relationship preserved despite scheme change

test_relationship_lifecycle_with_property_definitions
    Create property definition "is_a" with OWL mapping →
    create property definition "part_of" with OWL mapping →
    create classes "Database" and "Software" →
    create relationship Database→Software using "is_a" →
    verify relationship persisted with correct property reference →
    attempt duplicate relationship → verify rejected →
    create relationship with non-existent property → verify rejected →
    delete property definition → verify cascade/rejection behavior

test_external_reference_management
    Create class "Database" →
    add external reference to DBpedia URI →
    add external reference to Wikidata QID →
    read class → verify both references present →
    update reference confidence score →
    remove one reference → verify other remains →
    verify references survive class update (no accidental overwrites)

test_semantic_search_accuracy
    Create 10 classes with varied titles and definitions
    covering: Database, Cache, Queue, API, Microservice,
    Container, Kubernetes, Load Balancer, Firewall, Encryption →
    search for "data storage" → verify Database and Cache rank top 3 →
    search for "network security" → verify Firewall and Encryption rank top 3 →
    search for "container orchestration" → verify Kubernetes ranks top 2

test_domain_events_fire_correctly
    Record initial change event count →
    create taxonomy (expect: 1 create event) →
    create scheme (expect: 1 create event) →
    create class (expect: 1 create event) →
    update class title (expect: 1 update event with old/new values) →
    create relationship (expect: 1 create event) →
    delete relationship (expect: 1 delete event) →
    verify total: 6 new change events →
    verify each event has correct record_type, event_type, timestamps →
    verify update event contains both old_data and new_data

test_batch_class_creation_consistency
    Create scheme →
    create 50 classes in rapid succession (sequential API calls) →
    verify all 50 persisted →
    verify all 50 have embeddings →
    verify 50 change events recorded →
    verify no duplicate IDs →
    list classes by scheme → verify count is 50

test_concurrent_modification_safety
    Create a class →
    send two simultaneous update requests (different fields) →
    verify final state is consistent (no lost updates, no corruption) →
    verify change events capture both modifications
```

**What these prove:** The hexagonal extraction preserved all business rules. Validation logic (circular refs, duplicates, required fields) still enforces correctly. Embeddings generate on the right triggers. Events fire for every mutation. The system handles edge cases.

**External services used:** Embedding model (real, local).

---

## 6. Phase 2 E2E Tests: Real External Service Integration

These tests use actual external services and are marked accordingly.

### Test Suite: `tests/e2e/test_phase2_external_services.py`

```
@pytest.mark.nlp
test_nlp_pipeline_processes_real_text
    Submit text: "SQLite is a popular embedded relational database engine
    used in mobile applications and web browsers." →
    verify NLP processor returns entities →
    verify at least "SQLite" recognized as entity →
    verify entity has linked URI or label →
    verify processing completes within 10 seconds

@pytest.mark.reference
test_reference_source_enrichment_conceptnet
    Query ConceptNet for "database" →
    verify results returned with URIs →
    verify at least one relation found (e.g., IsA, RelatedTo) →
    verify response includes labels and weights →
    verify caching: second identical query is faster

@pytest.mark.reference
test_reference_source_enrichment_dbpedia
    Query DBpedia for "SQLite" →
    verify DBpedia URI returned →
    verify description/abstract present →
    verify response normalized to common ReferenceResult format

@pytest.mark.reference
test_reference_source_enrichment_wikidata
    Query Wikidata for "relational database" →
    verify Wikidata QID returned →
    verify at least one property/relation found →
    verify response normalized to common format

@pytest.mark.llm
test_llm_provider_completions
    Send a simple classification prompt to each configured LLM provider →
    prompt: "Classify the following term into a category.
    Term: PostgreSQL. Respond with just the category name." →
    verify response is non-empty string →
    verify response completes within provider timeout →
    verify token counts are positive

@pytest.mark.llm
@pytest.mark.reference
@pytest.mark.nlp
test_full_rag_extraction_pipeline
    Submit text: "PostgreSQL is an open-source object-relational database
    system. It uses SQL for queries and supports ACID transactions.
    Redis is often used alongside PostgreSQL as an in-memory cache
    to improve read performance." →
    verify extraction completes within 60 seconds →
    verify at least 3 entities extracted (PostgreSQL, Redis, SQL) →
    verify each entity has a confidence score →
    verify layer execution metrics recorded (all 4 layers) →
    verify at least one entity matched to existing KG class (if DB pre-populated) →
    verify execution trace stored in operations database

@pytest.mark.llm
test_pipeline_configuration_execution
    Create a pipeline configuration with real provider/model →
    execute the pipeline with test input →
    verify output received →
    verify execution record stored with token counts and duration →
    verify execution is queryable by pipeline config ID
```

**What these prove:** All external service adapters are correctly wired and producing real results. The caching layer works. The RAG pipeline processes text through all four layers with real services. LLM traceability captures real execution data.

---

## 7. Phase 3 E2E Tests: Graph & Extraction Contexts

**Goal:** Verify graph analysis and knowledge extraction work correctly through their new bounded context services.

### Test Suite: `tests/e2e/test_phase3_graph.py`

```
test_graph_build_and_query
    Create taxonomy → scheme → 8 classes with subclass hierarchy →
    create 10 relationships between classes →
    build graph via API →
    verify node count matches →
    verify edge count matches →
    query shortest path between two distant classes → verify path exists →
    verify path contains expected intermediate nodes

test_graph_centrality_analysis
    Build graph from test data (8 classes, 10 relationships) →
    request centrality analysis →
    verify all nodes have centrality scores →
    verify the most-connected node has highest centrality →
    verify results are deterministic (run twice, same results)

test_graph_community_detection
    Build graph with two loosely connected clusters
    (Cluster A: Database, SQL, Index, Query
     Cluster B: API, REST, HTTP, JSON
     Bridge: Database→API with "serves" relationship) →
    run community detection →
    verify two communities found →
    verify cluster membership is correct →
    verify bridge relationship connects the communities

test_graph_cycle_detection_for_subclass
    Build graph with valid hierarchy →
    verify no cycle detected →
    attempt to add edge that would create cycle →
    verify cycle detected and edge rejected →
    verify graph state unchanged after rejection

test_sparql_query_execution
    Build ontology in graph →
    execute SPARQL query: find all classes that are subClassOf "Database" →
    verify correct results returned →
    execute SPARQL query: find all relationships of type "is_a" →
    verify correct count →
    execute malformed SPARQL → verify clean error response

test_graph_invalidation_on_mutation
    Build graph → verify built →
    create a new class →
    verify graph marked as stale or auto-rebuilt →
    query graph → verify new class included →
    delete a relationship →
    query graph → verify relationship absent
```

### Test Suite: `tests/e2e/test_phase3_extraction.py`

```
@pytest.mark.llm
@pytest.mark.nlp
@pytest.mark.reference
test_extraction_with_kg_context
    Pre-populate KG: taxonomy "Technology", scheme "Databases",
    classes: Database, SQL, PostgreSQL, Redis →
    extract from text: "MySQL is similar to PostgreSQL but licensed
    differently. Both support SQL and ACID transactions." →
    verify "MySQL" extracted as new entity →
    verify "PostgreSQL" matched to existing KG class →
    verify "SQL" matched to existing KG class →
    verify confidence scores present →
    verify KG context layer contributed matches

@pytest.mark.llm
@pytest.mark.nlp
test_extraction_layer_metrics
    Run extraction on a paragraph →
    verify all 4 layer results returned →
    verify each layer has duration_ms > 0 →
    verify each layer has entities_found >= 0 →
    verify total duration ≈ sum of layer durations (within 20%) →
    verify layers executed in order (0, 1, 2, 3)

@pytest.mark.reference
test_reference_aggregation_across_sources
    Query "database" through the reference aggregation endpoint →
    verify results from multiple sources (ConceptNet + DBpedia minimum) →
    verify results are deduplicated →
    verify each result has source attribution →
    verify results sorted by relevance/confidence

@pytest.mark.reference
test_reference_cache_effectiveness
    Query a term through reference API → record response time →
    query the same term again → record response time →
    verify second query is at least 2x faster →
    verify both queries return identical results →
    verify cache entry exists in reference_api_cache.db
```

**What these prove:** The graph and extraction bounded contexts work with real services. The graph correctly reflects ontology state and invalidates when data changes. The RAG pipeline produces real extraction results with proper metrics. Reference source aggregation and caching work end-to-end.

---

## 8. Phase 4 E2E Tests: Pipeline, Versioning, Admin

### Test Suite: `tests/e2e/test_phase4_pipeline.py`

```
@pytest.mark.llm
test_pipeline_config_to_execution_workflow
    Create pipeline config with real model (e.g., gpt-4o-mini) →
    list pipeline configs → verify present →
    execute pipeline with: "Classify: PostgreSQL" →
    verify response received →
    query executions for this config → verify at least 1 →
    verify execution has tokens_in, tokens_out, duration_ms →
    verify execution status is "success" →
    update config to use different system prompt →
    re-execute → verify different output →
    query executions → verify now 2 records

@pytest.mark.llm
test_pipeline_execution_with_invalid_model
    Create pipeline config with non-existent model "gpt-999" →
    attempt execution →
    verify error response (not 500) →
    verify execution record stored with status "error" →
    verify error_message is meaningful
```

### Test Suite: `tests/e2e/test_phase4_versioning.py`

```
test_version_tracking_through_mutations
    Create class → record version 1 →
    update title → record version 2 →
    update definition → record version 3 →
    list versions → verify 3 versions exist →
    get version 1 → verify original title →
    get version 2 → verify updated title, original definition →
    get version 3 → verify both updated

test_change_event_completeness
    Start with empty change_events →
    execute a complex workflow:
      create taxonomy, scheme, 3 classes, 4 relationships, 2 property definitions →
    count change events → verify matches expected count (12) →
    filter by record_type → verify correct distribution →
    filter by event_type → verify all are "create" →
    update 2 classes → filter by event_type "update" → verify 2 →
    delete 1 relationship → filter by event_type "delete" → verify 1

test_changeset_workflow
    Create entities across multiple API calls →
    group into a changeset →
    verify changeset contains all expected operations →
    get changeset diff → verify shows correct before/after state

test_event_processing_reliability
    Create 100 entities in rapid succession →
    wait for event processor to catch up (poll processed flag) →
    verify all 100 events marked as processed →
    verify no events lost or duplicated →
    verify processing order matches creation order
```

### Test Suite: `tests/e2e/test_phase4_admin.py`

```
test_health_check_reports_real_status
    Call health endpoint →
    verify database_connected is true →
    verify response includes all expected service statuses →
    verify response time < 5 seconds

test_system_metrics_accuracy
    Create some entities (to generate activity) →
    call metrics endpoint →
    verify service creation counts > 0 →
    verify database query metrics present →
    verify embedding model metrics present

test_configuration_read_and_update
    Read current configuration →
    verify all expected sections present (server, database, llm, nlp, etc.) →
    update a non-sensitive config value →
    read configuration again → verify update persisted →
    restart app (or reload) → verify config survived

test_background_task_lifecycle
    Submit a background task →
    poll task status → verify transitions: pending → running → completed →
    get task result → verify non-null →
    verify task completion time recorded →
    list all tasks → verify submitted task present
```

**What these prove:** LLM pipeline management works with real providers. Version tracking captures complete mutation history. Change events are reliable at volume. Admin endpoints reflect real system state. Background tasks execute to completion.

---

## 9. Phase 5 E2E Tests: Regression & Clean Verification

**Goal:** After legacy removal, verify the entire system still works. This is essentially re-running all Phase 2–4 tests plus a comprehensive regression suite.

### Test Suite: `tests/e2e/test_phase5_regression.py`

```
test_full_workflow_no_legacy_routes
    Execute the complete workflow using ONLY new API routes →
    verify no 404s (old routes are gone, new routes handle everything) →
    taxonomy lifecycle → scheme lifecycle → class lifecycle →
    relationship lifecycle → property definition lifecycle →
    graph build → graph query →
    verify everything works without deprecated routes

@pytest.mark.llm
@pytest.mark.nlp
@pytest.mark.reference
test_full_rag_workflow_new_architecture
    Pre-populate KG through new routes →
    run RAG extraction with real services →
    verify entities extracted and matched to KG →
    verify all metrics and traces recorded →
    verify reference sources queried and cached →
    verify NLP pipeline contributed entities →
    verify LLM execution traced

test_database_schema_is_clean
    Connect directly to the database →
    verify only expected tables exist (no legacy table names) →
    verify enum values are all new terminology →
    verify no orphaned foreign keys →
    verify all indexes present →
    verify migration version is current

test_no_legacy_imports_in_codebase
    (This is a static analysis test, not a runtime test)
    Scan all Python files in domain/ →
    verify zero imports from adapters/, database/, or framework code →
    Scan all Python files in adapters/web/ →
    verify no business logic (no validation, no if/else on domain rules)

test_openapi_spec_matches_implementation
    Fetch OpenAPI spec from /openapi.json →
    for each endpoint in spec:
        make a valid request → verify response matches spec →
        make an invalid request → verify error response matches spec →
    verify no undocumented endpoints exist
```

---

## 10. Test Execution Strategy

### Nightly Full E2E Suite

All E2E tests run nightly against a fresh database with real services:

```bash
# Full suite — runs all tests including slow LLM and reference API calls
pytest tests/e2e/ -m e2e --timeout=300 -v --tb=long
```

### Per-PR Quick E2E

A faster subset runs on every pull request. Skips slow external service tests:

```bash
# Quick suite — no LLM, no reference APIs, just DB + embeddings
pytest tests/e2e/ -m "e2e and not llm and not reference" --timeout=60 -v
```

### Phase-Specific Execution

During each transformation phase, run only that phase's tests plus the baseline:

```bash
# Phase 2 verification
pytest tests/e2e/test_phase0_baseline.py tests/e2e/test_phase2_*.py -v --timeout=300
```

### Test Result Expectations

| Test Category | Expected Duration | Pass Criteria |
|---|---|---|
| Phase 0 baseline | ~30 seconds | 100% pass |
| Phase N (no external) | ~60 seconds | 100% pass |
| Phase N (with LLM) | ~3–5 minutes | 100% pass |
| Phase N (with reference) | ~2–3 minutes | 95% pass (reference APIs may be flaky) |
| Full suite | ~10–15 minutes | 95% pass (flaky tolerance for external APIs) |

### Handling External Service Flakiness

Reference APIs (ConceptNet, DBpedia, Wikidata) can have availability issues. Handle this with:

```python
@pytest.mark.reference
@retry_on_external_failure(max_retries=2, delay=5)
def test_reference_source_enrichment_conceptnet(e2e_client):
    ...
```

```python
# tests/e2e/helpers.py

def retry_on_external_failure(max_retries=2, delay=5):
    """Retry decorator for tests that depend on external APIs."""
    def decorator(test_func):
        @functools.wraps(test_func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return test_func(*args, **kwargs)
                except (ConnectionError, TimeoutError, requests.HTTPError) as e:
                    last_error = e
                    if attempt < max_retries:
                        time.sleep(delay)
            pytest.skip(f"External service unavailable after {max_retries} retries: {last_error}")
        return wrapper
    return decorator
```

For LLM tests, failures are always real failures (LLM APIs are highly available). No retry/skip for LLM tests.

---

## 11. What Each Phase's E2E Tests Prove

| Phase | Core Question | Key Verification |
|---|---|---|
| 0 | Does the existing system work? | Baseline behavior captured as repeatable tests |
| 1 | Did renaming break anything? | Old and new routes produce identical results. Migration preserves all data. |
| 2 | Did the domain extraction break business rules? | Circular ref detection, duplicate prevention, embedding generation, event firing — all still work through new architecture |
| 2+ | Do real external services still work? | LLM calls, NLP processing, reference API queries, RAG pipeline — all produce real results |
| 3 | Do graph and extraction contexts work independently? | Graph builds from ontology data, SPARQL queries work, extraction pipeline uses all 4 layers |
| 4 | Do pipeline, versioning, and admin work? | Pipeline configs execute against real LLMs, versions track correctly, health reflects real state |
| 5 | Is the system clean and complete? | No legacy routes, no legacy tables, no legacy imports, OpenAPI spec matches reality |

---

## 12. E2E Test File Summary

```
tests/e2e/
├── conftest.py                          # E2E fixtures: real app, real config
├── helpers.py                           # poll_until, retry_on_external_failure
├── test_data.py                         # Stable test concepts and relationships
├── test_phase0_baseline.py              # Baseline verification (4 tests)
├── test_phase1_terminology.py           # Terminology migration (6 tests)
├── test_phase2_ontology_core.py         # Ontology domain core (9 tests)
├── test_phase2_external_services.py     # Real external service integration (7 tests)
├── test_phase3_graph.py                 # Graph analysis context (6 tests)
├── test_phase3_extraction.py            # Knowledge extraction context (4 tests)
├── test_phase4_pipeline.py              # LLM pipeline management (2 tests)
├── test_phase4_versioning.py            # Version control & change tracking (4 tests)
├── test_phase4_admin.py                 # System administration (4 tests)
└── test_phase5_regression.py            # Final regression & cleanliness (4 tests)
                                         # ─────────────────────────────────
                                         # Total: ~50 E2E tests
```

Each test file is designed to be runnable independently. The phase 0 baseline should be run alongside every other phase as the core regression gate.
