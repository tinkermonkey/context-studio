---
description: Run all Context Studio validation gates — domain purity, selector contract, OpenAPI freshness, and frontend typecheck.
---

You are running the project's validation gates. None of these execute tests; they verify the codebase is internally consistent.

Run all four in this order. Do not stop on the first failure — collect every result, then report.

## 1. Domain purity (backend hexagonal-architecture invariant)

```bash
cd local-server && source .venv/bin/activate && python scripts/check_domain_imports.py
```

Exit 0 = clean. Any output = a `domain/` file imports infrastructure (banned: `adapters`, `sqlalchemy`, `fastapi`, `pydantic`, `sentence_transformers`, `spacy`, `networkx`, `rdflib`, `duckdb`, `openai`, `anthropic`, `httpx`, `uvicorn`, `utils`).

## 2. Selector contract (frontend)

```bash
cd ux && npm run validate-selectors
```

Hard-fails (exit 1) on:
- Test references a `data-testid` that doesn't exist in source and doesn't match a registry pattern.
- A spec outside `e2e/tests/api-contracts/` has no UI interactions (would silently pass against a blank frontend).

In **strict** mode (`npm run validate-selectors -- --strict`), it also hard-fails on undocumented source selectors. CI uses strict.

## 3. OpenAPI / type freshness

```bash
cd local-server && source .venv/bin/activate && python scripts/update_api_specs.py --check
```

`--check` generates the spec, compares it with `local-server/documentation/openapi.json` and `ux/documentation/openapi.json`, writes nothing, and exits 1 naming each stale file. Do not hide stderr (an import error from the app shows there) and do not regenerate as a fallback: a stale spec is a failure to report. Fix it with `python scripts/update_api_specs.py`, then commit the files.

The generated types are checked against the committed spec by regenerating into a temporary copy:

```bash
cd ux && cp src/api/types/index.ts "${TMPDIR:-/tmp}/index.ts.committed" && npm run generate-types && cmp src/api/types/index.ts "${TMPDIR:-/tmp}/index.ts.committed" && echo "✓ types in sync" || echo "✗ types stale: commit the regenerated ux/src/api/types/index.ts"
```

(`generate-types` rewrites `ux/src/api/types/index.ts`; when it differs from the copy, the committed file was stale.)

## 4. TypeScript

```bash
cd ux && npm run typecheck
```

## Reporting

Print a single summary table:

| Check | Result | Notes |
|---|---|---|
| Domain purity | ✓/✗ | violations if any |
| Selector contract | ✓/✗ | error count, top errors |
| OpenAPI freshness | ✓/✗ | which files drifted |
| TypeScript | ✓/✗ | first 5 errors |

Never claim success by reading the diff — always execute and report actual exit codes.
