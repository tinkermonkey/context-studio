# Individual-extraction benchmark

Hand-made extractions of three prose documents against the Documentation Robotics (DR) schema.
They are the baseline the individual-extraction pipelines are scored against: each `gold.json`
holds every individual a careful modeller finds in its `source.md`, typed against DR, with the
passages that evidence it.

The existing quality corpus (`../individual_extraction/`) is short passages written for the test,
scored as triples. This benchmark is the opposite end: real, long documents (3,000 to 6,000 words)
that describe software from different points of view, run through the same path a user's source
takes (chunking, boilerplate skipping, merging, proposing), and scored on the individuals that
reach the review queue.

## The documents

| id | perspective | source | individuals (core) | relationships |
|---|---|---|---|---|
| `gitlab_architecture` | engineering | [GitLab architecture overview](https://docs.gitlab.com/development/architecture/) | 122 (63) | 83 |
| `edit_check` | product | [Edit check](https://www.mediawiki.org/wiki/Edit_check), MediaWiki.org | 76 (42) | 53 |
| `wikimedia_enterprise` | platform | [Wikimedia Enterprise](https://meta.wikimedia.org/wiki/Wikimedia_Enterprise), Meta-Wiki | 99 (38) | 56 |

All three are CC BY-SA 4.0; each `gold.json` records the revision, the retrieval date and the
attribution under `document`. The `source.md` files are adaptations: GitLab's is the upstream
markdown with link targets removed; the two wiki pages were converted from their rendered HTML,
keeping headings, lists and tables, and dropping navigation, footnote markers and (for Wikimedia
Enterprise) the press-clippings list. The Edit check staff list was left out. Under the licence's
share-alike term these adapted texts, and the extractions made from them, are CC BY-SA 4.0 too.

Together they cover the application and technology layers (GitLab), motivation and product (Edit
check) and business and motivation (Wikimedia Enterprise), with smaller amounts of api, security,
ux, apm, data-model and data-store. Navigation and testing have no coverage; DR extracts those
from code.

## The schema they were made against

`dr_spec.bundle.json.xz` is the DR taxonomy as it stood in the workspace when the extractions
were made (DR spec 0.11.0, commit a06f0564), exported as a schema-only Context Studio bundle:
layers, classes with their definitions and attributes, predicates and the valid relationship
types. Gold files are validated against it, and the offline replay builds its ontology from it,
so a pipeline is prompted with the same definitions the extractions were judged by. Refresh it
with `GET /api/v1/interchange/bundles/<taxonomy id>?schema_only=true`.
When the DR spec moves, re-check the gold types against the new definitions before trusting
scores (a renamed or split class changes what "correct" means).

## What a gold file holds

- `individuals[]`
  - `key`: stable id within the file
  - `title`, `aliases`: the names a run may give it
  - `class`: the DR type a careful modeller would choose
  - `acceptable_classes`: other types that are defensible where DR leaves a judgment call. A run
    that picks one is typed correctly.
  - `tier`: `core` when the document names the element and says what it is or does, or lists it in
    its main inventory (GitLab's component table, Edit check's outcome tables); `supporting` when
    it is named only in a diagram, a table cell, an example or in passing, or when the title had to
    be written from a statement. Where two items sit in the same list, the one the document treats
    at more length is core.
  - `description`: one sentence, in our words
  - `data`: values for the class's attributes, only where the text gives them
  - `evidence[]`: verbatim passages, with character offsets into `source.md`
- `relationships[]`: `source`, `predicate`, `target` (keys), `tier`, `evidence[]`. Only
  relationships the text states, each a valid type in the schema. They are the plainly stated
  ones, not every relationship a run could correctly derive (GitLab's diagrams alone have about a
  hundred edges), so relationships are scored on recall only.
- `excluded[]`: things the text names that were left out on purpose, with the reason. A run that
  extracts one is counted separately from a run that invents something.

### Rules the extractions follow

1. An individual is a named fact about the system the document describes, or its immediate
   context: its users, the organisations and the external systems it works with. Prior art, press,
   named people, link lists and navigation are out.
2. One individual per thing, typed by its main sense in this document. Where the same name is
   used for two things (GitLab Pages the component and the feature), the other reading goes in
   `acceptable_classes`.
3. Third-party software the team runs but did not write is `technology.systemsoftware` (Puma,
   Sidekiq, PostgreSQL); software the team wrote is an application component.
4. Goals, requirements, principles, drivers, findings and outcomes are individuals when the text
   states them as such. Their title is a short paraphrase; the statement is the evidence. What a
   component does, taken from its one-line description, is not a separate individual.
5. A product measure with a name and a definition (revert rate, edit completion rate) is an
   `apm.metricinstrument`; DR links it to what it measures with `measures-outcome`.
6. Named policies an organisation adopts are `motivation.constraint`, not `security.securitypolicy`
   (which is a set of access rules).

## How they were made

Three passes per document, in November 2026: a first extraction by Claude (Fable 5.2) working from
the DR definitions; an independent pass in which a second reviewer extracted blind from the source
and the definitions and then compared; and an adjudication of every difference against the
definitions. The second pass removed duplicates (personas the text never separates), items that
were prior art or link text, and relationships that were inferred rather than stated, and added
what the first pass missed. No pipeline output was used to decide what is an individual or how it
is typed. After the first baseline run, seven aliases were added to `gitlab_architecture` for names
the document itself uses and the run had picked ("Community Edition (CE)", "GitLab self-monitoring:
Grafana"), so that a run is not marked wrong for using the document's wording.

They are a careful reading, not a ruling: where a run's "spurious" prediction turns out to be
something the document does say, fix the gold file (and note it in the commit) rather than tune a
pipeline toward the omission.

## Using them

From `local-server/`, with the server running:

```bash
python scripts/extraction_benchmark.py validate
python scripts/extraction_benchmark.py load                      # datasets bench-* in the DR taxonomy
python scripts/extraction_benchmark.py run --document edit_check --spend   # calls the LLM
python scripts/extraction_benchmark.py score --document edit_check --proposal <proposal id>
```

`load` puts a gold extraction into the workspace as a dataset (`bench-gitlab-architecture`,
`bench-edit-check`, `bench-wikimedia-enterprise`): the source document, then one applied proposal
whose operations carry the passages, so every individual shows where it came from. `run` extracts
the document into a fresh `bench-run-*` dataset with a pipeline configuration and scores the
proposal it produces; the proposal stays pending in the review queue.

Scoring is in `tests/integration/pipelines/_harness/benchmark.py`: recall (all and core),
precision, type accuracy, typed F1, relationship recall, a breakdown by layer, and the lists
behind them (missed, mistyped, spurious, duplicates, known distractors). The rules:

- A prediction finds a gold individual by its title or an alias; a prediction typed as a
  statement that names no gold individual can also find a gold statement by its passage, and
  those pair so that as many statements as possible are found. The scores do not depend on the
  order of the predictions.
- A found individual is typed correctly when every class the run gave it, under any of its
  names, is the gold class or an acceptable one. The right class with a wrong one beside it is
  mistyped, on one prediction or split over two that name the same individual: it would be
  created in both. `type_accuracy_any` reports how many had an accepted class among those given,
  to tell hedged typing from wrong typing.
- When two predictions name the same gold individual ("GitLab Runner" and "Runner"), the one
  under its title finds it and the other is a duplicate. Duplicates are listed, and left out of
  precision: gold sometimes joins what a run may defensibly extract apart ("Link check and
  Reference reliability"). Their classes still count toward the typing rule above.
- A relationship's ends are resolved by any name of an individual the run found, so a
  relationship stated under an alias counts. A title the run gave to two found statements names
  neither.

Offline, `scripts/benchmark_replay.py` scores one target on these documents from recorded LLM
responses: an implementation of individual extraction with one of its configurations
(`--implementation`, `--configuration`, each defaulting through the pipeline registry). Two
targets are recorded: `default` with `extraction-openrouter-default` (Gemini 3 Flash,
`cassettes/extraction_benchmark/`) and `find_then_type` with `extraction-find-then-type` (Claude
Haiku 5.5, `cassettes/extraction_benchmark_find_then_type/`); `--all` replays both. The variant
tournament ends with the same pass for the target it is given, and
`tests/integration/pipelines/test_extraction_benchmark_replay.py` replays both sets in CI, so a
change that makes either stale fails until it is recorded again. See `experiments/README.md`.
