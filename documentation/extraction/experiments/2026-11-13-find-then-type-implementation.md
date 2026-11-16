# The `find_then_type` implementation, recorded (2026-11-13)

**What.** The find-then-type prototype built as a registered implementation of individual extraction (PR #1595, merged 2026-11-14): `local-server/domain/extraction/find_then_type.py`, `local-server/domain/pipelines/individual_extraction/find_then_type.py`.

1. **Find:** each chunk is read once for what it mentions (named things, and statements such as goals and requirements), each with its passage. Nothing is typed.
2. **Type:** mentions are merged over the source by label key; each distinct one is typed once against every class of the ontology, each listed with the first 260 characters of its definition, as a cached system prompt; "none" allowed. Six calls at a time.
3. **Relate:** the two-pass pipeline's relationship stage, per chunk, between the individuals typed in it, with the predicates each subject class allows.

Then recognition against existing individuals, the chunk merge and the source proposal, unchanged.

## Result (Claude Haiku 5.5, one recording, replayed offline)

| | found F1 | typed F1 | recall (core) | precision | type accuracy | relationship recall |
|---|---|---|---|---|---|---|
| `edit_check` (dev) | 0.433 | 0.389 | 0.513 (0.738) | 0.375 | 0.897 | 0.094 |
| `gitlab_architecture` (dev) | 0.635 | 0.541 | 0.607 (0.889) | 0.667 | 0.851 | 0.265 |
| `wikimedia_enterprise` (holdout) | 0.513 | 0.481 | 0.485 (0.658) | 0.545 | 0.938 | 0.036 |
| dev mean | 0.534 | 0.465 | 0.560 (0.814) | 0.521 | 0.874 | 0.180 |

604 calls for three documents (570 typing calls reading the cached catalog), about $0.30, two to four minutes a document. Dev failure counts: 18 core and 67 supporting individuals missed, 15 mistyped, 93 spurious, 109 relationships missed.

These are the committed `find_then_type` recordings: `python scripts/benchmark_replay.py --implementation find_then_type`. Two further takes were recorded on 2026-11-15 for the [head-to-head](2026-11-15-head-to-head.md): over three takes typed F1 is 0.426-0.465 dev and 0.393-0.481 holdout.

## Verdict

Typed F1 0.114 to 0.465 against the two-pass baseline, mostly from typing (type accuracy 0.27 to 0.87) and from finding statements. Spurious items became the largest failure count. It became the default implementation on 2026-11-14 (PR #1598).
