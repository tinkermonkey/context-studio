# Individual-recognition episodes (issue #1142)

Multi-document episodes for measuring cross-document entity recognition (dedup):
each episode is a set of ordered documents that mention shared entities with
surface variants, plus `expected_entities.json` — the coreference gold (which
mentions across docs are the same entity).

## What recognition does and does not resolve (measured finding)

Recognition = exact-label match, then a conservative vector match (title
embedding, class-scoped, threshold 0.90 + ambiguity margin), biased toward "new
node". Measured against the imported DR ontology with real embeddings:

- **Surface variants — resolved perfectly** (`surface_variants` episode:
  precision 1.0, recall 1.0). Casing (`Kubernetes`/`kubernetes`), pluralization
  (`RAPL Counter`/`RAPL counters`, `Data Object`/`data objects`), punctuation —
  the casing/pluralization problem that motivated recognition. Surface variants
  embed at ~0.97 cosine (or match exactly), so they merge; nothing false-merges.

- **Abbreviation-aliases — NOT resolved, by design** (`kubernetes_energy`
  episode: precision 1.0, recall ~0.33). The embedding model (all-MiniLM) does
  not know `K8s` = `Kubernetes` (cosine ~0.39, near-random) or that
  `the Nextflow engine` = `Nextflow` (~0.80). No threshold can accept these
  without merging unrelated entities, so recognition correctly leaves them
  separate. Precision (the safety metric) stays 1.0.

Resolving true aliases would need a separate mechanism — a curated/accrued alias
registry (persist confirmed variants as `external_references`) or LLM
adjudication (out of scope: needs a per-(mention, candidate) cassette scheme).
It is a distinct problem from the casing/pluralization one recognition solves.

## Cassettes (issue #1142 Phase 2)

Each episode has one recorded LLM cassette per document, under
`<episode>/cassettes/doc_NN.json`, replayed via `CassetteLLMProvider` by the
full-pipeline episode runner (`_harness/episode_runner.py`, "Level 2"). They
were produced by `scripts/record_recognition_episode_cassettes.py`, whose
docstring documents their provenance: no live LLM provider was available when
they were recorded, so each document's pass-1/pass-2 responses were authored
by reading the fixture text against the exact prompts `ExtractionService`
builds, then run for real through `IndividualExtractionOrchestrator` wrapped
in `RecordingLLMProvider` — every downstream code path (prompt construction,
response parsing, ontology canonicalization, hashing) executes exactly as it
would recording against a live model. Pass-1 typing triples mirror the
ground-truth surfaces in `expected_entities.json` exactly, since both
episodes' sentences are short and unambiguous enough that a careful reading
extracts every named individual they mention. Re-record with
`python scripts/record_recognition_episode_cassettes.py` if a fixture's text
or the DR ontology changes.

**Level 2 (full pipeline, real cassettes) vs. Level 1 (GT-mention-only)**,
measured with real embeddings
(`test_recognition_episode_cassette_replay.py`):

| Episode | Level | precision | recall | node_count_ratio |
|---|---|---|---|---|
| `surface_variants` | 1 (GT mentions) | 1.0 | 1.0 | 1.0 |
| `surface_variants` | 2 (full pipeline) | 1.0 | 1.0 | 1.0 |
| `kubernetes_energy` | 1 (GT mentions) | 1.0 | ~0.33 | — |
| `kubernetes_energy` | 2 (full pipeline) | 1.0 | 0.3333 | 1.5 |

No divergence: the LLM cassettes extract every ground-truth mention in both
episodes (zero `extraction_misses`), so Level 2 feeds recognition the same
mention set Level 1 feeds it directly, and — since recognition is the same
non-LLM code either way — produces the same clustering. `kubernetes_energy`'s
recall gap versus `surface_variants` is the same already-documented
abbreviation-alias limitation above (`K8s`/`Kubernetes`, `the Nextflow
engine`/`Nextflow`), not a new one introduced by the full pipeline.

ADR-1 (cassette hashes are independent of prior documents' graph state) is
verified directly by
`test_recognition_episode_cassette_replay.py::TestCassetteHashGraphStateIndependence`,
which rebuilds a document's pass-1 prompt before and after materializing an
individual into the graph and asserts the prompt text — and therefore its
cassette hash key — is unchanged.
