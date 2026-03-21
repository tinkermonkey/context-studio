# Reference_db vs Schema_org: Architecture Analysis

**Date**: 2025-10-05
**Total Lines**: ~3,698 lines across both modules
**Issue**: Unclear separation of concerns, potential duplication

---

## Executive Summary

These two modules have **significant overlap and unclear boundaries**, leading to confusion and duplication. They appear to have evolved from different design phases without proper consolidation.

### Key Finding
**Both modules import and manage Schema.org data, but with different architectures, different data models, and different API surfaces.**

---

## Module Breakdown

### 1. `reference_db/` - Generic Reference Database (Phase 2-4)

**Purpose**: Generic reference database for **multiple external knowledge sources** (Schema.org, WikiData, DBpedia, ConceptNet)

**Database Schema**:
- `reference_nodes` - Generic nodes from ANY source
  - Fields: `id`, `title`, `definition`, `source`, `external_id`, `attributes` (JSON), `title_embedding`, `definition_embedding`
  - **Generic**: `source` column distinguishes Schema.org from WikiData, etc.

- `reference_links` - Generic relationships
  - Fields: `id`, `subject_node`, `predicate`, `object_node`, `attributes` (JSON)

**Key Classes**:
- `ReferenceManager` - CRUD operations, vector search, health checks
- `SchemaOrgImporter` - **Schema.org-specific importer** (ironic!)
- `ReferenceConfig` - Configuration for all reference sources

**API Surface** (`/api/reference/`):
```
GET  /dbpedia/search
GET  /conceptnet/query
GET  /wikidata/entity
GET  /schema-org/entity/{identifier}      ← Schema.org via reference system
GET  /ref-db/search                       ← Vector search across all sources
GET  /ref-db/nodes/{node_id}
GET  /ref-db/nodes/{node_id}/links
GET  /ref-db/health
POST /search                              ← Multi-source search
```

**Features**:
- ✅ Multi-source support (Schema.org, WikiData, DBpedia, ConceptNet)
- ✅ Vector similarity search with sqlite-vec
- ✅ Generic graph traversal (links, predicates)
- ✅ Health monitoring with degraded state detection
- ✅ Schema versioning and automatic rebuild
- ✅ Lock file management for concurrent imports

**Typical Use Case**: "Search across Schema.org, WikiData, and DBpedia for entities matching 'person who writes books'"

---

### 2. `schema_org/` - Schema.org-Specific Module (Phase 5)

**Purpose**: **Schema.org-only** local database with optimized schema

**Database Schema**:
- `schema_org_entities` - **Schema.org entities only**
  - Fields: `id`, `identifier`, `title`, `title_embedding`, `definition`, `definition_embedding`, `parent_identifier`, `parent_id`, `raw` (JSON)
  - **Specific**: Has `parent_id` foreign key for hierarchy

- `schema_org_properties` - **Schema.org properties only**
  - Fields: `id`, `identifier`, `title`, `title_embedding`, `definition`, `definition_embedding`, `contributors`, `domain_includes`, `range_includes`, `inverse_of`, `raw` (JSON)
  - **Specific**: Property-specific fields embedded

**Key Classes**:
- `SchemaOrgManager` - Schema.org-specific lifecycle management
- `SchemaOrgService` - Schema.org-specific search service
- `SchemaOrgMetrics` - Performance monitoring

**API Surface** (`/api/schema-org/`):
```
GET  /status
POST /refresh
GET  /entities
GET  /entities/{identifier}
GET  /properties
GET  /properties/{identifier}
GET  /search
```

**Features**:
- ✅ Schema.org-specific optimizations
- ✅ Entity hierarchy (parent/child relationships)
- ✅ Property metadata (domain_includes, range_includes)
- ✅ Performance metrics tracking
- ✅ Rebuild-only strategy (no migrations)
- ✅ Memory profiling during imports

**Typical Use Case**: "Get Schema.org 'Person' entity with all its properties and parent hierarchy"

---

## Critical Duplication Issues

### 1. **Schema.org Import Logic - DUPLICATED**

**Problem**: Two completely separate implementations for importing Schema.org data

| Feature | `reference_db/schema_org_importer.py` | `schema_org/manager.py` |
|---------|--------------------------------------|------------------------|
| Downloads Schema.org JSON-LD | ✅ | ✅ |
| Parses entities/properties | ✅ | ✅ |
| Generates embeddings | ✅ | ✅ |
| Creates vector tables | ✅ | ✅ |
| Extracts relationships | ✅ | ✅ |
| Lock file management | ✅ | ❓ |
| Transaction rollback | ✅ | ❓ |

**Impact**: ~1,000+ lines of duplicated logic

---

### 2. **Data Models - INCOMPATIBLE SCHEMAS**

**Problem**: Same data (Schema.org entities) stored in two different schemas

**reference_db approach**:
```python
ReferenceNode(
    source="schema.org",
    external_id="Person",
    title="Person",
    definition="A person...",
    attributes={"@type": "entity", "parent": "Thing"}  # JSON blob
)
```

**schema_org approach**:
```python
SchemaOrgEntity(
    identifier="Person",
    title="Person",
    definition="A person...",
    parent_identifier="Thing",
    parent_id="<uuid>",  # Actual FK relationship
    raw={"@id": "...", "@type": "..."}
)
```

**Impact**:
- Cannot share data between modules
- Cannot migrate from one to the other without full rebuild
- Queries must target specific module

---

### 3. **Vector Search - DUPLICATED**

Both modules implement vector similarity search independently:

**reference_db**:
```python
manager.search_by_similarity(
    query_text="person",
    source="schema.org",  # Optional filter
    threshold=0.7
)
```

**schema_org**:
```python
service.semantic_search(
    query="person",
    threshold=0.7
)
```

**Impact**: Same functionality, different APIs, different codepaths

---

### 4. **API Endpoints - OVERLAPPING**

Both expose Schema.org entity retrieval:

```
GET /api/reference/schema-org/entity/Person    ← reference_db route
GET /api/schema-org/entities/Person            ← schema_org route
```

**Impact**:
- Unclear which to use
- Different response schemas
- Inconsistent behavior

---

## Architecture Confusion

### Why Two Modules Exist

Based on README context:

1. **reference_db** (Phase 2-4): Generic multi-source reference system
   - Designed for **heterogeneous sources** (Schema.org, WikiData, DBpedia)
   - Schema.org is just **one of many sources**

2. **schema_org** (Phase 5): Dedicated Schema.org optimization
   - Designed for **Schema.org-specific use cases**
   - Optimized schema with entity hierarchy and property metadata

### The Problem

**`reference_db/` has a Schema.org-specific importer** (`schema_org_importer.py`), blurring the lines:

```
reference_db/
  ├── schema_org_importer.py   ← Why is this here?
  ├── manager.py                ← Generic manager
  └── models.py                 ← Generic models (source column)

schema_org/
  ├── manager.py                ← Schema.org-specific manager
  └── models.py                 ← Schema.org-specific models
```

**This violates separation of concerns**: The "generic" reference database shouldn't contain source-specific importers.

---

## Recommendations

### Option 1: Consolidate (Recommended)

**Merge schema_org into reference_db as a source adapter**

```
reference_db/
  ├── manager.py              ← Generic manager
  ├── models.py               ← Generic models
  └── importers/
      ├── __init__.py
      ├── schema_org.py       ← Move from reference_db/schema_org_importer.py
      ├── wikidata.py
      └── dbpedia.py
```

**Benefits**:
- Single source of truth
- Consistent API surface
- Reduced duplication
- Clear separation: importers vs. storage vs. search

**Migration Path**:
1. Move `reference_db/schema_org_importer.py` → `reference_db/importers/schema_org.py`
2. Deprecate `schema_org/` module
3. Add migration utility to move data from `schema_org_entities` → `reference_nodes`
4. Update API routes to use unified reference endpoints

---

### Option 2: Clear Separation

**Keep both but enforce strict boundaries**

**reference_db**:
- Multi-source reference system
- Generic search across all sources
- No source-specific importers (move `schema_org_importer.py` out)

**schema_org**:
- Schema.org-specific optimizations
- Used by reference_db as a data source
- reference_db imports from schema_org module

**Changes Required**:
1. Move `reference_db/schema_org_importer.py` → `schema_org/importer.py`
2. ReferenceManager imports Schema.org data via `schema_org.manager`
3. Deprecate `/api/reference/schema-org/*` routes (use `/api/schema-org/*`)
4. Document that `schema_org/` is the authoritative source

---

### Option 3: Feature-Based Split

**Keep both with clear feature ownership**

**reference_db**:
- Cross-source search
- Multi-source aggregation
- Vector similarity across DBpedia + WikiData + ConceptNet

**schema_org**:
- Schema.org entity/property browsing
- Schema.org hierarchy navigation
- Schema.org-specific metadata

**Changes Required**:
1. Remove Schema.org search from `reference_db` (use schema_org for that)
2. Remove `reference_db/schema_org_importer.py`
3. ReferenceManager delegates Schema.org queries to `schema_org.service`

---

## Questions to Answer

1. **What is the intended architecture?**
   - Is `reference_db` meant to be the unified interface?
   - Is `schema_org` a specialized optimization or a standalone module?

2. **What's the migration path?**
   - Are both modules in production?
   - Can we deprecate one without breaking users?

3. **What are the performance requirements?**
   - Does Schema.org need specialized optimization (hierarchy queries)?
   - Is generic `reference_nodes` fast enough for Schema.org use cases?

4. **What's the UX expectation?**
   - Should users call `/api/reference/search` or `/api/schema-org/search`?
   - Should there be two health check endpoints?

---

## Immediate Actions

### 1. Document Intent
Create `ARCHITECTURE.md` clearly stating:
- Purpose of each module
- When to use which module
- Migration path (if applicable)

### 2. Move Schema.org Importer
`reference_db/schema_org_importer.py` should not exist in a "generic" module.

**Decision needed**: Move to `schema_org/` or to `reference_db/importers/`?

### 3. Deprecate Duplicate APIs
Choose one:
- `/api/reference/schema-org/*` (generic system)
- `/api/schema-org/*` (specialized system)

Mark the other as deprecated with migration timeline.

### 4. Add Cross-References
If keeping both modules:
- `reference_db/README.md` should link to `schema_org/` for Schema.org-specific features
- `schema_org/README.md` should link to `reference_db/` for multi-source search

---

## Conclusion

**The current architecture has unclear boundaries and significant duplication.**

The presence of `reference_db/schema_org_importer.py` suggests that someone started building Schema.org support in the generic reference system, then later built a dedicated `schema_org/` module without consolidating.

**Recommended Path Forward**: **Option 1 (Consolidate)** unless there's a compelling performance or feature requirement for separate Schema.org optimization that justifies the duplication.
