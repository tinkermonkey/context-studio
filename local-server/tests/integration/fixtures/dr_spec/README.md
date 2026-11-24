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
| `dr_spec_0.10.0.tar.xz` | `9aaf1317` ("spec: retire supports-goals and fulfills-requirements; fix 18 four-part relationship ids") | `GOLDEN_DR_SPEC_VERSION`: the DR golden tests (`test_dr_claims.py`, `test_dr_drift.py`, `test_evidence_pack_dr_golden.py`, `test_notes_to_claims_dr_golden.py`), whose fixtures DR made from this spec |
| `dr_spec_0.11.0.tar.xz` | `a06f0564` (the commit the workspace's DR taxonomy mirrored when the extraction benchmark was made) | `BENCHMARK_DR_SPEC_VERSION` in `scripts/benchmark_replay.py`: the ontology the benchmark documents are extracted against. `test_extraction_benchmark_replay.py` checks it builds the same classes, definitions and relationship types as `fixtures/pipelines/extraction_benchmark/dr_spec.bundle.json.xz` |
| `dr_spec_0.15.0.tar.xz` | `6e64c515` (tag `spec-v0.15.0`, "Merge pull request #1416 from tinkermonkey/release/cli-0.8.0-spec-0.15.0") | `MODEL_DR_SPEC_VERSION`: `test_dr_model_import.py` and `test_dr_model_type_changes.py`, which import Context Studio's own DR model (`documentation-robotics/model/`) |

Moving `PINNED_DR_SPEC_VERSION` to a new spec version means updating the expected
counts and re-recording the cassettes. Moving `MODEL_DR_SPEC_VERSION` needs
a snapshot that matches the model's `spec_version`, the expected counts in
`test_dr_model_import.py`, and relationship types in `test_dr_model_type_changes.py`
that the model still uses (and, for the rename, reverse and retarget, types the
spec does not have yet). `GOLDEN_DR_SPEC_VERSION` stays put until the golden
fixtures are regenerated from a newer spec.

To regenerate a snapshot, or add one for a new spec version, run from the
`documentation_robotics` checkout:

```bash
git archive --format=tar <commit> \
  spec/schemas/nodes spec/schemas/relationships spec/schemas/base spec/dist/manifest.json \
  | xz -9e > <context-studio>/local-server/tests/integration/fixtures/dr_spec/dr_spec_<version>.tar.xz
```
