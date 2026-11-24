# Test Plan: Proposal Review Against the Source (an extraction reviewed on its proposal page)

## Overview

End-to-end coverage for reviewing an extraction against its source (GitHub issues #1611, #1664). Since #1664 this happens on the proposal page itself, `/app/proposals/$proposalId`: the separate Review page (`/app/proposals/$proposalId/review`) is retired, and its URL redirects to the proposal page keeping `?selected=`. A reviewer opens an extraction proposal and sees the whole source with every element's passage highlighted by verdict, the operations grouped by layer, and the first awaiting element in the inspector. They then decide three elements in a row: **Correct** on the first, **a better class** from the class picker on the second, **Not an element** with a reason and note on the third. Under the default **Needs decision** filter a decided row leaves the list and the row below is selected; under **All** each decision moves the selection on to the next awaiting element. Finally they open the relationship whose end they rejected: the inspector shows the ends callout and offers only rejection. An old `/review` link then lands on the proposal page with its selection and the new tally.

No LLM call is made. The proposal is seeded through the public API (`POST /api/proposals` with `source: "pipeline"`), with evidence passages that point into a pasted-text source (`POST /api/sources`). Every decision hits the real isolated backend (:8888) and is verified through `GET /api/proposals/{id}`.

### Seeding note: the source

The source pane (`useSourcePane`, `ux/src/components/proposals/review/useSourcePane.tsx`) uses the source the proposal records in `client_metadata.source_id`, else the one most cited by the elements' **evidence passages** (`reviewSourceId()` in `reviewModel.ts`). The seed passes `client_metadata.source_id` with the proposal (adding a missed element needs it, #1610). So the seeding path is the public API alone: no source extraction run (which would cost LLM money), no direct DB write.

## Scope

- **Entities involved**: Taxonomy, ConceptScheme, Class, PropertyDefinition, Dataset, Source, ChangeProposal / ProposedOperation, Individual (created by applying), EntitySource (provenance, read-only)
- **Pages involved**: `/app/proposals/$proposalId` (the review page), `/app/proposals/$proposalId/review` (retired: redirects to the proposal page), `/app/pipelines/gold` (gold mode)
- **External dependencies** (all on the isolated test backend):
  - Seed: `POST /api/taxonomies`, `POST /api/taxonomies/{id}/schemes`, `POST /api/schemes/{id}/classes`, `POST /api/properties` (factories), `POST /api/datasets`, `POST /api/sources` (JSON `{taxonomy_id, dataset, title, text}`), `GET /api/sources/{id}/text`, `POST /api/proposals`
  - Page reads: `GET /api/proposals/{id}`, `GET /api/sources/{id}`, `GET /api/sources/{id}/text`, taxonomy classes and schemes, `GET /api/datasets?taxonomy_id=`
  - Decisions (UI): `POST /api/proposals/{id}/apply` (`operation_ids`, `review_ms`, `edits` for a class change), `POST /api/proposals/{id}/reject` (`operation_ids`, `note`, `reason_code`, `review_ms`)
  - Verification reads: `GET /api/proposals/{id}`, `GET /api/individuals/{id}`, `GET /api/individuals/{id}/sources`
- **DB state**: `fixtures/app-test` wipes ontology data before each test. Proposals have no delete route and are not wiped, so always address the proposal by the id the seed returned. Never assert global proposal counts.

## Shared Test Data

### Source text (`TEXT`)

```
The Billing Service sends invoices through the Mail Gateway to Customers.
```

Source title: `E2E Review Notes`. Each quote (`Billing Service`, `Mail Gateway`, `Customers`) occurs exactly once.

### Seed (`seedReviewProposal(page)`, a local helper inside the spec, not a new factory)

| Ref | How | Data |
|---|---|---|
| `taxonomy` | `createTaxonomy(page, { title: "E2E Review Taxonomy" })` | |
| `scheme` | `createConceptScheme(page, taxonomy.id, { title: "E2E Review Layer" })` | the only layer, so one element group, `review-group-{scheme.id}` (rows first render under `review-group-loading` and move there once classes and schemes load, which remounts them: wait for it before clicking rows) |
| `appService` | `createClass(page, scheme.id, { title: "E2E Review Application Service", description: "A service an application exposes to its users." })` | the proposed class of all three elements |
| `techNode` | `createClass(page, scheme.id, { title: "E2E Review Technology Node", description: "A piece of infrastructure that runs or carries software." })` | the better class picked for element 2 |
| `actor` | `createClass(page, scheme.id, { title: "E2E Review Business Actor", description: "A person or organisation that takes part in the business." })` | a distractor, so the picker has more than one other class |
| `property` | `createPropertyDefinition(page, { identifier: "e2e_review_serves", title: "E2E Review Serves" })` | no domain or range, so no domain/range mismatch; the predicate shows as its identifier |
| `dataset` | `apiRequest(page, "/api/datasets", { method: "POST", body: { taxonomy_id, identifier: "e2e-review", title: "E2E Review" } })` | named in the source and the proposal |
| `source` | `apiRequest(page, "/api/sources", { method: "POST", body: { taxonomy_id, dataset: "e2e-review", title: "E2E Review Notes", text: TEXT } })` | assert `status === "ready"` before going on |
| `sourceText` | `apiRequest(page, \`/api/sources/${source.id}/text\`)` | **compute every passage's offsets from `sourceText.text` (plus `sourceText.start`)**, not from `TEXT`: the reader may normalise the pasted text |
| `proposal` | `apiRequest(page, "/api/proposals", { method: "POST", body })` (below) | returns 201 with every operation `pending` |

Proposal body:

```
{
  taxonomy_id, dataset_id: dataset.id,
  title: "E2E review extraction",
  source: "pipeline",
  source_detail: "e2e seed: individual_extraction",
  operations: [
    { seq: 1, op: "create", kind: "individual", ref: "billing",
      fields: { title: "Billing Service", class_ids: [appService.id] },
      evidence: [passage("Billing Service")], probability: 0.92 },
    { seq: 2, op: "create", kind: "individual", ref: "gateway",
      fields: { title: "Mail Gateway", class_ids: [appService.id] },
      evidence: [passage("Mail Gateway")], probability: 0.85 },
    { seq: 3, op: "create", kind: "individual", ref: "customers",
      fields: { title: "Customers", class_ids: [appService.id] },
      evidence: [passage("Customers")], probability: 0.60 },
    { seq: 4, op: "create", kind: "relationship",
      fields: { source_id: "$gateway", target_id: "$customers", property_definition_id: property.id },
      probability: 0.80 }
  ]
}
```

`passage(quote)` = `{ source_id: source.id, page: 1, start, end: start + quote.length, quote }`, where `start = sourceText.start + sourceText.text.indexOf(quote)`.

The helper returns `{ taxonomy, scheme, appService, techNode, actor, property, dataset, source, proposal, ops }`, where `ops` maps `billing | gateway | customers | serves` to the `ProposedOperationResponse.id` of seq 1-4 (looked up by `seq` in `proposal.operations`). **Every** row, mark and relationship locator is built from these ids. No id is ever hard-coded.

The default approval policy has no auto-apply rules, so all four operations stay `pending` after the POST. Assert it in the helper so a policy change fails loudly here rather than as a confusing UI failure.

### Locator conventions

- Highlight of an element: `page.locator('[data-testid="review-mark"][data-span-keys~="<opId>"]')`. That is the registered `review-mark` testid narrowed by its `data-span-keys` attribute.
- Row state: `review-row-<opId>` has `aria-selected` and `data-verdict` (`awaiting | correct | changed | rejected | added`).
- Mark state: class `review-mark--<verdict>`; the selected mark also has `review-mark--selected` and `aria-current="true"`.
- Class picker: `page.getByTestId("review-class-picker").getByRole("combobox")` to type. Heimdall (0.14) portals the picker's listbox to the body, so its options are found through the combobox's `aria-controls` (the listbox id), then `getByRole("option")`.
- Operations filter: `proposal-operation-filter` holds a SegmentedControl ("Show operations"): radios `Needs decision · N`, `Decided · N`, `All · N`, with `aria-checked`. Needs decision is the default while anything awaits; a page opened with `?selected=` on a decided operation opens on All.
- Classes have no DR external reference, so `classLabel()` shows each class's title.

## Test Cases

### Test Case 1: The proposal page shows the source, operations and first awaiting element

- **Preconditions**: `seedReviewProposal(page)`; navigate to `/app/proposals/${proposal.id}`; wait for `proposal-page` and `review-group-${scheme.id}`.
- **Steps**:
  1. `proposal-tally` has text `4 of 4 need a decision`.
  2. Header: `proposal-page` contains the proposal title `E2E review extraction` and `by e2e seed: individual_extraction` (no pipeline run, so no origin chip: `proposal-summary` has no `proposal-origin`; "Proposed … by" falls back to `source_detail`).
  3. Progress: `proposal-summary` is visible; `proposal-decided-counts` has text `0 applied · 0 rejected`; `review-time` matches `/^\d+:\d{2} on this review$/`.
  4. Source: `proposal-review` has class `proposal-review--source`; `review-source` contains the source title `E2E Review Notes` and `review-legend` with `Awaiting`, `Correct`, `Class changed`, `Not an element`, `Added by you`; `review-source-text` contains the whole `TEXT`; exactly 3 `review-mark` elements; each element's mark has class `review-mark--awaiting`.
  5. Operations: `proposal-operations` is visible; `proposal-operation-filter` contains `Needs decision · 4`, `Decided · 0` and `All · 4`, with Needs decision checked; `review-element-list` holds `review-group-${scheme.id}` (rows for billing, gateway, customers, in that order) and `review-group-relationships` (row for serves). The serves row text contains `Mail Gateway` and `Customers`.
  6. Initial selection: `review-row-${ops.billing}` has `aria-selected="true"` and `data-verdict="awaiting"`; the billing mark has `aria-current="true"` and class `review-mark--selected`.
  7. Inspector: `review-inspector-eyebrow` contains `Individual · p 0.92`; `review-inspector-title` has text `Billing Service`; `review-inspector-class` has text `E2E Review Application Service`; `review-inspector-status` has text `awaiting`; `review-evidence` contains `Billing Service`; `review-definition` contains `A service an application exposes to its users.`; `review-correct` is enabled; `review-better-class` and `review-reasons` are visible; `review-relationships` contains `Its relationships · 0`.
  8. Click a highlight: click the customers mark. Assert `review-row-${ops.customers}` has `aria-selected="true"`, `review-inspector-title` has text `Customers`, the customers mark has `aria-current="true"`, and `review-relationships` contains `review-relationship-${ops.serves}`.
- **Expected Result**: The proposal page shows the source with three awaiting highlights, the operations grouped by layer with the relationship last, `4 of 4 need a decision`, and the first awaiting element in the inspector. A highlight click opens its element. No decision is made, and `GET /api/proposals/{id}` still has all four operations `pending`.
- **Selectors Used**: `proposal-page`, `proposal-tally`, `proposal-summary`, `proposal-origin`, `proposal-decided-counts`, `review-time`, `proposal-review`, `review-source`, `review-legend`, `review-source-text`, `review-mark`, `proposal-operations`, `proposal-operation-filter`, `review-element-list`, `review-group-*`, `review-row-*`, `review-inspector`, `review-inspector-eyebrow`, `review-inspector-title`, `review-inspector-class`, `review-inspector-status`, `review-evidence`, `review-definition`, `review-correct`, `review-better-class`, `review-reasons`, `review-relationships`, `review-relationship-*`
- **Invariants Verified**: I2, I3, I4, I5 (see Invariants)

### Test Case 2: Correct, a better class, not an element, then the relationship whose end was rejected

- **Preconditions**: `seedReviewProposal(page)`; navigate to `/app/proposals/${proposal.id}`; wait for `review-group-${scheme.id}` and for `review-row-${ops.billing}` to have `aria-selected="true"`.
- **Steps**:
  1. **Correct** (element 1), under the default Needs decision: click `review-correct`.
     - The billing mark gets class `review-mark--correct`; `review-row-${ops.billing}` leaves the list (count 0).
     - `proposal-tally` has text `3 of 4 need a decision`; `proposal-decided-counts` has text `1 applied · 0 rejected`.
     - Selection moved to the row below: `review-row-${ops.gateway}` has `aria-selected="true"`; `review-inspector-title` has text `Mail Gateway`; the gateway mark has `aria-current="true"`.
     - API: in `GET /api/proposals/{id}`, the billing operation has `status === "applied"` and a `result_entity_id`. `GET /api/individuals/{result_entity_id}` has `title === "Billing Service"` and `class_ids` equal to `[appService.id]`. `GET /api/individuals/{result_entity_id}/sources` has one item with `source_id === source.id`, `proposal_id === proposal.id`, `quote === "Billing Service"`.
     - Click `All · 4` in `proposal-operation-filter`: it is checked, `review-row-${ops.billing}` is back with `data-verdict="correct"`, and gateway stays selected.
  2. **A better class** (element 2), under All: while gateway is selected, assert `review-relationships` contains `Its relationships · 1` and `review-relationship-${ops.serves}`. In `review-class-picker`, assert the label `Search all 3 classes`, type `Technology` into its combobox, assert exactly one option with text `E2E Review Technology Node`, and click it.
     - `review-row-${ops.gateway}` gets `data-verdict="changed"`; the gateway mark gets class `review-mark--changed`.
     - `proposal-tally` has text `2 of 4 need a decision`; `proposal-decided-counts` has text `2 applied · 0 rejected`.
     - Selection advanced to the next awaiting row: `review-row-${ops.customers}` has `aria-selected="true"`; `review-inspector-title` has text `Customers`.
     - API: the gateway operation has `status === "applied"` and `applied_fields.class_ids` equal to `[techNode.id]`; `GET /api/individuals/{result_entity_id}` has `class_ids` equal to `[techNode.id]`.
  3. **Not an element** (element 3): fill `review-note` with `A group of readers, not a component`, then click `review-reason-mentioned_only`.
     - `review-row-${ops.customers}` gets `data-verdict="rejected"`; the customers mark gets class `review-mark--rejected`.
     - `proposal-tally` has text `1 of 4 need a decision`; `proposal-decided-counts` has text `2 applied · 1 rejected`; `proposal-operation-filter` contains `Needs decision · 1`.
     - Selection advanced to the only awaiting operation: `review-row-${ops.serves}` has `aria-selected="true"`.
     - API: the customers operation has `status === "rejected"`, `reason_code === "mentioned_only"` and `reason === "A group of readers, not a component"`; it has no `result_entity_id`.
  4. **The relationship whose end was rejected**: click `review-row-${ops.customers}`.
     - The inspector shows the decided element read-only: `review-decided` contains `Not an element: Mentioned only.`; `review-decided-note` has text `A group of readers, not a component`; `review-inspector-status` has text `not an element`; `review-correct`, `review-better-class` and `review-reasons` have count 0.
     - `review-relationships` lists `review-relationship-${ops.serves}`, containing `Mail Gateway`, `e2e_review_serves` and `awaiting`. Click it.
     - `review-row-${ops.serves}` has `aria-selected="true"`; `review-inspector-eyebrow` contains `Relationship · p 0.80`; `review-inspector-title` contains `Mail Gateway` and `Customers`; `review-inspector-status` has text `awaiting`.
     - `review-ends-callout` is visible and contains `#3 was rejected` and `Reject it too, or give it another end.`
     - Only rejection is offered: `review-correct` has count 0; `review-reasons` is visible and `review-reason-not_in_text` is enabled; `review-inspector-class` and `review-better-class` have count 0 (a relationship has no class).
     - API: the serves operation is still `status === "pending"`.
  5. **An old Review page link**: navigate to `/app/proposals/${proposal.id}/review?selected=${ops.customers}`. Assert the URL is `/app/proposals/${proposal.id}?selected=${ops.customers}`, `review-row-${ops.customers}` has `aria-selected="true"` and `data-verdict="rejected"`, `All · 4` is checked (the link names a decided operation), `proposal-tally` has text `1 of 4 need a decision`, and `proposal-decided-counts` has text `2 applied · 1 rejected`.
- **Expected Result**: Each decision applies or rejects through the real backend at once. The row, highlight, and inspector chips show the verdict. The tally and counts advance. Under Needs decision a decided row leaves the list and the row below is selected; under All the selection moves to the next awaiting operation. A relationship with a rejected end can only be rejected. An old `/review` link lands on the proposal page with its selection, and the tally there agrees with the review.
- **Selectors Used**: `proposal-page`, `review-group-*`, `review-row-*`, `review-mark`, `review-correct`, `proposal-tally`, `proposal-decided-counts`, `proposal-operation-filter`, `review-inspector-title`, `review-inspector-eyebrow`, `review-inspector-status`, `review-inspector-class`, `review-relationships`, `review-relationship-*`, `review-better-class`, `review-class-picker`, `review-note`, `review-reasons`, `review-reason-*`, `review-decided`, `review-decided-note`, `review-ends-callout`
- **Invariants Verified**: I1, I3, I4, I6, I7, I8, I9, I10

## Invariants

`ux/e2e/documentation/app-context.md` does not exist in this tree (only `legacy/legacy_ux/e2e/documentation/app-context.md`, which predates this page). The invariants below come from issues #1611 ("Build" and "Done when") and #1664, and the page's own model (`reviewModel.ts`, `decisionModel.ts`, `ReviewInspector.tsx`, `ProposalDetailPage.tsx`).

- **I1**: The review against the source is the proposal page. `/app/proposals/$proposalId/review` redirects there, keeping `?selected=`.
- **I2**: The source pane shows the whole source text, and each element's passage is a highlight coloured by its verdict.
- **I3**: Progress is the proposal's tally (`N of M need a decision`, else `All M decided`) and its decided counts (`N applied · M rejected`).
- **I4**: Elements are grouped by layer (the proposed class's concept scheme), and relationships come last in their own group.
- **I5**: Until the reviewer picks one, the first awaiting element is selected. Clicking a highlight selects its element.
- **I6**: A decision applies (or rejects) at once. No undo is offered. The row, highlight, and inspector status show the verdict.
- **I7**: After a decision under Needs decision, the decided row leaves the list and the row below is selected (else the new last row). Under All or Decided, the selection moves to the next awaiting operation below, wrapping to the top.
- **I8**: A class picked from the picker applies the element with `edits.class_ids` (status `applied`, `applied_fields.class_ids` the picked class), and its verdict is "class changed". The picker leaves out the element's own class.
- **I9**: A rejection records its reason code and note on the operation.
- **I10**: A relationship whose new end was rejected cannot be accepted. The ends callout names the rejected end by `#seq`, Correct is absent, and the reasons stay.

## Coverage Analysis

### CRUD Coverage

- **ChangeProposal / ProposedOperation**: Create (API seed). Read (proposal page, `GET /api/proposals/{id}`). Update (apply as proposed, apply with a class edit, reject with a reason, all through the UI). Delete: not applicable (no route; proposals are reverted, not deleted, and revert is out of scope).
- **Individual**: Create (by applying elements 1 and 2). Read (`GET /api/individuals/{id}` and its sources). Update: the class edit is checked as the created individual's `class_ids`. Delete: teardown only.
- **Source / Dataset / Taxonomy / Scheme / Class / PropertyDefinition**: Create (seed) and Read (header, picker, definition). Update and Delete are not exercised by the UI here; teardown is described under Cleanup.
- **Relationship**: Not created. Its operation stays pending because one end was rejected (I10).

### Edge Cases

- **Reference-integrity**: a relationship create whose `$ref` end was rejected cannot apply. The UI blocks it (TC2 step 4) and the API shows it still `pending`.
- **Orphaned relationships**: the serves relationship would be orphaned by rejecting `customers`. The ends callout covers this. It is not applied.
- **Cascade deletes**: not exercised (no deletes from this page).
- **Concurrency (version mismatch)**: the stale-operation "Apply anyway" path (`review-force-message`) is out of scope. Seeding a stale operation needs a second writer between proposal and decision. Covered by component tests.
- **Out of scope by request ("few tests")**: keyboard decisions (A, 1-3, X, J / K), near-match choices (`review-class-locked`), bulk selection, and the source-unavailable states. All are covered by `ProposalReview.test.tsx`. The spec also has two tests beyond this plan: adding a missed element from selected text, and gold mode (tier, note required, the Benchmark gold page opening the check on its proposal page).

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions. Every wait is a polling assertion on a DOM state (`aria-selected`, `data-verdict`, a `review-mark--*` class, `aria-current`, a tally text) or on `expect.poll` over an API read. Never `waitForTimeout`.
- ✓ No hardcoded UUIDs. Every operation, scheme, class, source and dataset id comes from the seed's API responses. The only literal identifiers are seeded slugs (`e2e-review`, `e2e_review_serves`) and the API's own reason codes.
- ✓ No invented selectors. Every `data-testid` is registered in `ux/selector-registry.yaml` (#1611 section and the proposal detail section). The other locators are ARIA roles inside a registered testid (`combobox` and `option` in `review-class-picker`) and attributes on registered elements (`data-span-keys`, `data-verdict`, `aria-selected`, `aria-current`).
- ✓ No vacuous assertions. Every step asserts a specific text, attribute, class or API field value.
- ✓ No text-based selectors for mutable content. Text is only asserted, never used to find an element. The exceptions are the picker option (a seeded fixed value, reached by role in the listbox the `review-class-picker` combobox controls) and the filter segments (`All · N`), reached by role inside `proposal-operation-filter`.
- ✓ `review-time` is asserted by pattern only, because it ticks each second.
- ✓ Console errors fail the test (`fixtures/app-test`). The flow should log none, so no `allowedConsoleErrors` entry is planned.

### Cleanup

- `fixtures/app-test` runs `clearTestData(page)` before each test. Also call `clearTestData(page)` in `afterEach`. It drains individuals (including those the apply created), properties, classes, schemes and taxonomies. Deleting the taxonomy cascades to its datasets and sources (`ondelete="CASCADE"`).
- Change proposals have no taxonomy foreign key and no delete route, so the seeded proposal stays in the isolated DB until the next `global-setup` reset. It is harmless because tests address it by id (same as pipeline runs in `extraction-review.md`).

## Open Questions

No selectors are missing. Every testid this plan needs is registered.

Non-blocking notes for the generator:

1. `app-context.md` and `ux/e2e/reports/` (with `SCHEMA.md`) do not exist under `ux/e2e/` in this tree. Invariants come from issue #1611 and the code. There was no `selector_coverage.gaps` report to target.
2. The seed assumes `POST /api/proposals` accepts the four operations with no approval-policy auto-apply. Confirm it on the first run with the helper's `pending` assertion. If it fails, a `?dry_run=true` POST returns `auto_apply` per operation and the 422 lists problems by `seq`.
3. If the plain-text reader changes the pasted text (for example a trailing newline), offsets derived from `GET /api/sources/{id}/text` stay correct. Never derive them from the `TEXT` constant.

## Factory Usage

From `ux/e2e/fixtures/factories.ts` (via `fixtures/test-helpers.ts`):

- `createTaxonomy`: the taxonomy
- `createConceptScheme`: the one layer
- `createClass` (x3): `appService`, `techNode`, `actor`, each with a description (shown under "What <class> means")
- `createPropertyDefinition`: `e2e_review_serves`
- `clearTestData`: teardown (and the fixture's before-each wipe)

From `ux/e2e/fixtures/api-client.ts`:

- `apiRequest`: dataset, source, source text, proposal, and the verification reads. There are no factories for datasets, sources or proposals. The spec keeps them in one local `seedReviewProposal(page)` helper, not new shared factories, as `extraction-review.spec.ts` does with `seedDrScope`.

Test fixture: `import { test, expect } from "../../fixtures/app-test"`. Proposed file: `ux/e2e/tests/proposals/proposal-review-page.spec.ts`.
