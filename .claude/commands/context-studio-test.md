---
description: Run Context Studio test suites — backend (pytest), frontend unit (vitest), or E2E (playwright). Pass an arg to scope.
---

You are running tests for Context Studio. The user's argument (if any) is in `$ARGUMENTS`.

## Routing

Pick the matching scope from `$ARGUMENTS`:

| Argument | What to run |
|---|---|
| `backend` or `py` | Backend pytest suites |
| `unit` | Backend unit only |
| `integration` | Backend integration only |
| `frontend` or `ux` | Frontend vitest suites |
| `e2e` | Smoke + full Playwright suite |
| `smoke` | E2E smoke suite only (5 tests, < 30s) |
| `validate` | `npm run validate-selectors` only |
| `all` (default) | Everything in CI order |

If `$ARGUMENTS` is empty, default to `all`.

## How to run

**Validate selectors first** for any E2E-touching scope:

```bash
cd ux && npm run validate-selectors
```

If that exits non-zero, stop and report — do not run E2E.

### Backend
```bash
cd local-server && source .venv/bin/activate
pytest tests/unit/                        # unit
pytest tests/integration/                 # integration
pytest tests/ -m "not e2e"                # skip external calls
```

### Frontend unit
```bash
cd ux && npm run test:run
```

### E2E smoke (must pass before trusting other E2E results)
```bash
cd ux && npx playwright test e2e/tests/smoke/smoke.spec.ts
```

### E2E full
```bash
cd ux && npm run test:e2e
```

## Reporting

After running, report:

1. The command(s) you ran.
2. Actual pass/fail counts from the runner output.
3. For E2E: the structured report path (`ux/e2e/reports/<run_id>.json`) and its `is_valid` field. If `is_valid: false`, treat coverage numbers as unreliable.
4. Any selector contract failures verbatim — they block test execution.

Never approve test results by reading the diff. Always execute.
