# DR triage snapshots

DR's split claims and triage bench gold, copied from the `documentation_robotics`
repo's `cli/scripts/spec-enrich/data/triage/` at commit `2890207e` ("enrich:
reflection stage (sorting questions) for relationship claims"). They exist only on
DR's `wf_7c26f604` worktree branch, not on DR main, so they are pinned here.

| File | Source | Rows |
|---|---|---|
| `claims.jsonl.xz` | `claims.jsonl`, xz-compressed | 1,462 claims |
| `bench-gold.jsonl` | `bench-gold.jsonl` | 10 adjudicated claims |

`scripts/import_dr_claims.py` loads them into the `dr_spec` taxonomy, and
`tests/integration/interchange/test_dr_claims.py` imports them against the pinned
DR 0.10.0 spec snapshot.
