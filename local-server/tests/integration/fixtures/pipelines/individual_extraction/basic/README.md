# `basic` — contract-test fixture, not a quality-corpus scenario

This directory follows the project-wide `basic/` naming convention used by
every pipeline type for a minimal `input.json` + `expected.json` pair (see
`tests/integration/fixtures/pipelines/README.md`). It is consumed by
functional/contract tests (e.g.
`tests/integration/pipelines/test_individual_extraction.py`) that exercise the
pipeline's execution contract with a `FakeLLMProvider`, not extraction
quality.

**It is not one of the 10 hand-labeled quality-corpus scenarios** (see
`tests/integration/pipelines/_harness/dataset_split.py` for the fixed
dev/holdout list: `async_patterns`, `clean_code`, `design_patterns`,
`distributed_systems`, `domain_driven_design`, `microservices_architecture`,
`object_oriented_design`, `reactive_programming`, `service_oriented`,
`testing_strategies`). Unlike those, it has no `distractors.json` and no GT
triples worth scoring (`expected.json` intentionally has an empty triples
list) — do not add it to `QUALITY_SCENARIOS` or the dev/holdout split.
