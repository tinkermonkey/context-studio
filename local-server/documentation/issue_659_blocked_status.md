# Issue #659 Status: BLOCKED on #658

This issue (#659) depends on issue #658 (Implement interchange API routes).

## Acceptance Criteria Status:
- ❌ `local-server/documentation/openapi.json` regenerated with interchange endpoints
- ❌ `ux/src/api/client/types.ts` regenerated with interchange types
- ❌ Interchange entity/route types appear in generated output
- ❌ No hand-written parallel types for the new surface
- ❌ Re-running scripts produces no diff for interchange surface

## Why Blocked:
Issue #658 (Implement interchange API routes) must be completed first. The interchange API routes have not been implemented in the back-end (`adapters/web/interchange_routes.py` does not exist). Without these routes, the OpenAPI spec and generated front-end types cannot include the required:
- `ImportPlanResponse`
- `ImportConflictResponse`
- `ImportRunResponse`
- `match_kind` enum
- `resolution` enum

## Next Steps:
Once #658 is merged with interchange API route implementations, this issue (#659) can be reopened and completed by running:
1. `python local-server/scripts/update_api_specs.py` from the back-end
2. `npm run generate-types` from the front-end

This will automatically generate the interchange types into the API client.
