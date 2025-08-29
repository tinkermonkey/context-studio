import { server } from './server';
import { handlers } from './handlers';
import { rest } from 'msw';

/**
 * setupMocks
 *
 * Minimal helper for test files that want to opt into an MSW-controlled
 * network environment. The repository also includes a global MSW start in
 * `vitest.setup.ts` for broad coverage; use this helper for file-scoped
 * lifecycle when desired.
 */
export function setupMocks() {
  beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());
}

// Re-exports for convenience in tests
export { server, handlers, rest };
