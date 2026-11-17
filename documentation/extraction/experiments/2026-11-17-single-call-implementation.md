---
date: 2026-11-17
kind: experiment
implementations: [single_call]
models: [claude-opus-5-5]
takes: 1
cost_usd: 2.76
verdict: adopted
reproducible: yes
---

# The `single_call` implementation, recorded (2026-11-17)

**What.** The [head-to-head](2026-11-15-head-to-head.md)'s arm B built as a registered implementation of individual extraction, and made the default by the user's decision of 2026-11-17: `local-server/domain/extraction/single_call.py`, `local-server/domain/pipelines/individual_extraction/single_call.py`, configuration `extraction-single-call` (`local-server/configs/extraction-single-call.json`).

1. **Find individuals:** one Claude Opus 5.5 call reads the whole document and lists every individual with its class and a quote, against all 193 DR classes with their whole definitions, by layer, as a cached system prompt (about 62,000 tokens); adaptive thinking (always on for Opus 5.5) at effort high; streamed; 64,000 output tokens allowed. The prompt is arm B's, without its relationships and predicates, and asks for plain JSON instead of a structured-output schema. It is the stage `find_individuals` in `local-server/domain/extraction/prompts.py`, editable through a configuration's `stage_prompts` like the others. A document too long for one call is read in the fewest runs of chunks of at most 60,000 characters, one call each (not exercised here: every benchmark document fits one call).
2. **Place:** each individual goes in the chunk its quote is in, and in every other chunk that names it as written.
3. **Relate:** `find_then_type`'s relate step, unchanged and shared (`FindThenTypeOrchestrator._relate_and_merge`): per chunk, between the individuals placed in it, with the predicates each subject class allows. It runs on the configuration's model (Opus 5.5) at the model's default effort.

Then recognition, the chunk merge and the source proposal, unchanged.

## Question

How does the head-to-head's winning single call do as the app's implementation, run through the path a user's source takes and followed by the schema-constrained relate step? This is not a new test of whether to adopt it: the user adopted it on the head-to-head's evidence.

## Decision rule (set in advance)

None for adoption: the decision was taken on the head-to-head's evidence (one Opus call ahead of `find_then_type` by more than the 0.08 noise threshold on both splits, over three takes). This page records one take of the implementation as built, so the offline replay and the CI quality tests cover it, and states its cost. It claims no gain of its own: a single take, and differences under 0.08 typed F1 are noise.

## Method

- Implementation `single_call`, configuration `extraction-single-call`, model `claude-opus-5-5`.
- Documents: `edit_check` and `gitlab_architecture` (dev), `wikimedia_enterprise` (holdout).
- Takes: one. Recorded through `scripts/benchmark_replay.py`'s path (`extract_document` with a recording provider), one request at a time, every call metered from its usage.
- Budget USD 6.00; spent $2.76.

## Results (one take, replayed offline)

| | found F1 | typed F1 | recall (core) | precision | type accuracy | relationship recall |
|---|---|---|---|---|---|---|
| `edit_check` (dev) | 0.511 | 0.467 | 0.605 (0.809) | 0.442 | 0.913 | 0.207 |
| `gitlab_architecture` (dev) | 0.710 | 0.686 | 0.713 (0.952) | 0.707 | 0.966 | 0.434 |
| `wikimedia_enterprise` (holdout) | 0.667 | 0.625 | 0.646 (0.684) | 0.688 | 0.938 | 0.161 |
| **dev mean** | **0.611** | **0.576** | 0.659 (0.881) | 0.575 | 0.939 | 0.321 |

Dev failure counts: 11 core and 54 supporting individuals missed, 7 mistyped, 92 spurious, 2 known distractors extracted, 89 relationships missed.

Against the head-to-head's numbers (typed F1; relationship recall):

| | typed F1 dev | typed F1 holdout | relationship recall dev / holdout |
|---|---|---|---|
| `single_call`, this take (one take) | 0.576 | 0.625 | 0.321 / 0.161 |
| Arm B, one Opus call, no relate step (three takes, mean [range]) | 0.624 [0.611-0.642] | 0.659 [0.640-0.674] | 0.038 / 0.012 |
| `find_then_type` (three takes, mean [range]) | 0.452 [0.426-0.465] | 0.442 [0.393-0.481] | 0.164 / 0.018 |
| `find_then_type`, committed take 1 (the take this replay is paired with) | 0.465 | 0.481 | 0.180 / 0.036 |

Read as one take:

- **Individuals:** above every `find_then_type` take on both splits (+0.11 dev, +0.14 holdout against its committed take), and below arm B's range on both (−0.05 dev, −0.03 holdout against its mean), within the noise threshold of B. The call listed more individuals than any arm B take (105, 124 and 93 against 81-100 per document), with higher recall than B (dev 0.659 vs 0.632) and lower precision (0.575 vs 0.702). Why is not established; the differences from arm B are that this call is not asked for relationships, answers in plain JSON rather than to a schema, and goes through the app's merge, recognition and proposal planning rather than the head-to-head's adapter.
- **Relationships:** the relate step on Opus, with the allowed class pairs, gives the highest relationship recall measured on this benchmark (dev 0.321, holdout 0.161, against 0.164 / 0.018 for `find_then_type` and 0.038 / 0.012 for arm B). Part of that may be Opus in the relate step rather than its input; that is not separated here.

## Cost per document

| | `edit_check` | `gitlab_architecture` | `wikimedia_enterprise` |
|---|---|---|---|
| find_individuals call (output tokens incl. thinking; latency) | $0.27 (10,744; 78 s) | $0.34 (12,618; 92 s) | $0.51 (8,557; 61 s) |
| relate calls (count, output tokens) | $0.45 (5, 18,797) | $0.90 (7, 37,948) | $0.29 (4, 11,819) |
| **total, as recorded** | **$0.72** | **$1.23** | **$0.80** |
| total with a cold cache | about $1.02 | about $1.53 | $0.80 |
| wall time | 4 min | 6 min | 3 min |

`wikimedia_enterprise` was recorded first and wrote the catalog to the cache ($0.31 of its cost); the two dev documents read it. A user extracting one document usually pays the write: about $0.8-1.5 a document, against $0.08-0.12 for `find_then_type`. The relate step on Opus is now more than half of the cost on the longer documents; running it on a cheaper model is the obvious lever, not measured. Prices (per million tokens, Opus 5.5): input $4, 5-minute cache write $5, cache read $0.20, output $20.

## Output-token limit

The single call used up to 12,618 output tokens here (arm B, which also listed relationships, up to 28,700). Selection capped a run's output limit at 20,000 because the Anthropic client refuses a request that does not stream above about 21,000. The simplest fix consistent with the selection method: the Anthropic provider now streams any request for more than 20,000 output tokens, and the cap (`MAX_OUTPUT_TOKENS` in `local-server/domain/pipelines/selection.py`) is 64,000, which `extraction-single-call` sets like any configuration's limit. The relate calls keep `find_then_type`'s own limit, 16,000 (or the run's when lower; `RELATE_MAX_TOKENS` in `single_call.py`); in this recording, made while they were still given 64,000, they used at most 11,808. The cassette key does not include the output limit, so the recording replays unchanged. A single call cut off at its limit is not asked again (it would be cut off the same way): its section fails, saying so.

## Limits

- One take. Arm A's whole-take range in the head-to-head was about 0.04-0.09 typed F1; nothing here is a new claim of gain.
- The gold is model-made (Claude Fable 5.2 drafting from whole documents with full definitions, model-reviewed), not human-checked, and may favour approaches that read whole documents with full definitions, as this one does.
- Three documents; per-document results differ a lot.
- Long documents (several sections) are covered only by unit tests with a fake LLM.
- Relationship recall is scored without relationship precision.
- The single call rates none of its individuals, so their typing triples carry no confidence (`None`). A confidence threshold (applying a run without a selection, the recognition preview's default 0.5) does not hold them to it: no score is not a score of 0 (`is_below_confidence` in `local-server/domain/extraction/services.py`). Their relationships, from the relate step, are rated as before.

## Verdict

**Adopted as the default implementation of individual extraction**, by the user's decision of 2026-11-17 on the head-to-head's evidence; this take is consistent with it (above every `find_then_type` take, within noise of arm B). `find_then_type`, two-pass `default` and `open_v1` stay selectable. Changed: `local-server/domain/pipelines/individual_extraction/bootstrap.py` (the registry's default), the Anthropic provider (streaming, `effort`), the output-limit cap, the Extract page's stage display, and [the current state](../README.md).

## Reproduce

From `local-server/`, offline and free:

```bash
python scripts/benchmark_replay.py                              # the default: single_call
python scripts/benchmark_replay.py --implementation single_call --json
```

Recordings: `tests/integration/fixtures/cassettes/extraction_benchmark_single_call/`. A new take is `--record --spend --implementation single_call` (about $3 for the three documents). The per-call cost ledger of this recording is scratch; not reproducible from the repository (the figures above are from it).

## Links

- Pull requests: the one that adds `single_call` (branch `claude/single-call-extraction`)
- Head-to-head: [2026-11-15-head-to-head.md](2026-11-15-head-to-head.md)
- Ledger entries: none (the refinement loop has no backlog for `single_call`)
