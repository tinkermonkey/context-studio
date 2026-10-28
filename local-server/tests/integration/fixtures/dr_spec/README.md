# Pinned DR spec snapshots

Each `dr_spec_<version>.tar.xz` is the subset of the `documentation_robotics` spec
that `scripts/dr_ontology_loader.py` reads (`spec/schemas/{nodes,relationships,base}/`
and `spec/dist/manifest.json`). Tests extract them via
`tests/integration/pipelines/_harness/dr_spec.py` instead of reading the live
sibling checkout, so expected row counts and recorded cassettes stay stable.
`scripts/import_dr_ontology.py` still reads the live sibling checkout by default.

| Snapshot | Source commit | Used by |
|---|---|---|
| `dr_spec_0.8.4.tar.xz` | `89f87e94` ("Bump spec version to 0.8.4") | `PINNED_DR_SPEC_VERSION`: the DR ontology integration tests and `scripts/record_recognition_episode_cassettes.py` |
| `dr_spec_0.10.0.tar.xz` | `9aaf1317` ("spec: retire supports-goals and fulfills-requirements; fix 18 four-part relationship ids") | `MODEL_DR_SPEC_VERSION`: `test_dr_model_import.py`, which imports Context Studio's own DR model (`documentation-robotics/model/`) |

Moving `PINNED_DR_SPEC_VERSION` to a new spec version means updating the expected
counts and re-recording the cassettes. Moving `MODEL_DR_SPEC_VERSION` only needs
a snapshot that matches the model's `spec_version`.

To regenerate a snapshot, or add one for a new spec version, run from the
`documentation_robotics` checkout:

```bash
git archive --format=tar <commit> \
  spec/schemas/nodes spec/schemas/relationships spec/schemas/base spec/dist/manifest.json \
  | xz -9e > <context-studio>/local-server/tests/integration/fixtures/dr_spec/dr_spec_<version>.tar.xz
```
