MSW interception follow-up

Status: open

## Context

We temporarily mocked `domainService.domainService.update` in `test/integration/domain_edit.integration.test.tsx` because MSW did not intercept the PUT request in the test environment during initial debugging. The integration test is left mocked to keep CI green and avoid flaky behavior while we diagnose the root cause.

## Next steps (investigation)

1. Reproduce minimal failing case
   - Create a tiny isolated test that performs a single axios.put against `API_CONFIG.baseURL + '/api/domains/1'` and assert MSW/node intercepts it.
   - This isolates adapters and baseURL resolution.

2. Confirm axios adapter in test environment
   - Inspect `apiClient.defaults.adapter` at runtime in the test to determine whether axios uses fetch, XHR, or the Node HTTP adapter.
   - If axios picks fetch/XHR under jsdom, ensure test setup deletes global.fetch / XMLHttpRequest or configure axios to use the Node adapter explicitly for tests.

3. Harden MSW handlers
   - Add explicit absolute and relative handlers and an early test-level handler via `server.use` to guarantee priority for the integration test.
   - Use RegExp handlers for flexible matching while diagnosing.

4. Remove test-only instrumentation
   - Once MSW intercepts reliably, remove any `console.debug` or temporary handlers from tests and restore a pure MSW flow.

5. Restore integration test
   - Replace the `domainService` spy with a pure MSW-driven interaction and assert `invalidateQueries` as before.

Owner: @tinkermonkey
Estimated effort: 1–3 hours

## Notes

- Common causes: axios using fetch/XHR adapter, mismatched baseURL or trailing slash, and handler ordering.
- Keep `vitest.setup.ts` MSW startup with `onUnhandledRequest: 'warn'` enabled during investigation to surface mismatches.
