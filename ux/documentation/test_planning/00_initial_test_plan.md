# Initial Test Plan — Context Studio UX

Last update: 2025-08-29

## Purpose

This document records the current test surface for the UX repo, gaps in coverage, and a pragmatic, prioritized plan to add reliable unit, integration, and light end-to-end tests so the UI and API wiring remain stable as we continue refactors (selector portal work, modal edits, and query invalidation).

## Quick status (scan results)

- Test runner: Vitest (configured, jsdom environment, jest-dom loaded via `vitest.setup.ts`).
- Existing unit tests (quick inventory):
  - `src/components/node_selectors/__tests__/portal_record_selector.test.tsx` — selector unit tests (placeholder, search, basic interactions).
  - `src/components/misc/__tests__/create_child_button.test.tsx` — button & modal wiring tests (mock forms).
- Several `src/api/tests/*.ts` helper scripts exist but are not unit tests (manual integration scripts).
- Coverage: there is no coverage report yet; current test count small (2 test files, 8 tests at time of scan).

## High-level gaps and priorities

1. Core interactive components (High priority)
   - `PortalRecordSelector` — extend tests for keyboard navigation, ARIA roles, focus management, multi-select edge cases, and portal positioning behavior.
   - Modal wiring components (domain, layer, term details + edit modals) — ensure the Edit button opens expected modal, form populates correctly, and success callback invalidates queries.
   - Forms (dataset/domain/term/predicate) — validate client-side validation rules, error displays, and onSuccess flows.

2. Hooks & API services (High priority)
   - React Query hooks (use\* hooks) — test optimistic updates, cache invalidation, and error paths using mocked API responses.
   - services/\* (axios wrappers) — unit tests for request/response mapping, error handling, interceptors.

3. Tables, renderers & node tables (Medium)
   - PredicatesTable, datasets table — test column renderers, sorting/pagination props, and row actions.

4. Graph utilities & layout (Low/Medium)
   - treeBuilder, layout utilities — unit tests for pure functions, layout constraints, and edge cases (empty input, deep nesting).

5. Accessibility & keyboard flows (Cross-cutting)
   - Ensure major interactive workflows are keyboard operable (modals, selectors, tables) and include ARIA assertions.

## Testing types recommended

- Unit tests (Vitest + @testing-library/react) — small components, pure functions, services.
- Hook tests (Vitest with msw or manual mocking) — mount hooks with `@testing-library/react`'s `renderHook` alternative or small consumers.
- Integration tests (Vitest + MSW) — test component + hook + mocked network in one go (eg. form submit -> mutation -> query invalidation).
- Light E2E/smoke (Playwright or Cypress) — optional later: critical user flows in a real browser (open app, open details modal, create child) run in CI.

## Tooling & configuration suggestions

- Keep Vitest as unit/integration runner. Add coverage collection via Vitest's `--coverage` option and set baseline thresholds.
- Use MSW (Mock Service Worker) to stub network calls in component/hook integration tests. It plays well with Vitest.
- Use `@testing-library/react` and `@testing-library/user-event` for realistic DOM interactions.
- Keep `vitest.setup.ts` for global setup (jest-dom, portal root). Add MSW server start/stop hooks here if used across many tests.
- Add a CI job (GitHub Actions) to run tests + coverage and enforce thresholds on PRs.

## Concrete test cases (examples)

Below are representative test cases to implement.

PortalRecordSelector (extend existing)

- Keyboard navigation:
  - open selector, press ArrowDown repeatedly, ensure highlighted item moves and `option` receives focus.
  - press Enter when highlighted -> ensure `onSelect` or `onSelectionChange` called appropriately.
  - Escape closes the menu and returns focus to the trigger.
- Multi-select
  - add multiple items, ensure pills appear and `onSelectionChange` receives correct arrays.
  - respect `maxSelections` restriction.
- ARIA
  - ensure `aria-expanded`, `role=listbox`, and `role=option` attributes are present and change as expected.

Modal edit flows (domain/layer/term details)

- Clicking Edit opens the modal with form populated (mock hook data or render with props).
- Submitting the form calls the mutation and invalidates the expected query (use MSW to return success and assert react-query cache update via QueryClient).
- Error path: server returns 4xx -> form shows server error message.

Forms (predicate_form, dataset_form, etc.)

- Field validation rules (invalid characters, required fields) show correct messages.
- Successful submission calls the passed onSuccess with the new object.

Hooks & services

- Test service functions for URL and payload correctness; mock `axios` with `vi.mock` and assert interceptors behavior.
- Hook mutation flows: mount small test component that uses the hook, simulate mutation, assert query invalidation and optimistic update behavior.

Utilities & pure functions

- treeBuilder, renderers, layout utils — unit tests for deterministic outputs across various inputs.

## Quality gates & metrics

- Target: gradually raise coverage to 70% (short-term), 85% (medium-term). Start with critical UI flows to reduce regression risk.
- Add coverage thresholds in CI; fail PRs under threshold. Keep thresholds permissive at first and tighten over time.

## Rollout plan (phased)

Phase 0 — baseline (1–2 days)

- Add coverage script: `vitest --coverage` and generate an lcov report.
- Add MSW to dev deps and create a shared `test/msw` folder with example handlers.
- Convert any remaining Jest-style tests to Vitest (done for current tests).

Phase 1 — core interactive components (3–7 days)

- Finish thorough tests for `PortalRecordSelector` (keyboard, ARIA, multi-select, edge cases).
- Add tests for Create/Edit modal flows (domain/layer/term) including successful submission + query invalidation.

## Temporary MSW note

- The `DomainDetails` integration test currently uses a service-level mock for the update call (`domainService.domainService.update`).
- Reason: during initial migration to pure MSW-driven integration tests we observed MSW not intercepting the PUT request in the jsdom test environment (likely due to adapter/baseURL shape differences). Mocking keeps CI/tests stable while we investigate.
- Follow-up: see `documentation/task_reports/msw_interception_followup.md` for the investigative plan and steps to convert the test back to pure MSW when resolved.

Phase 2 — hooks & services (3–5 days)

- Add unit tests for services (axios wrappers) and hook tests using MSW to simulate API responses.

Phase 3 — tables, renderers, utilities (2–4 days)

- Add unit tests for node_tables and graph/layout utilities.

Phase 4 — CI + coverage enforcement (1–2 days)

- Add GitHub Actions workflow to run tests and publish coverage; set baseline thresholds.

## Maintenance & best practices

- Keep tests focused and deterministic: prefer MSW over network calls. Reset MSW between tests.
- Write small helper factories for rendering components with `QueryClientProvider` and common wrappers.
- Aim for tests that exercise behaviour rather than implementation details.

## Commands (how to run locally)

- Run tests: `npx vitest` (interactive) or `npx vitest run` (CI)
- Run with coverage: `npx vitest run --coverage` (produces coverage report/lcov)

## Next concrete actions I can take (pick any)

- Add a `test:coverage` npm script and a minimal `msw` setup in `test/` to standardize mocks.
- Implement the PortalRecordSelector keyboard/accessibility tests (extend the existing file).
- Implement one integration test for domain edit modal using MSW to show full mutation/invalidation flow.

If you want, I will proceed with one of the above (recommended: add MSW + coverage script, then extend PortalRecordSelector tests).

---

End of plan
