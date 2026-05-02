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
cd local-server && python scripts/update_api_specs.py --check 2>/dev/null || python scripts/update_api_specs.py
cd ux && npm run generate-types
git diff --quiet ux/src/api/client/types.ts ux/documentation/openapi.json && echo "✓ types in sync" || echo "✗ types drifted — commit regenerated files"
```

If the generated files have changes after regeneration, the OpenAPI spec is stale.

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
