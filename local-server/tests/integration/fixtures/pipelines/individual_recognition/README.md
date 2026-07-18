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
