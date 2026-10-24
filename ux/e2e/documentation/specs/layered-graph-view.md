# Test Plan: Layered Graph View

## Overview

The `/app/graph` page renders the ontology as a layered graph built from `GET /api/graph/view`
(`GraphAnalysisService.get_graph_view`). **Concept schemes are layers.** Only **classes and
individuals become nodes**: taxonomies and concept schemes are *not* nodes (taxonomies group the
layer filter; schemes become layer bands/headers). Edges come from asserted relationships
(`edge_type: relationship`), property-definition domain to range (`schema`), individual to class
membership (`instance_of`) and class to parent (`subclass_of`). An individual's layer is the
`concept_scheme_id` of its first class.

This plan covers the layer filter (hide/show a layer and its nodes), the inspector (selecting a node
shows its details; switching selection), focus mode (neighbourhood-only rendering with a depth
control, re-focus from the inspector, and exit), and the layered/force layout switch.

### Behaviour verified in the source (drives the assertions)

- **Default filter** (`ux/src/components/graph/graphLayers.ts`): layers = first 3 layers of the
  taxonomy with the most layers; node kind = `individual` when any individual exists, else `class`.
  With the seed below both layers are on and **only individuals render by default**.
- **Layer filter** removes nodes from the DOM (not dimmed). Edges are kept only when both endpoints
  are visible.
- **Focus mode removes** non-neighbourhood nodes (no dimming). The neighbourhood is computed
  client-side, ignores the layer filter, honours the node-kind filter (non-matching nodes other than
  the focus node are skipped), and treats edges as undirected. While focused the toolbar swaps the
  layer/class filters for `graph-focus-bar`; the focused node's `GraphNode` gets class
  `graph-node--focus`.
- **Layer headers** are only rendered in layered layout
  (`data-testid="graph-layer-header-<conceptSchemeId>"`). In force layout there are no headers.
- **Selection cannot be cleared**: the page has no deselect path (no close button, background click
  does not deselect, exiting focus keeps the selection). See Open Questions. "Closing" is covered as
  the initial empty inspector state plus *switching* the selection.

### DOM notes for the generator

- The canvas is Heimdall `GraphCanvas`: each node is an SVG `<g data-testid="graph-node-<id>">`
  wrapping a `<foreignObject>` whose child is our `GraphNode`
  `<div role="button" aria-pressed aria-label="<label> (<node_type>)">`. Edges are
  `<g aria-hidden="true">`. The `graph-node-*` / `graph-edge-*` ids are emitted by Heimdall and
  **are not in the registry**; do not use them.
- **Locate nodes by role**, scoped to the canvas:
  `page.getByTestId("graph-canvas").getByRole("button", { name: "CRM System (individual)" })`.
  Labels are fixed seed titles, not mutable content.
- Heimdall renders a hidden measurement copy of every node (`.graph-measure`, `visibility:hidden`,
  `aria-hidden`). Role locators skip it automatically, but **`getByTestId("graph-layer-header-...")`
  matches twice**. Use `.filter({ visible: true })` for presence/text assertions and
  `toHaveCount(0)` on the unfiltered locator for absence.
- Assert edges through `graph-visible-counts` text (`"<n> nodes · <m> edges"`) and
  `graph-legend-cross-layer-count`, never via SVG paths.
- Segmented controls (`graph-layout-toggle`, `graph-node-kind-filter`, `graph-focus-depth`) render
  `role="radiogroup"` with `role="radio"` + `aria-checked` buttons labelled
  Layered/Force, All/Classes/Individuals, "1 hop"/"2 hops"/"3 hops".
- Layer-filter items render `role="option"` with `aria-selected` inside `graph-layer-filter-panel`
  (opened by clicking `graph-layer-filter`, which has `aria-expanded`). The accessible name starts
  with the scheme title (identifier appended as description), so match `{ name: /^Application/ }`
  and `{ name: /^Business/ }`.
- Inspector relationship targets are buttons with `aria-label="Navigate to <title>"`.

## Scope

- **Entities involved**: Taxonomy, ConceptScheme (layers), Class, Individual, PropertyDefinition, Relationship
- **Pages involved**: `/app/graph`
- **External dependencies**: isolated backend on :8888 (`ux/e2e/global-setup.ts`, fresh DB);
  `GET /api/graph/view`; seed endpoints `POST /api/taxonomies`, `/api/taxonomies/{id}/schemes`,
  `/api/schemes/{id}/classes`, `/api/individuals`, `/api/properties`, `/api/relationships`.
  The `app-test` fixture wipes ontology data (`clearTestData`) before each test.

## Seed Data (shared `beforeEach`, all via factories)

| Var | Factory call | Notes |
|---|---|---|
| `tax` | `createTaxonomy(page, { title: "Enterprise Model" })` | |
| `app` | `createConceptScheme(page, tax.id, { title: "Application" })` | layer A |
| `biz` | `createConceptScheme(page, tax.id, { title: "Business" })` | layer B |
| `appComponent` | `createClass(page, app.id, { title: "Application Component" })` | layer A |
| `bizService` | `createClass(page, biz.id, { title: "Business Service" })` | layer B |
| `bizProcess` | `createClass(page, biz.id, { title: "Business Process" })` | layer B |
| `customerService` | `createClass(page, biz.id, { title: "Customer Service", parent_class_id: bizService.id })` | layer B; `subclass_of` edge |
| `crm` | `createIndividual(page, { title: "CRM System", description: "Customer relationship management platform", class_ids: [appComponent.id] })` | layer A |
| `billing` | `createIndividual(page, { title: "Billing Service", class_ids: [bizService.id] })` | layer B |
| `orderHandling` | `createIndividual(page, { title: "Order Handling", class_ids: [bizProcess.id] })` | layer B; never in CRM's neighbourhood |
| `realizes` | `createPropertyDefinition(page, { identifier: "realizes", title: "Realizes" })` | |
| `rel` | `createRelationship(page, crm.id, billing.id, realizes.id, "realizes")` | cross-layer A to B |

Note: `POST /api/relationships` resolves the predicate from `relationship_type` via
get-or-create-by-identifier (title defaults to `"Realizes"`), so the predicate shown is `"Realizes"`
either way. Schema (domain to range) edges cannot be seeded: the property factory/API has no
domain/range fields (see Open Questions).

Then `page.goto("/app/graph")` and wait for `graph-canvas` to be visible.

### Expected graph (from `get_graph_view`)

- Nodes (7): classes Application Component (A), Business Service (B), Business Process (B),
  Customer Service (B); individuals CRM System (A), Billing Service (B), Order Handling (B).
- Edges (5): `relationship` CRM to Billing (**cross-layer**); `instance_of` CRM to Application
  Component, Billing to Business Service, Order Handling to Business Process; `subclass_of`
  Customer Service to Business Service.

| View | Visible nodes | `graph-visible-counts` | cross-layer count |
|---|---|---|---|
| Default (both layers, kind = Individuals) | CRM, Billing, Order Handling | `3 nodes · 1 edges` | 1 |
| Kind = All, both layers | all 7 | `7 nodes · 5 edges` | 1 |
| Default, Application hidden | Billing, Order Handling | `2 nodes · 0 edges` | 0 |
| Focus CRM, kind All, depth 1 | CRM, Application Component, Billing | `3 nodes · 2 edges` | 1 |
| Focus CRM, kind All, depth 2 | + Business Service | `4 nodes · 3 edges` | 1 |
| Focus CRM, kind All, depth 3 | + Customer Service | `5 nodes · 4 edges` | 1 |

## Test Cases

Header test ids below are written `graph-layer-header-<app.id>`, meaning the prefix
`graph-layer-header-` followed by the factory-returned scheme id.

### Test Case 1: Layered layout renders one band per concept scheme with the default individual slice
- **Preconditions**: seed data; on `/app/graph`.
- **Steps**:
  1. Wait for `graph-canvas` visible.
  2. Click `graph-node-kind-filter` radio "All".
- **Expected Result**:
  - After 1: `graph-canvas` has `data-layout="layered"`; `graph-layout-toggle` radio "Layered" has
    `aria-checked="true"`; `graph-node-kind-filter` radio "Individuals" has `aria-checked="true"`.
  - `graph-layer-header-<app.id>` (visible-filtered) is visible and contains "Application" and "1";
    `graph-layer-header-<biz.id>` (visible-filtered) is visible and contains "Business" and "2".
  - Node buttons visible: "CRM System (individual)", "Billing Service (individual)",
    "Order Handling (individual)". Class node buttons have count 0, e.g.
    "Application Component (class)", "Business Service (class)".
  - `graph-visible-counts` has text `3 nodes · 1 edges`.
  - `graph-layer-legend` visible; `graph-legend-layer` has count 2;
    `graph-legend-cross-layer-count` has text `1`.
  - `graph-layer-filter` contains "2 selected".
  - After 2: `graph-visible-counts` = `7 nodes · 5 edges`; "Customer Service (class)" and
    "Application Component (class)" visible; `graph-layer-header-<biz.id>` (visible) contains "5";
    `graph-legend-cross-layer-count` still `1`.
- **Selectors Used**: `graph-page`, `graph-canvas`, `graph-layout-toggle`, `graph-node-kind-filter`,
  `graph-layer-header-{conceptSchemeId}`, `graph-visible-counts`, `graph-layer-legend`,
  `graph-legend-layer`, `graph-legend-cross-layer-count`, `graph-layer-filter` (+ role locators)
- **Invariants Verified**: schemes are layers; only classes/individuals are nodes (no taxonomy or
  scheme node buttons); an individual's layer is its first class's scheme; relationship,
  instance_of and subclass_of edges are emitted; cross-layer edges are detected.

### Test Case 2: Layer filter hides and restores a layer and the nodes it contains
- **Preconditions**: seed data; default view (kind = Individuals).
- **Steps**:
  1. Click `graph-layer-filter`; assert `graph-layer-filter-panel` visible.
  2. In the panel, assert options `/^Application/` and `/^Business/` have `aria-selected="true"`.
  3. Click option `/^Application/`; assert it has `aria-selected="false"`.
  4. Close the panel (click `graph-layer-filter` again, or press Escape); assert panel hidden.
  5. Re-open the panel, click option `/^Application/` again, close the panel.
  6. Re-open, click options `/^Application/` and `/^Business/` (both deselected), close the panel.
- **Expected Result**:
  - After 3-4: `graph-layer-header-<app.id>` has count 0; "CRM System (individual)" count 0;
    "Billing Service (individual)" and "Order Handling (individual)" visible;
    `graph-visible-counts` = `2 nodes · 0 edges`; `graph-legend-cross-layer-count` = `0`;
    `graph-legend-layer` count 1; `graph-layer-filter` contains "Business".
  - After 5: `graph-layer-header-<app.id>` (visible) visible again; "CRM System (individual)"
    visible; counts back to `3 nodes · 1 edges`; cross-layer `1`.
  - After 6: `graph-canvas-empty` visible; no node buttons inside `graph-canvas`;
    `graph-layer-legend` count 0; `graph-visible-counts` = `0 nodes · 0 edges`;
    `graph-layer-filter` contains "None".
- **Selectors Used**: `graph-layer-filter`, `graph-layer-filter-panel`,
  `graph-layer-header-{conceptSchemeId}`, `graph-canvas`, `graph-canvas-empty`,
  `graph-visible-counts`, `graph-legend-layer`, `graph-legend-cross-layer-count`, `graph-layer-legend`
- **Invariants Verified**: hiding a layer removes every node in it and every edge touching it;
  re-showing restores them; an empty selection shows an explicit status, not a blank canvas.

### Test Case 3: Inspector shows the selected node's details and relationships
- **Preconditions**: seed data; default view.
- **Steps**:
  1. Assert `node-inspector` contains "No node selected" and `node-inspector-relationship-count`
     has count 0.
  2. Click node "CRM System (individual)" in `graph-canvas`.
  3. Click node "Billing Service (individual)".
- **Expected Result**:
  - After 2: CRM node button `aria-pressed="true"`. `node-inspector` contains "CRM System",
    "Individual", "Customer relationship management platform", "Application Component" (Class row),
    "Application" (Layer row), "Enterprise Model" (Taxonomy row), and predicates "Realizes" and
    "instance of". `node-inspector-relationship-count` = `2 relationships`. `node-inspector`
    contains buttons named "Navigate to Billing Service" and "Navigate to Application Component".
    `node-inspector-focus-button` enabled with `aria-pressed="false"`; `graph-focus-bar` count 0.
  - After 3: CRM button `aria-pressed="false"`, Billing button `aria-pressed="true"`;
    `node-inspector` contains "Billing Service", "Business Service", "Business" and button
    "Navigate to CRM System" (incoming); `node-inspector-relationship-count` = `2 relationships`;
    "Customer relationship management platform" no longer in `node-inspector`.
- **Selectors Used**: `graph-canvas`, `node-inspector`, `node-inspector-relationship-count`,
  `node-inspector-focus-button`, `graph-focus-bar` (+ role locators)
- **Invariants Verified**: inspector reflects exactly one selected node; relationships include both
  directions and instance_of membership; layer and taxonomy resolve from the scheme.

### Test Case 4: Focus mode shows only the selected node's neighbourhood, by depth, and exits cleanly
- **Preconditions**: seed data; click `graph-node-kind-filter` radio "All"; assert
  `graph-visible-counts` = `7 nodes · 5 edges`.
- **Steps**:
  1. Click node "CRM System (individual)"; click `node-inspector-focus-button`.
  2. Click `graph-focus-depth` radio "2 hops".
  3. Click `graph-focus-depth` radio "3 hops".
  4. In `node-inspector`, click button "Navigate to Billing Service".
  5. Click `graph-focus-exit`.
- **Expected Result**:
  - After 1: `graph-focus-bar` visible; `graph-focus-label` = "CRM System"; `graph-layer-filter` and
    `graph-class-filter` count 0; `graph-focus-depth` radio "1 hop" `aria-checked="true"`;
    `node-inspector-focus-button` disabled, `aria-pressed="true"`, contains "Focused";
    CRM button has class `graph-node--focus`. Visible: CRM, "Application Component (class)",
    "Billing Service (individual)". Count 0: "Order Handling (individual)",
    "Business Process (class)", "Business Service (class)", "Customer Service (class)".
    `graph-visible-counts` = `3 nodes · 2 edges`; `graph-legend-cross-layer-count` = `1`.
  - After 2: "Business Service (class)" visible; `4 nodes · 3 edges`; Order Handling count 0.
  - After 3: "Customer Service (class)" visible; `5 nodes · 4 edges`; Order Handling and
    Business Process still count 0.
  - After 4: `graph-focus-label` = "Billing Service"; Billing button has class `graph-node--focus`
    and `aria-pressed="true"`; CRM button lacks `graph-node--focus`; "3 hops" still
    `aria-checked="true"`; `node-inspector` contains "Billing Service". Billing's 3-hop
    neighbourhood is the same 5 nodes, so counts stay `5 nodes · 4 edges`.
  - After 5: `graph-focus-bar` count 0; `graph-layer-filter` visible; `graph-visible-counts` =
    `7 nodes · 5 edges`; "Order Handling (individual)" visible again; no node button has class
    `graph-node--focus`; `node-inspector` still contains "Billing Service" (selection persists).
- **Selectors Used**: `graph-node-kind-filter`, `graph-canvas`, `node-inspector`,
  `node-inspector-focus-button`, `graph-focus-bar`, `graph-focus-label`, `graph-focus-depth`,
  `graph-focus-exit`, `graph-layer-filter`, `graph-class-filter`, `graph-visible-counts`,
  `graph-legend-cross-layer-count`
- **Invariants Verified**: focus neighbourhood is an undirected N-hop expansion; non-neighbours are
  removed (not dimmed); focus crosses layers; inspector navigation re-focuses; exiting focus
  restores the pre-focus filter.

### Test Case 5: Layout switch layered / force
- **Preconditions**: seed data; default view.
- **Steps**:
  1. Assert `graph-canvas` `data-layout="layered"` and `graph-layer-header-<app.id>` (visible) visible.
  2. Click `graph-layout-toggle` radio "Force".
  3. Click `graph-layout-toggle` radio "Layered".
- **Expected Result**:
  - After 2: `graph-canvas` `data-layout="force"`; radio "Force" `aria-checked="true"`;
    `graph-layer-header-<app.id>` and `graph-layer-header-<biz.id>` count 0; CRM, Billing and
    Order Handling node buttons still visible; `graph-visible-counts` still `3 nodes · 1 edges`;
    `graph-legend-layer` count still 2.
  - After 3: `data-layout="layered"`; radio "Layered" `aria-checked="true"`; both layer headers
    visible again; counts unchanged.
- **Selectors Used**: `graph-canvas`, `graph-layout-toggle`, `graph-layer-header-{conceptSchemeId}`,
  `graph-visible-counts`, `graph-legend-layer` (+ role locators)
- **Invariants Verified**: layout mode changes positioning only (identical node/edge set); layer
  bands exist only in layered mode. Force is enabled because 3 nodes is below
  `FORCE_LAYOUT_MAX_NODES` (250).

## Coverage Analysis

### CRUD Coverage
- **Create**: all entities created via factories (setup only; the graph page is read-only).
- **Read**: TC1-TC5 read the graph view (layers, nodes, edges, inspector details).
- **Update / Delete**: not applicable; the graph page has no mutation UI ("Rebuild Graph" rebuilds
  the analysis engine and does not change `/api/graph/view`). Out of scope.

### Edge Cases
- Empty layer selection shows `graph-canvas-empty` (TC2 step 6).
- Cross-layer edge counting under layer filter and focus (TC2, TC4).
- Node-kind filter interplay with focus: TC4 runs with kind = All; with kind = Individuals the
  CRM neighbourhood would be only CRM + Billing (instance_of edges to classes are skipped).
- Concurrency / cascade deletes / orphaned relationships / reference integrity: not applicable to
  a read-only view (the backend drops edges whose endpoints are not nodes; leave to backend tests).

### Anti-Pattern Validations
- ✓ No fixed timeouts without conditions: every step waits on a DOM condition (visibility,
  `aria-checked`, `aria-pressed`, `aria-selected`, `data-layout`, counts text).
- ✓ No hardcoded UUIDs: header ids are built from factory-returned scheme ids.
- ✓ No invented selectors: only registered test ids; Heimdall-internal ids (`graph-node-*`,
  `graph-edge-*`, `inspector-*`, `graph-viewport`) deliberately unused; nodes located by role +
  aria-label.
- ✓ No vacuous assertions: every step asserts a concrete count, attribute or text.
- ✓ No text selectors for mutable content: text only targets fixed seed titles and static copy.
- ✓ Cleanup: the `app-test` fixture runs `clearTestData` before each test; also call
  `clearTestData(page)` in `afterEach` per CRUD convention.

## Open Questions

Non-blocking; the plan proceeds with role/text locators.

1. **No way to clear the inspector selection.** `GraphPage` never resets `selectedNodeId` (no close
   button, background click does not deselect, exiting focus keeps it). If clearing is required it
   is a feature gap and needs a new registered selector (e.g. a node-inspector clear button).
   TC3 covers the empty state and switching selection instead.
2. **Heimdall-emitted ids are not registered**: `graph-node-{id}`, `graph-edge-{id}`,
   `graph-viewport`, `inspector-title`, `inspector-id`, `inspector-empty`, `inspector-description`,
   `inspector-metadata`, `inspector-outgoing`, `inspector-incoming`, `inspector-rel-{edgeId}`.
   Register them as patterns if id-based node/edge assertions are wanted.
3. **Duplicate `graph-layer-header-*` in the DOM** (Heimdall's hidden measurement layer): the
   generator must use a visible filter for presence and `toHaveCount(0)` for absence.
4. **Schema (domain to range) edges are untestable via factories**: `createPropertyDefinition` and
   `POST /api/properties` take no domain/range class ids. Add a factory option to cover that edge type.
5. **Planner inputs missing in this tree**: `ux/e2e/documentation/app-context.md` (exists only
   under `legacy/`), `ux/e2e/reports/*.json`, and `ux/src/api/client/types.ts` (types are in
   `ux/src/api/types/`). Invariants were taken from `get_graph_view` and `graphLayers.ts`.

## Factory Usage

From `ux/e2e/fixtures/factories.ts`: `createTaxonomy`, `createConceptScheme`, `createClass`
(with `parent_class_id`), `createIndividual` (with `class_ids`, `description`),
`createPropertyDefinition` (with `identifier`, `title`), `createRelationship`, `clearTestData`.
Fixture: `import { test, expect } from "../../fixtures/app-test"`. No new factories.
