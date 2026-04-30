# Context Studio Application Context

This document is the authoritative source of truth for Context Studio's product surface. Humans, agents, and tooling all consume this contract to understand pages, selectors, entity fields, and invariants.

## Page Map

| Route | Purpose | Status |
|-------|---------|--------|
| `/app` | Dashboard / app home | Primary |
| `/app/taxonomies` | List and manage all taxonomies | Primary |
| `/app/taxonomies/$taxonomyId` | View a single taxonomy and its schemes | Primary |
| `/app/concept-schemes` | List and manage concept schemes across all taxonomies | Primary |
| `/app/concept-schemes/$schemeId` | View a single concept scheme and its classes | Primary |
| `/app/classes` | List and manage all classes across all schemes | Primary |
| `/app/classes/$classId` | View a single class and its relationships | Primary |
| `/app/relationships` | List and manage relationships between entities | Primary |
| `/app/properties` | List and manage property definitions (predicate registry) | Primary |
| `/app/datasets` | Data import and management interface | Secondary |
| `/app/config` | Configuration hub for system settings | Secondary |
| `/app/config/pipelines` | LLM pipeline definitions and management | Secondary |
| `/app/config/pipelines/$pipelineType` | View pipelines by type (extraction, analysis, etc.) | Secondary |
| `/app/config/pipelines/$pipelineType/create` | Create a new pipeline flavor | Secondary |
| `/app/config/pipelines/$pipelineType/edit/$flavorId` | Edit an existing pipeline flavor | Secondary |
| `/app/config/pipelines/$pipelineType/test/$flavorId` | Test a pipeline flavor with sample data | Secondary |
| `/app/config/data-sources` | External knowledge source configuration | Secondary |
| `/app/config/models` | LLM model configuration and selection | Secondary |
| `/app/config/processing` | Text processing and NLP settings | Secondary |
| `/app/config/network` | Graph visualization and network settings | Secondary |
| `/app/config/advanced` | Advanced system settings and diagnostics | Secondary |
| `/app/reference` | External knowledge graph explorer (ConceptNet, DBpedia, schema.org) | Secondary |
| `/app/monitoring` | System health, background tasks, observability | Secondary |
| `/app/rag` | RAG pipeline testing and experimentation | Experimental |

---

## Entity Model Summary

The complete entity type definitions are generated from the OpenAPI specification and located in `ux/src/api/client/types.ts`.

### Core Entity Relationships

**Hierarchy:**
```
Taxonomy (root)
  ├─ ConceptScheme (belongs to one Taxonomy)
  │   └─ Class (belongs to one ConceptScheme)
  │       └─ Relationship (links Classes via PropertyDefinitions)
  └─ PropertyDefinition (predicate registry, used by Relationships)
```

### Key Entity Fields

**TaxonomyResponse** (`id`, `title`, `description`, `version`, `created_at`, `last_modified`)
- Root organizational unit for ontologies
- Referenced by: ConceptScheme (via `taxonomy_id`)
- Can be soft-deleted (cascades to schemes and classes)

**ConceptSchemeResponse** (`id`, `title`, `description`, `taxonomy_id`, `version`, `created_at`, `last_modified`)
- Organizational unit within a Taxonomy
- Referenced by: Class (via `concept_scheme_id`)
- Cannot exist without a parent Taxonomy

**ClassResponse** (`id`, `title`, `description`, `concept_scheme_id`, `type`, `version`, `created_at`, `last_modified`)
- Represents a class/concept within a ConceptScheme
- Referenced by: Relationship (via `source_id` and `target_id`)
- `type` may indicate domain, layer, or other classifier

**RelationshipResponse** (`id`, `source_id`, `target_id`, `predicate_id`, `version`, `created_at`, `last_modified`)
- Typed, directed edge between two Classes
- Requires a PropertyDefinition (via `predicate_id`) as the predicate
- Both `source_id` and `target_id` must reference existing Classes

**PropertyDefinitionResponse** (`id`, `title`, `identifier`, `description`, `version`, `created_at`, `last_modified`)
- Predicate registry: defines allowed relationship types
- Referenced by: Relationship (via `predicate_id`)
- `identifier` is the RDF-style URI or namespace identifier (e.g., `rdfs:subClassOf`)

### Example Workflow

1. User creates a Taxonomy: `"Biology"`
2. User creates a ConceptScheme within Biology: `"Linnaean Taxonomy"`
3. User creates Classes: `"Kingdom"`, `"Phylum"`, `"Class"`
4. User creates a PropertyDefinition: `"narrower"` (identifier: `skos:narrower`)
5. User creates a Relationship: `Kingdom` --narrower--> `Phylum` (predicate: "narrower")

---

## Key User Flows

### 1. Creating a New Taxonomy
1. Navigate to `/app/taxonomies`
2. Click "Add" / "New Taxonomy" button (`data-testid="taxonomy-add-button"`)
3. Form modal opens (`data-testid="taxonomy-form"`)
4. Fill in `title` (required) and `description` (optional)
5. Submit form → Taxonomy created, appears in list, modal closes
6. User can now add ConceptSchemes to this Taxonomy

### 2. Moving a Class Between Concept Schemes
1. Navigate to `/app/classes`
2. Select a Class from the list
3. Open the Class detail view
4. Click "Move" action → Move modal opens (`data-testid="class-move-modal"`)
5. Select target ConceptScheme from dropdown
6. Confirm → Class's `concept_scheme_id` updates, appears in new scheme's list

### 3. Deleting a Concept Scheme (with cascade)
1. Navigate to `/app/concept-schemes`
2. Select a ConceptScheme
3. Click "Delete" → Delete confirmation modal appears
4. Confirm deletion
5. ConceptScheme is soft-deleted; all contained Classes are also soft-deleted (cascade)
6. Relationships referencing those Classes become orphaned (flagged as invalid)

### 4. Creating a Relationship Between Classes
1. Navigate to `/app/relationships` OR within `/app/classes/$classId` detail view
2. Click "Add Relationship" → Form modal opens
3. Select `source_id` (Class) via dropdown
4. Select `target_id` (Class) via dropdown
5. Select or create a PropertyDefinition (predicate)
6. Submit → Relationship created, both Classes must exist and be in valid states

### 5. Configuring and Testing an LLM Pipeline
1. Navigate to `/app/config/pipelines`
2. Select a pipeline type (e.g., "extraction")
3. Click "Create Flavor" or edit an existing one
4. Configure pipeline parameters (model, prompt templates, etc.)
5. Click "Test" → Test page opens with sample data
6. Run test → Observe pipeline output and traceability logs
7. Save configuration when satisfied

### 6. Syncing with External Knowledge Source
1. Navigate to `/app/config/data-sources`
2. Select or add a source (ConceptNet, DBpedia, schema.org)
3. Configure credentials and parameters
4. Click "Sync" → Background task starts
5. Monitor progress on `/app/monitoring`
6. Once complete, imported entities appear in `/app/reference`

### 7. Bulk Import from Datasets
1. Navigate to `/app/datasets`
2. Upload a file (CSV, RDF, or other supported format)
3. Map file columns to entity fields
4. Preview import results
5. Confirm → Background task processes import, updates entity count

### 8. Viewing Entity Ancestry and Relationships
1. Navigate to any entity detail page (e.g., `/app/classes/$classId`)
2. View "Attributes" section (properties, metadata)
3. View "Children" section (outgoing relationships)
4. View incoming relationships if present
5. Click linked entities to navigate the graph

---

## Invariants

These are rules the application guarantees:

### Deletion Rules
- **Soft delete**: Deleting a Taxonomy soft-deletes all its ConceptSchemes and their Classes. Relationships are flagged as invalid but not deleted.
- **Cascade to Classes**: Deleting a ConceptScheme soft-deletes all its Classes and all Relationships involving those Classes.
- **Orphaning Relationships**: Deleting a Class orphans any Relationship where that Class is the source or target. The Relationship record persists but is marked as invalid.

### Reference Integrity
- A ConceptScheme **must** have a parent Taxonomy (non-null `taxonomy_id`).
- A Class **must** have a parent ConceptScheme (non-null `concept_scheme_id`).
- A Relationship **must** reference a PropertyDefinition (non-null `predicate_id`).
- A Relationship's `source_id` and `target_id` **must** reference existing, valid (non-soft-deleted) Classes.

### Field Constraints
- Taxonomy `title`, ConceptScheme `title`, Class `title`, PropertyDefinition `title` are required and must be unique within their parent scope.
- PropertyDefinition `identifier` is required and globally unique (e.g., `rdfs:subClassOf`).
- All entities have `version` (for optimistic concurrency control) and `created_at` / `last_modified` timestamps.

### Concurrency
- All CRUD operations use optimistic concurrency control via the `version` field.
- If a concurrent update occurs, the API returns a 409 Conflict; the client must refetch and retry.

### Immutability
- Entity `id` and `created_at` are immutable.
- Entity `version` is incremented on each update.
- `last_modified` is updated on every change.

---

## Anti-Patterns: Things Tests Must NEVER Do

### Test Anti-Patterns
- ❌ **Wait for fixed timeout**: Do not use `page.waitForTimeout(N)` without a condition. Always wait for a state change or element visibility.
  - ✅ Good: `await page.waitForLoadState("networkidle")` or `await expect(element).toBeVisible()`
  - ❌ Bad: `await page.waitForTimeout(2000)` (causes flaky tests)

- ❌ **Expect trivial conditions**: Do not write assertions that are always true.
  - ❌ Bad: `expect(true).toBe(true)` or `expect(page.url()).toBeTruthy()` (adds no value)
  - ✅ Good: `expect(page.url()).toContain("/app/taxonomies")` (specific assertion)

- ❌ **Hardcoded UUIDs**: Do not assume specific UUIDs in tests; UUIDs are generated per test run.
  - ❌ Bad: `page.goto("/app/classes/123e4567-e89b-12d3-a456-426614174000")`
  - ✅ Good: Create the entity first and use the returned `id`, then navigate: `page.goto(`/app/classes/${classId}`)`

- ❌ **Incorrect selector references**: Do not use `data-testid` values that don't exist in the codebase.
  - ❌ Bad: `page.locator('[data-testid="taxonomy-remove-button"]')` (selector doesn't exist)
  - ✅ Good: Use the selector registry to verify the selector exists before writing the test

- ❌ **Relying on UI text for navigation**: Do not depend on text that may change or be localized.
  - ❌ Bad: `page.getByText("Delete This Taxonomy").click()` (text may change)
  - ✅ Good: Use `data-testid` or role-based selectors: `page.getByRole("button", { name: /delete/i })`

- ❌ **Missing cleanup**: Do not leave test data behind.
  - ❌ Bad: Test creates Taxonomy but doesn't delete it
  - ✅ Good: Use `test.afterEach()` to clean up: `await clearTestData(page)`

- ❌ **Testing implementation details**: Do not assert on internal state, Redux store, or API calls.
  - ❌ Bad: `expect(store.getState().ontology.taxonomies.length).toBe(3)`
  - ✅ Good: Assert on visible UI: `expect(page.getByText("Taxonomy 1")).toBeVisible()`

- ❌ **Ignoring error states**: Do not skip error handling in happy-path tests.
  - ❌ Bad: `await apiRequest(page, "/invalid-endpoint")` without error handling
  - ✅ Good: Wrap in try-catch or expect specific error codes

- ❌ **Making assumptions about page load order**: Do not assume elements load in a specific order.
  - ❌ Bad: `const element = page.locator("div").first()` (assumes first div is the one you want)
  - ✅ Good: Use `data-testid` or role-based queries: `page.getByRole("button", { name: /submit/i })`

---

## Selector Registry

See `selector-registry.yaml` for the canonical list of all `data-testid` values exposed by the application.

The registry is organized by page/component and includes:
- The exact `data-testid` value
- The component or page where it appears
- Brief description of its purpose
- Whether it's static or dynamically generated

### Adding a New Selector

When adding a new `data-testid` to the codebase:
1. Add the `data-testid` attribute to your React component
2. Add an entry to `selector-registry.yaml` under the appropriate section
3. Run `npm run validate-selectors` to ensure consistency
4. CI will fail if selectors in tests don't match the registry

### Selector Naming Convention

Follow this convention for all `data-testid` values:
- **Format**: `{entity-type}-{component}-{action}`
  - `entity-type`: `taxonomy`, `class`, `relationship`, `property`, etc.
  - `component`: `form`, `table`, `modal`, `button`, `input`, etc.
  - `action`: `submit`, `cancel`, `delete`, `add`, etc.
  
- **Examples**:
  - `taxonomy-form` (the form for creating/editing taxonomies)
  - `taxonomy-title-input` (input field for taxonomy title)
  - `class-table` (table displaying classes)
  - `relationship-delete-modal` (delete confirmation modal for relationships)

### Dynamic Selectors

For row identifiers or dynamic content, append the entity ID:
- `${entity-type}-row-${id}` (e.g., `class-row-123e4567-e89b-12d3-a456-426614174000`)
- `${entity-type}-${action}-button-${id}` (e.g., `taxonomy-edit-button-abc123`)

These are listed in the registry as templates (e.g., `{taxonomy}-row-{id}`).

---

## References

- **API Types**: `ux/src/api/client/types.ts` — Generated from OpenAPI spec; source of truth for entity fields
- **Architecture Design**: `rearchitecture/architecture_design.md` — Bounded contexts and domain design
- **E2E Testing**: `ux/e2e/README.md` — How to write and run e2e tests
- **Selector Registry**: `selector-registry.yaml` — Complete list of `data-testid` values
