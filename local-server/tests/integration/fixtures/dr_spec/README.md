# Pinned DR spec snapshot

`dr_spec_0.8.4.tar.xz` is the subset of the `documentation_robotics` spec that
`scripts/dr_ontology_loader.py` reads (`spec/schemas/{nodes,relationships,base}/`
and `spec/dist/manifest.json`), taken at spec version **0.8.4**, commit
`89f87e94` ("Bump spec version to 0.8.4") of the `documentation_robotics` repo.

The DR ontology integration tests and `scripts/record_recognition_episode_cassettes.py`
build against this snapshot (via `tests/integration/pipelines/_harness/dr_spec.py`)
instead of the live sibling checkout, so expected row counts and recorded
cassettes stay stable. `scripts/import_dr_ontology.py` still reads the live
sibling checkout by default.

To regenerate it, or to move to a new spec version (then update
`PINNED_DR_SPEC_VERSION`, the expected counts, and re-record the cassettes),
run from the `documentation_robotics` checkout:

```bash
git archive --format=tar <commit> \
  spec/schemas/nodes spec/schemas/relationships spec/schemas/base spec/dist/manifest.json \
  | xz -9e > <context-studio>/local-server/tests/integration/fixtures/dr_spec/dr_spec_<version>.tar.xz
```
