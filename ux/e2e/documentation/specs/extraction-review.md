# Test Plan: Extraction Review (paste → run → review → apply → revert)

## Overview

End-to-end coverage for `/app/pipelines/review` (GitHub issue #1233, milestone #1). A reviewer pastes a paragraph, the page auto-picks the `dr_spec` taxonomy and its first concept scheme, and one click on "Run extraction" starts `schema_extraction` and `individual_extraction` on the same text. Each tab is reviewed separately: accept/reject candidates (keyed by the API `candidate_id`: `class-N`, `property-N`, `connection-N`, `triple-N`), merge/keep-separate recognition hits (individual tab), click a highlighted provenance span to select the matching item in the inspector, then apply through a confirm dialog and read the created / merged / skipped summary. Persistence and revert are verified against the real backend API. Also covered: paragraph validation (error on Run, cleared on typing), the stale-paragraph warning, and a failed run with retry on one tab while the other tab completes.

Live LLM extraction never runs. `routeRunsToSeededOutput` (ux/e2e/fixtures/pipeline-runs.ts) intercepts the UI POST `/api/pipelines/{type}/run`, writes a real COMPLETED run with a fixed `output_summary` (built from the request the UI really sent), and fulfils the POST with that run. Candidates, recognition preview, apply, revert and change events all hit the real isolated backend (:8888).

The expected apply/revert results below were verified on 2026-10-23 against a scratch backend built from this worktree, using `seed_pipeline_run.py` with the exact output summaries in this plan. Three backend defects turned up while planning (see "Known Backend Defects"); all three are fixed, and TC3 and TC5 assert the correct revert behaviour.

## Scope

- **Entities involved**: Taxonomy, ConceptScheme, Class, PropertyDefinition, Individual, Relationship, PipelineRun (read-only), ChangeEvent (read-only)
- **Pages involved**: `/app/pipelines/review`
- **External dependencies** (all on the isolated test backend):
  - `GET /api/taxonomies`, `GET /api/taxonomies/{id}/schemes`, `GET /api/pipelines/types/{type}/implementations[/{impl}/configurations]` (page bootstrap)
  - `POST /api/pipelines/{schema_extraction|individual_extraction}/run`: **intercepted** (seeded or failed)
  - `GET /api/pipelines/runs/{id}/schema-extraction-candidates`, `GET /api/pipelines/runs/{id}/individual-extraction-candidates`
  - `POST /api/pipelines/runs/{id}/recognition-preview` (UI sends `confidence_threshold: 0`, `recognition_threshold: 0.9`)
  - `POST /api/pipelines/runs/{id}/apply` (schema: `taxonomy_id` + `concept_scheme_id` query params; individual: `taxonomy_id` + `recognition_threshold=0.9`; body `{accepted_candidate_ids, recognition_decisions?}`)
  - `POST /api/pipelines/runs/{id}/revert`, `GET /api/pipelines/runs/{id}/change-events`
  - Verification reads: `GET /api/classes?concept_scheme_id=`, `GET /api/properties`, `GET /api/relationships?source_id=&property_id=`, `GET /api/individuals?class_id=`, `GET /api/individuals/{id}`
- **DB state**: ontology wiped before each test by `fixtures/app-test`. Pipeline runs are NOT wiped (no delete endpoint), so never assert global run counts; always address runs by the id from the intercepted record.

## Shared Test Data

### Paragraph (`TEXT`, 159 chars)

```
The Order Service exposes the Checkout API, which the Storefront Web App calls to place orders. The Order Service publishes order events to the Billing Engine.
```

### Seed (`seedDrScope(page)`, a local helper inside the spec, not a new factory)

Created in this order (order matters for the taxonomy auto-pick check):

| Ref | How | Data |
|---|---|---|
| `decoy` | `createTaxonomy(page, { title: "Acme Glossary" })` | created FIRST so `taxonomies[0]` is not `dr_spec` |
| `tax` | `apiRequest(page, "/api/taxonomies", { method: "POST", body: { title: "Documentation Robotics", identifier: "dr_spec", description: "DR spec ontology" } })` | select label `Documentation Robotics · dr_spec` |
| `scheme` | `apiRequest` POST `/api/taxonomies/{tax.id}/schemes` with `{ title: "Application Layer", identifier: "application", description: "DR application layer" }` | select label `Application Layer · application` |
| `componentClass` | `createClass(page, scheme.id, { title: "Application Component" })` | |
| `serviceClass` | `createClass(page, scheme.id, { title: "Application Service" })` | |
| `interfaceClass` | `createClass(page, scheme.id, { title: "Application Interface" })` | has NO individuals (keeps recognition for new mentions deterministic, no LLM tiebreak) |
| `exposes` | `createPropertyDefinition(page, { identifier: "exposes", title: "exposes" })` | |
| `orderService` | `createIndividual(page, { title: "Order Service", class_ids: [serviceClass.id] })` | exact-title recognition target |
| `storefront` | `createIndividual(page, { title: "Storefront Web App", class_ids: [componentClass.id] })` | exact-title recognition target |

Field names used are all in `components["schemas"]` of `ux/src/api/types/index.ts`: TaxonomyCreateRequest (`title`, `identifier`, `description`), ConceptSchemeCreateRequest (`title`, `identifier`, `description`), ClassCreateRequest (`title`, `description`), PropertyDefinitionCreateRequest (`identifier`, `title`, `description`), IndividualCreateRequest (`title`, `class_ids`, `description`).

### Schema output summary (`schemaOutput()`), provenance is a **list** of spans

```ts
{
  candidates: [
    { kind: "class", label: "Application Interface", confidence: 0.9,  proposed_definition: "An access point where application services are made available.", provenance: [spanIn(TEXT, "Checkout API")] }, // class-0 (exists → reused)
    { kind: "class", label: "Event Stream",          confidence: 0.82, proposed_definition: "An ordered channel of published domain events.", provenance: [spanIn(TEXT, "order events")] },                 // class-1
    { kind: "class", label: "Billing System",        confidence: 0.41, proposed_definition: null, provenance: [spanIn(TEXT, "Billing Engine")] },                                                              // class-2
    { kind: "property_definition", label: "publishes", confidence: 0.86, proposed_definition: "The subject emits events onto the object.",
      proposed_domain: "Application Service", proposed_range: "Event Stream", provenance: [spanIn(TEXT, "publishes")] },                                                                                       // property-0
  ],
  connections: [
    { subject_ref: "Application Service", predicate: "publishes", object_ref: "Event Stream", confidence: 0.8,  provenance: [spanIn(TEXT, "Order Service publishes order events")] }, // connection-0
    { subject_ref: "Billing System",      predicate: "publishes", object_ref: "Event Stream", confidence: 0.52, provenance: [spanIn(TEXT, "to the Billing Engine")] },               // connection-1
  ],
}
```

Candidate ids returned by the API: `class-0, class-1, class-2, property-0, connection-0, connection-1` (schema tab count 6).

Schema-tab highlight segments (`extraction-review-span`, `data-span-keys`):

| Text | `data-span-keys` |
|---|---|
| `Checkout API` | `class-0` |
| `Order Service ` (second occurrence) | `connection-0` |
| `publishes` | `property-0 connection-0` |
| `order events` | `class-1 connection-0` |
| `to the ` | `connection-1` |
| `Billing Engine` | `class-2 connection-1` |

### Individual output summary (`individualOutput(seed)`), provenance is a **single span object** (a list for `triple-0`)

The production pipelines store triple provenance as one `{quote,start,end}` object (`domain/extraction/services.py` serializes the SourceSpan to a dict). Apply also accepts a list of spans (or a bare string) since the D3 fix, so `triple-0` uses `[spanIn(...)]` to keep that shape covered; the other triples use the production single-object shape. Triple order matters: `triple-0` mints "Checkout API" so `triple-1` can resolve it as its object.

```ts
{
  triples: [
    { subject: { kind: "individual", id: "", label: "Checkout API",       class_ids: [interfaceClass.id] },
      predicate: { property_definition_id: null, label: "is_a" },
      object: { kind: "class", id: interfaceClass.id, label: "Application Interface" },
      confidence: 0.9,  provenance: [spanIn(TEXT, "Checkout API")] },                            // triple-0
    { subject: { kind: "individual", id: "", label: "Order Service",      class_ids: [serviceClass.id] },
      predicate: { property_definition_id: exposes.id, label: "exposes" },
      object: { kind: "individual", id: "", label: "Checkout API", class_ids: [interfaceClass.id] },
      confidence: 0.92, provenance: spanIn(TEXT, "Order Service exposes the Checkout API") },    // triple-1
    { subject: { kind: "individual", id: "", label: "Storefront Web App", class_ids: [componentClass.id] },
      predicate: { property_definition_id: null, label: "calls" },
      object: { kind: "individual", id: "", label: "Checkout API", class_ids: [interfaceClass.id] },
      confidence: 0.85, provenance: spanIn(TEXT, "the Storefront Web App calls") },              // triple-2
    { subject: { kind: "individual", id: "", label: "Billing Engine",     class_ids: [componentClass.id] },
      predicate: { property_definition_id: null, label: "receives" },
      object: { kind: "literal", id: "", label: "order events" },
      confidence: 0.6,  provenance: spanIn(TEXT, "order events to the Billing Engine") },        // triple-3
  ],
}
```

Recognition preview (verified): 4 mentions, 2 matched. Hit ids are assigned by the UI in response order:

| Hit | mention_label | Result | Decision control |
|---|---|---|---|
| `hit-0` | Checkout API | no match → "no match · created as new" | none ("new" chip) |
| `hit-1` | Order Service | exact, 100%, resolves to `orderService.id` | `extraction-review-recognition-decision-hit-1` |
| `hit-2` | Storefront Web App | exact, 100%, resolves to `storefront.id` | `extraction-review-recognition-decision-hit-2` |
| `hit-3` | Billing Engine | no match | none |

Individual-tab highlight segments:

| Text | `data-span-keys` |
|---|---|
| `Order Service` (first occurrence) | `triple-1 hit-1` |
| ` exposes the ` | `triple-1` |
| `Checkout API` | `triple-0 triple-1 hit-0` |
| `the ` / ` calls` | `triple-2` (two segments, use `.first()`) |
| `Storefront Web App` | `triple-2 hit-2` |
| `order events to the ` | `triple-3` |
| `Billing Engine` | `triple-3 hit-3` |

### Locator conventions

- Heimdall Select: `page.getByTestId("extraction-review-taxonomy").locator(".select__trigger")` + `page.getByRole("option", { name })` (same helper as `tests/schema/schema-crud-current-ui.spec.ts`). Assert the chosen value with `toContainText` on the select testid.
- Tabs: `page.getByTestId("extraction-review-tabs").getByRole("tab", { name: /Individual extraction/ })`.
- Candidate-kind filter: `page.getByTestId("extraction-review-schema-candidates").getByRole("radio", { name: /Connections/ })`.
- Confirm dialog: `page.getByRole("dialog").filter({ has: page.getByTestId("extraction-review-schema-confirm") })`, then `.getByRole("button", { name: "Apply 5 accepted" })`. Always scope to the dialog: the apply bar button has the same label.
- Decision state: `aria-pressed="true"` on `...-yes` / `...-no` buttons.
- Toasts: `page.locator("[data-testid^=toast-content-]").filter({ hasText: "<static title>" })` (titles are fixed copy, not mutable data).
- Apply/revert network capture: start `page.waitForRequest(r => r.method() === "POST" && r.url().includes("/api/pipelines/runs/" + runId + "/apply"))` and the matching `waitForResponse` before the confirm click.
- Run-POST counter: `page.on("request", ...)` counting POSTs to `/api/pipelines/{type}/run` per type.
- The first recognition preview can be slow (embedding model loads lazily). Use a 30 s expect timeout on the first `extraction-review-recognition-decision-hit-1` visibility assertion. Never `waitForTimeout`.

## Test Cases

### Test Case 1: Scope auto-pick, paragraph validation and the stale-paragraph warning

- **Preconditions**: `seedDrScope(page)`; `routeRunsToSeededOutput(page, { schema_extraction: schemaOutput(), individual_extraction: individualOutput(seed) })`; run-POST counter attached. Navigate to `/app/pipelines/review`.
- **Steps**:
  1. Wait for `extraction-review-page`.
  2. Assert `extraction-review-taxonomy` contains `Documentation Robotics · dr_spec` (auto-picked over the earlier-created "Acme Glossary") and `extraction-review-scheme` contains `Application Layer · application`. Assert `extraction-review-config-refs` is visible and contains `schema-extraction-default`.
  3. Assert both tabs idle: `extraction-review-schema-idle` is visible; switch to the Individual tab, `extraction-review-individual-idle` is visible; switch back.
  4. With an empty paragraph, click `extraction-review-run`.
  5. Assert `getByText("Paste a paragraph to extract from", { exact: true })` is visible and `extraction-review-text` has `aria-invalid="true"`. Assert the run-POST counter is 0 for both types and `extraction-review-schema-idle` is still visible.
  6. `pressSequentially("T")` into `extraction-review-text` (do NOT blur). Assert the error text has count 0 and `aria-invalid="false"`, which proves it cleared on change, not blur.
  7. `fill("")` then `blur()`. Assert the error is visible again (emptied after an attempted run re-shows on blur).
  8. `fill(TEXT)`. Assert the error has count 0. Click `extraction-review-run`.
  9. Assert `extraction-review-schema-run-meta` contains `COMPLETED` and `extraction-review-schema-candidates` is visible. Assert the Schema tab contains count `6` and the Individual tab contains `4`. Assert counter: exactly 1 POST per type.
  10. Assert `extraction-review-stale` has count 0. `fill(TEXT + " It is owned by the Payments Team.")`.
  11. Assert `extraction-review-stale` is visible and `extraction-review-schema-source` still has text exactly `TEXT` (highlights show the text that was run).
  12. `fill(TEXT)`. Assert `extraction-review-stale` has count 0.
- **Expected Result**: dr_spec is preferred. The empty-paragraph error blocks the run (no POST), clears on the first keystroke, and returns on blur. A valid run completes both tabs. Editing the text after the run shows the stale warning without changing the highlighted run text, and restoring the exact text clears it.
- **Selectors Used**: `extraction-review-page`, `extraction-review-taxonomy`, `extraction-review-scheme`, `extraction-review-config-refs`, `extraction-review-run`, `extraction-review-text`, `extraction-review-tabs`, `extraction-review-schema-idle`, `extraction-review-individual-idle`, `extraction-review-schema-run-meta`, `extraction-review-schema-candidates`, `extraction-review-stale`, `extraction-review-schema-source`
- **Invariants Verified**: INV-7, INV-8, INV-1 (no run POST on invalid input)

### Test Case 2: Schema tab: review, span → inspector, confirm with orphan warning, apply result, persistence

- **Preconditions**: as TC1; `intercepted = await routeRunsToSeededOutput(...)`. Navigate, `fill(TEXT)`, click Run, wait for `extraction-review-schema-run-meta` to contain `COMPLETED`.
- **Steps**:
  1. Assert `extraction-review-schema-run-meta` contains `intercepted.schema_extraction.run.id`. Assert the intercepted request: `documents` equals `[TEXT]`, `scope === tax.id`, `concept_scheme_id === scheme.id`, `implementation_id === "default"`.
  2. **Nothing written yet**: `GET /api/classes?concept_scheme_id={scheme.id}` titles (sorted) equal `["Application Component", "Application Interface", "Application Service"]`.
  3. Classes filter is active by default: `extraction-review-schema-decision-class-0`, `-class-1`, `-class-2` are visible; `extraction-review-schema-decision-property-0` has count 0.
  4. Click `...-decision-class-0-yes`, `...-decision-class-1-yes`, `...-decision-class-2-no`. Assert each has `aria-pressed="true"`.
  5. Click the span `[data-testid="extraction-review-span"][data-span-keys="property-0 connection-0"]`. Assert the Properties radio is checked, `extraction-review-schema-inspector` contains `SCHEMA PROPERTY CANDIDATE` and `publishes`, its `extraction-review-provenance` contains `114–123`, and the clicked span has `aria-current="true"`.
  6. Click `extraction-review-schema-inspector-decision-yes`. Assert `extraction-review-schema-decision-property-0-yes` has `aria-pressed="true"`.
  7. Click the same span again (it cycles through overlapping items). Assert the Connections radio is checked and the inspector contains `SCHEMA CONNECTION CANDIDATE` and `Application Service → publishes → Event Stream`.
  8. Click `...-decision-connection-0-yes` and `...-decision-connection-1-yes`.
  9. Assert `extraction-review-schema-apply-bar` contains `5 accepted`, `1 rejected`, `0 pending`, `Documentation Robotics · dr_spec`, `Application Layer · application`. `extraction-review-schema-apply` is enabled and contains `Apply 5 accepted`.
  10. Click `extraction-review-schema-apply`. Assert `extraction-review-schema-confirm` is visible and `extraction-review-schema-orphan-warning` contains `1 accepted connection points at a proposed class you did not accept` and `Billing System → publishes → Event Stream`.
  11. Start the apply request/response wait, then click the dialog button `Apply 5 accepted`.
  12. Request: query `taxonomy_id === tax.id`, `concept_scheme_id === scheme.id`, no `confidence_threshold`. Body `accepted_candidate_ids` (sorted) equals `["class-0","class-1","connection-0","connection-1","property-0"]` and has no `recognition_decisions`.
  13. Response (200): `classes_created 1`, `classes_skipped 2`, `properties_created 1`, `relationships_created 1`, `applied_candidate_ids ["class-0","class-1","property-0","connection-0"]`, `skipped_candidate_ids ["class-2","connection-1"]`.
  14. UI: `extraction-review-apply-result-created` contains `4 of 5 accepted applied`, `1 classes created`, `1 properties created`, `1 relationships created`. `extraction-review-apply-result-skipped` contains `Billing System → publishes → Event Stream` and has no chip whose exact text is `Billing System` (rejected candidates are not listed). `extraction-review-schema-revert` is visible and `extraction-review-schema-apply` has count 0. A toast titled `Schema candidates applied` contains `4 applied · 1 accepted skipped`.
  15. Persistence via API:
      - `GET /api/classes?concept_scheme_id={scheme.id}` titles (sorted) equal `["Application Component","Application Interface","Application Service","Event Stream"]`. "Application Interface" appears once (reused, not duplicated) and there is no "Billing System".
      - `GET /api/properties?limit=1000` contains exactly one item with `identifier === "publishes"`.
      - `GET /api/relationships?source_id={serviceClass.id}&property_id={publishesId}` returns 1 item whose `target_id` is the Event Stream class id.
- **Expected Result**: Only the accepted selection is applied. The existing class is reused. The orphaned connection is predicted in the confirm dialog and reported as skipped after apply. Graph state matches the response.
- **Selectors Used**: `extraction-review-run`, `extraction-review-text`, `extraction-review-schema-run-meta`, `extraction-review-schema-candidates`, `extraction-review-schema-decision-{class-0,class-1,class-2,property-0,connection-0,connection-1}[-yes/-no]`, `extraction-review-span`, `extraction-review-schema-source`, `extraction-review-schema-inspector`, `extraction-review-schema-inspector-decision-yes`, `extraction-review-provenance`, `extraction-review-schema-apply-bar`, `extraction-review-schema-apply`, `extraction-review-schema-confirm`, `extraction-review-schema-orphan-warning`, `extraction-review-apply-result-created`, `extraction-review-apply-result-skipped`, `extraction-review-schema-revert`, `toast-content-*`
- **Invariants Verified**: INV-1, INV-2, INV-3, INV-9

### Test Case 3: Schema tab: revert removes what the run created

- **Preconditions**: as TC2 through the run. Accept `class-1`, `property-0`, `connection-0` only (switch radios as needed), apply via the confirm dialog (`Apply 3 accepted`), and wait for `extraction-review-schema-revert`. Capture `eventStreamId` and `publishesId` from `GET /api/classes` and `GET /api/properties`.
- **Steps**:
  1. `GET /api/pipelines/runs/{runId}/change-events` has at least 3 items (class, property definition, relationship creates).
  2. Start a wait on the revert response, then click `extraction-review-schema-revert`.
  3. Revert response: `classes_deleted 1`, `properties_deleted 1`, `relationships_deleted 1`, `events_reverted >= 3`.
  4. UI: a toast titled `Run reverted` is visible. `extraction-review-schema-apply` is visible again with `Apply 3 accepted`. `extraction-review-apply-result-created` has count 0.
  5. API: no class titled "Event Stream" in the scheme; no property with identifier `publishes`; `GET /api/relationships?source_id={serviceClass.id}&property_id={publishesId}` is empty. The three seeded classes and `exposes` still exist.
- **Expected Result**: Revert deletes exactly the DRAFT entities this run created and leaves seeded data alone.
- **Selectors Used**: `extraction-review-schema-decision-*`, `extraction-review-schema-apply`, `extraction-review-schema-confirm`, `extraction-review-schema-revert`, `extraction-review-apply-result-created`, `toast-content-*`
- **Invariants Verified**: INV-5

### Test Case 4: Individual tab: triples, recognition merge / same-title lock, span → inspector, apply, persistence

- **Preconditions**: as TC2 through the run; switch to the Individual tab.
- **Steps**:
  1. Assert `extraction-review-individual-run-meta` contains `COMPLETED` and `intercepted.individual_extraction.run.id`. Intercepted request: `text === TEXT`, `ontology_id === tax.id`, `ontology_name === "Documentation Robotics"`.
  2. Assert `extraction-review-individual-decision-triple-0` … `-triple-3` are visible. Wait (30 s) for `extraction-review-recognition-decision-hit-1` and `-hit-2`. Assert `extraction-review-recognition-decision-hit-0` and `-hit-3` have count 0, and `extraction-review-recognition` contains `no match · created as new`.
  3. Click the span `[data-span-keys="triple-2"]` (`.first()`). Assert `extraction-review-individual-inspector` contains `TRIPLE CANDIDATE` and `Storefront Web App → calls → Checkout API`.
  4. Click the span `[data-span-keys="triple-1 hit-1"]`. Assert the inspector contains `Order Service → exposes → Checkout API`. Click the same span again. Assert `extraction-review-recognition-inspector` is visible and contains `Order Service`, `existing individual`, `exact`, `100%`, and `extraction-review-individual-inspector` has count 0.
  5. Click `...-individual-decision-triple-0-yes`, `-triple-1-yes`, `-triple-2-yes`, `-triple-3-no`. Assert `aria-pressed="true"` on each. Click `extraction-review-recognition-decision-hit-1-yes` (Merge). Assert pressed. Assert `extraction-review-recognition-decision-hit-2-no` (Keep separate) is disabled with a title mentioning that titles are unique per class (hit-2 is an exact same-class title match).
  6. Assert `extraction-review-individual-apply-bar` contains `3 accepted`, `1 rejected`, `0 pending`, `1 merge`, `0 keep separate`, `threshold 0.90`.
  7. **Nothing written yet**: `GET /api/individuals?class_id={interfaceClass.id}` returns 0 items.
  8. Click `extraction-review-individual-apply`. Assert `extraction-review-individual-confirm` contains `3 accepted triples`, `1 merge into existing`, `0 kept separate`, `1 same title · merges automatically`, and does not contain `left to recognition`.
  9. Start the apply wait, then click the dialog button `Apply 3 accepted`.
  10. Request: query `taxonomy_id === tax.id`, `recognition_threshold === "0.9"`. Body `accepted_candidate_ids` (sorted) equals `["triple-0","triple-1","triple-2"]`, and `recognition_decisions` equals `[{ mention_label: "Order Service", decision: "merge", individual_id: orderService.id }]` (no decision is sent for the undecided Storefront Web App hit).
  11. Response (200): `individuals_created 1`, `relationships_created 1`, `applied_candidate_ids ["triple-0","triple-1","triple-2"]`, `skipped_candidate_ids ["triple-3"]`, `merged_mentions [{ mention_label: "Order Service", individual_id: orderService.id, source: "decision" }, { mention_label: "Storefront Web App", individual_id: storefront.id, source: "existing_title" }]`.
  12. UI: `extraction-review-apply-result-created` contains `3 of 3 accepted applied`, `1 individuals created`, `1 relationships created`. `extraction-review-apply-result-merged` contains `Order Service → Order Service` with chip `your merge`, and `Storefront Web App → Storefront Web App` with chip `same title`. `extraction-review-apply-result-skipped` has count 0 (triple-3 was rejected, not accepted-but-skipped). `extraction-review-individual-revert` is visible. A toast titled `Individuals applied` contains `3 applied · 0 accepted skipped`.
  13. Persistence via API:
      - `GET /api/individuals?class_id={interfaceClass.id}` has exactly one item, titled `Checkout API` (record its id as `checkoutId`).
      - `GET /api/individuals?class_id={serviceClass.id}` has exactly one item, with id `orderService.id` (merge did not duplicate).
      - `GET /api/individuals?class_id={componentClass.id}` has exactly one item, `Storefront Web App` (no duplicate, and "Billing Engine" was not created).
      - `GET /api/relationships?source_id={orderService.id}&property_id={exposes.id}` has 1 item whose `target_id === checkoutId`.
      - `GET /api/pipelines/runs/{runId}/change-events` contains an item with `entity_id === checkoutId`, `entity_type === "individual"`, `operation === "create"`.
- **Expected Result**: Accepted triples are applied. The merge reuses the existing Order Service and keeps its relationship. The rejected triple writes nothing. The result panel reports created / merged correctly.
- **Note (same-title lock)**: an exact-title hit in the mention's class cannot be kept separate, because individual titles are unique per class (documented in `IndividualExtractionApplyService.apply`): the server always resolves it to the existing individual and reports it as merged with source `existing_title` ("same title"). The UI therefore disables "Keep separate" for those hits and counts undecided ones as "same title · merges automatically" (resolves Q1).
- **Selectors Used**: `extraction-review-tabs`, `extraction-review-individual-run-meta`, `extraction-review-triples`, `extraction-review-individual-decision-{triple-0..3}[-yes/-no]`, `extraction-review-recognition`, `extraction-review-recognition-decision-{hit-1,hit-2}[-yes/-no]`, `extraction-review-span`, `extraction-review-individual-source`, `extraction-review-individual-inspector`, `extraction-review-recognition-inspector`, `extraction-review-individual-apply-bar`, `extraction-review-individual-apply`, `extraction-review-individual-confirm`, `extraction-review-apply-result-created`, `extraction-review-apply-result-merged`, `extraction-review-apply-result-skipped`, `extraction-review-individual-revert`, `toast-content-*`
- **Invariants Verified**: INV-1, INV-2, INV-3, INV-4, INV-9

### Test Case 5: Individual tab: revert removes the minted individual and its relationship

- **Preconditions**: as TC4 through the run and recognition load. Accept `triple-0` and `triple-1` only. Merge `hit-1`. Leave `hit-2` undecided.
- **Steps**:
  1. Click `extraction-review-individual-apply`. Assert `extraction-review-individual-confirm` contains `1 same title · merges automatically` (the undecided hit-2) and not `left to recognition`. Confirm `Apply 2 accepted`. The request body `recognition_decisions` contains only the Order Service merge. Response: `individuals_created 1`, `relationships_created 1`. Record `checkoutId`.
  2. Start a wait on the revert response, then click `extraction-review-individual-revert`.
  3. Revert response: `individuals_deleted 1`, `relationships_deleted 1`.
  4. UI: a toast titled `Run reverted` is visible. `extraction-review-individual-apply` is visible with `Apply 2 accepted`. `extraction-review-apply-result-created` has count 0.
  5. API: `GET /api/individuals?class_id={interfaceClass.id}` is empty. `GET /api/individuals/{orderService.id}` is 200 (merge target untouched). `GET /api/relationships?source_id={orderService.id}&property_id={exposes.id}` is empty (no dangling relationship to the deleted `checkoutId`).
- **Expected Result**: Revert removes everything the run created (individual and relationship) and never touches the pre-existing merge target.
- **Selectors Used**: `extraction-review-individual-decision-*`, `extraction-review-recognition-decision-hit-1-yes`, `extraction-review-individual-apply`, `extraction-review-individual-confirm`, `extraction-review-individual-revert`, `extraction-review-apply-result-created`, `toast-content-*`
- **Invariants Verified**: INV-4, INV-5

### Test Case 6: One tab fails, the other completes; retry only the failed tab

- **Preconditions**: `seedDrScope(page)`; `routeRunToFailure(page, "schema_extraction", "LLM provider timed out")`; `const ind = await routeRunsToSeededOutput(page, { individual_extraction: individualOutput(seed) })`; run-POST counter. Navigate, `fill(TEXT)`, click Run.
- **Steps**:
  1. Assert `extraction-review-schema-failed` is visible and contains `Run failed: LLM provider timed out. The other extraction tab is unaffected.` Assert `extraction-review-schema-run-meta` contains `FAILED`, `extraction-review-schema-retry` is visible, and `extraction-review-schema-apply-bar` has count 0.
  2. Switch to the Individual tab. Assert `extraction-review-individual-run-meta` contains `COMPLETED` and `ind.individual_extraction.run.id`. Click `extraction-review-individual-decision-triple-0-yes` and assert pressed.
  3. `await page.unroute("**/api/pipelines/schema_extraction/run")`, then `const schema = await routeRunsToSeededOutput(page, { schema_extraction: schemaOutput() })`.
  4. Switch to the Schema tab and click `extraction-review-schema-retry`.
  5. Assert `extraction-review-schema-run-meta` contains `COMPLETED` and `schema.schema_extraction.run.id`. `extraction-review-schema-decision-class-0` is visible and `extraction-review-schema-failed` has count 0. The retried request still carries `documents: [TEXT]`, `scope: tax.id`, `concept_scheme_id: scheme.id`.
  6. Other tab untouched: the counter shows exactly 1 individual_extraction POST and 2 schema_extraction POSTs. On the Individual tab the run-meta still shows the original `ind.individual_extraction.run.id` and `...-decision-triple-0-yes` still has `aria-pressed="true"`.
- **Expected Result**: A failed run is isolated to its tab with the server reason and a retry. Retry re-runs only that pipeline with the last request, and the other review session (run and decisions) survives.
- **Selectors Used**: `extraction-review-run`, `extraction-review-text`, `extraction-review-tabs`, `extraction-review-schema-failed`, `extraction-review-schema-run-meta`, `extraction-review-schema-retry`, `extraction-review-schema-apply-bar`, `extraction-review-schema-decision-class-0`, `extraction-review-individual-run-meta`, `extraction-review-individual-decision-triple-0-yes`
- **Invariants Verified**: INV-6

## Invariants

`ux/e2e/documentation/app-context.md` does not exist in this repo (only `legacy/legacy_ux/e2e/documentation/app-context.md`), so the invariants are taken from the page copy, the apply route docstrings and CLAUDE.md:

- **INV-1** Nothing is written until apply (page subtitle). Invalid input sends no run POST.
- **INV-2** `accepted_candidate_ids` is the full selection. Everything else is skipped regardless of confidence.
- **INV-3** Existing entities are reused, not duplicated (class title per scheme, property identifier, individual title per class).
- **INV-4** A merge decision reuses the existing individual. The merge target is never modified or deleted.
- **INV-5** Revert removes everything the run created ("Revert removes everything this run created") and nothing else.
- **INV-6** One tab failing never blocks the other. Retry re-runs only that pipeline.
- **INV-7** Validation errors clear on `onChange`, not only on blur (CLAUDE.md Form Validation Behavior).
- **INV-8** Highlights show the text that was run. Editing afterwards shows the stale warning.
- **INV-9** The apply summary lists only accepted-but-skipped candidates as skipped, not unselected ones.

## Coverage Analysis

### CRUD Coverage

- **Create**: Class, PropertyDefinition, Relationship (schema apply, TC2); Individual and Relationship (individual apply, TC4).
- **Read**: candidates for both pipeline types; recognition preview; post-apply API reads for every created entity; change events (TC3, TC4).
- **Update**: none. Review decisions are client state, and apply reuses existing entities without modifying them (asserted: no duplicates, merge target intact).
- **Delete**: run revert (TC3 schema, TC5 individual). Test-data teardown via `clearTestData`.

### Edge Cases

- **Concurrency / version mismatch**: N/A. Apply/revert carry no entity versions. Superseded run results (the generation counter in `useExtractionReviewRuns`) are covered by unit tests, not E2E.
- **Cascade deletes**: TC5 checks that reverting a minted individual also removes its relationship (the D2 regression).
- **Orphaned relationships**: TC2 (orphan-warning connection skipped on apply); TC5 (dangling relationship after revert).
- **Reference integrity**: TC2 reuses an existing class by title. TC4 merges into an existing individual. Rejected candidates and unaccepted classes are never materialised.
- **Overlapping provenance**: TC2 and TC4 click overlapped segments twice to prove cycling.
- **Failed run isolation + retry**: TC6.

### Anti-Pattern Validations

- ✓ No fixed timeouts. Every wait is a DOM/network condition (`toBeVisible`, `toHaveAttribute`, `waitForRequest` / `waitForResponse`); the only extended timeout is a 30 s expect on the first recognition-preview render.
- ✓ No hardcoded UUIDs. All ids come from factory/apiRequest returns or the intercepted run record. `class-0` / `triple-0` / `hit-1` are positional API/UI keys, not UUIDs.
- ✓ No invented selectors. Every `data-testid` is registered under `extraction-review-*` or `toast-content-*`. Other locators are ARIA roles (`tab`, `radio`, `option`, `dialog`, `button`), the `.select__trigger` class already used by `schema-crud-current-ui.spec.ts`, and `data-span-keys` / `aria-pressed` / `aria-current` attributes on registered elements.
- ✓ No vacuous assertions. Every assertion checks a concrete value, count, attribute or API state.
- ✓ No text selectors for mutable content. Text matching is limited to fixed UI copy (validation message, toast titles, chip copy) or assertions inside a registered container, never used to locate rows.
- ✓ No global pipeline-run counts. Runs are addressed by the intercepted id; the POST counter is per-test via `page.on("request")`.

### Cleanup

- `fixtures/app-test` wipes all ontology data before each test (the suite isolation mechanism).
- Each test also calls `clearTestData(page)` in `test.afterEach` so apply-created DRAFT entities do not leak.
- Routes are per-page and drop with the page. Pipeline runs persist by design and are not asserted globally.

## Known Backend Defects (found while planning; all fixed)

- **D1 (high) – schema apply recorded no change events, so revert was a no-op.** Fixed in 88d3dfd4 (schema apply now records ChangeEvents); TC3 covers it.
- **D2 (high) – relationships created by individual apply were not recorded, so revert left them dangling.** Fixed in 88d3dfd4; TC5 covers it.
- **D3 (low) – individual apply 500'd on list-shaped triple provenance.** `_triple_context` called `provenance.get(...)` on a list. Fixed in this PR: apply accepts a span dict, a list of spans or a string. `triple-0` in TC4/TC5 uses a list to cover it.

## Open Questions

No registry gaps: every selector this plan needs is registered. Non-blocking questions:

- **Q1 (product, resolved)**: "Keep separate" had no effect on exact same-class title hits. The UI now disables it for those hits (see the TC4 note).
- **Q2 (docs)**: `ux/e2e/documentation/app-context.md`, `ux/src/api/client/types.ts` and `ux/e2e/reports/` named in the planner contract do not exist. Fields were verified against `ux/src/api/types/index.ts`, and there were no run reports to mine for selector-coverage gaps.

## Factory Usage

- `createTaxonomy` (decoy taxonomy), `createClass` (x3), `createPropertyDefinition` (`exposes`), `createIndividual` (x2), `clearTestData` (afterEach), all from `ux/e2e/fixtures/factories.ts`.
- `apiRequest` from `ux/e2e/fixtures/api-client.ts`: `dr_spec` taxonomy and `application` scheme (the factories do not pass `identifier`), plus every persistence/verification read.
- `routeRunsToSeededOutput`, `routeRunToFailure`, `spanIn` from `ux/e2e/fixtures/pipeline-runs.ts`.
- `test`, `expect` from `ux/e2e/fixtures/app-test.ts`.
- Spec-local helpers only (no new fixtures): `seedDrScope`, `schemaOutput`, `individualOutput`, `selectOption`, `confirmDialog(kind)`, `countRunPosts(page)`.
- Suggested file: `ux/e2e/tests/pipelines/extraction-review.spec.ts`.

## Demo path

Human walkthrough of the seeded DR POC with a **live LLM**. This is the demo, not the E2E suite.

1. Seed a fresh scratch DB (from `local-server/`, server stopped): `.venv/bin/python scripts/seed_dr_poc.py --db-dir <scratch> --write-config <scratch>/config.json --base-config ./config.json`. It migrates `<scratch>/local.db` and `<scratch>/operations.db`, imports the DR spec from the sibling `../documentation_robotics/spec` as taxonomy `dr_spec` (pass `--spec-dir` for another checkout), imports `documentation-robotics/model/` as individuals and relationships, rebuilds the schema and individual vector indexes, and verifies counts (exit 1 on any failed check). It does not touch `experiments/ledger.jsonl`. Against the 0.10.0 spec checkout it reports 13 schemes, 191 classes, 1589 property definitions, 450 individuals and 584 relationships, nothing skipped. Re-running is idempotent. The demo DB is throwaway and intentionally uses whatever spec version the sibling checkout has; the workspace DB stays on spec 0.8.4.
2. `<scratch>/config.json` is a copy of `--base-config` with only the database paths changed, so it carries your LLM keys. The app refuses to start without at least one key; the demo needs a real OpenRouter or Anthropic key.
3. Start the backend: `cd local-server && CONFIG_PATH=<scratch>/config.json .venv/bin/python app.py` (port from the base config). Start the UX: `cd ux && npm run dev` (port 3100, `VITE_API_BASE_URL` pointing at the backend).
4. Open `http://localhost:3100/app/pipelines/review`. The taxonomy auto-picks `… · dr_spec`. Pick the concept scheme that should receive new schema (for example the application layer) and keep configuration `default`.
5. Paste the opening paragraph of the repo `README.md` ("Context Studio is a local-first application for building and curating knowledge graphs, …") and click **Run extraction**. Both runs call the LLM (tens of seconds).
6. Review. **Schema** tab: click highlights to jump between proposed classes, properties and connections, then accept or reject. **Individual** tab: check triples whose nodes show `mapped` against the imported DR individuals; each node's class line reads `L<nn> · <class title>` (for example `L04 · Application Component`), and the inspector adds a `dr_layer` row. Classes from a layer outside the 12 known DR layers (0.10.0's Product layer) show the class title only. Under **Recognition · dedup hits**, Merge mentions that are existing DR elements and Keep separate the rest (Keep separate is disabled for exact same-class title matches, which always merge).
7. Apply each tab through its confirm dialog and read the created / merged / skipped summary.
8. Open `/app/graph` to see the new draft nodes and edges wired into the imported DR model. Reverting either tab removes everything that run created.
