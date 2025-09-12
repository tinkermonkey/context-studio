# MSW test helpers

This folder contains shared MSW handlers and a test server used by
integration tests in the UX repo.

Files

- `handlers.ts` - centralized handlers for common API endpoints used in tests.
- `server.ts` - `setupServer(...handlers)` instance used by tests.
- `setupTests.ts` - small per-file helper `setupMocks()` and re-exports (`server`, `handlers`, `rest`).

How to use

- The repository starts MSW globally via `vitest.setup.ts` by default. That
  global start makes most tests work without imports. If you prefer explicit
  per-file lifecycle, import `setupMocks()` from this folder and call it at
  the top of your test file.

Example

```ts
import { setupMocks } from "./test/msw/setupTests";
setupMocks();

test("my integration test", async () => {
  // ... test that relies on network mocks
});
```

Notes

- If a test requires different behavior for a single endpoint, prefer using
  `server.use()` within that test to override handlers and `server.resetHandlers()`
  in `afterEach` to restore defaults.
