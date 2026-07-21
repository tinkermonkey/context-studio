# SME Fixture (Wave 5, SCAFFOLD): sme_waypoint_security_data_protection

> **STATUS: PROSE DRAFTED (review it) — GT NOT YET AUTHORED.** `input.json`
> holds candidate agent-drafted prose for you to review/edit; `expected.json`
> and `distractors.json` are still TODO templates for you to author. This
> scenario is **not** in the scored split yet (see graduation at the bottom).

**Intent:** Waypoint's data-protection posture: how customer/job information entities are classified, retained, audited, and protected against threats via countermeasures.

**Source:** SME-authored prose for "Waypoint," the fictional field-service
scheduling/dispatch platform used by the Wave 2/3 corpus. Continue that product;
restate any entity introduced elsewhere (each scenario's GT must be
self-contained — prose-only sourcing rule, design doc §3).

**Wave:** 5 — SME-authored coverage-growth scenarios (holdout thickening +
`security`-layer coverage). Folded into the scored dev/holdout split on
graduation, like Wave 2/3 (NOT a diagnostic tier).

**Split:** `holdout` — gives the holdout veto power over the security layer (currently dev-only).

**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`).

**Layer focus:** `security`.

## DR class palette for this layer (is_a `object` targets)

Use these fully-qualified refs as the `object.label` on each individual's `is_a`
triple (full layer list: DR spec `schemas/nodes/security/`):

- `security.dataclassification`
- `security.informationentity`
- `security.secureresource`
- `security.retentionpolicy`
- `security.auditconfig`
- `security.threat`
- `security.countermeasure`
- `security.securityconstraints`
- `security.evidence`

## Valid relationship predicates

Spec-valid `(subject_class, predicate, object_class)` edges sourced from this
scenario's classes. Object refs are fully qualified — a `security.` object stays
in this layer; anything else is a legitimate cross-layer edge you may use if the
prose supports it.

**Within this scenario's focused classes:**

- `security.auditconfig` --depends-on--> `security.retentionpolicy`
- `security.auditconfig` --governs--> `security.retentionpolicy`
- `security.auditconfig` --governs--> `security.secureresource`
- `security.auditconfig` --mitigates--> `security.threat`
- `security.auditconfig` --monitors--> `security.secureresource`
- `security.auditconfig` --triggers--> `security.evidence`
- `security.countermeasure` --fulfills--> `security.securityconstraints`
- `security.countermeasure` --mitigates--> `security.threat`
- `security.countermeasure` --monitors--> `security.secureresource`
- `security.countermeasure` --protects--> `security.secureresource`
- `security.countermeasure` --requires--> `security.evidence`
- `security.dataclassification` --governs--> `security.informationentity`
- `security.dataclassification` --governs--> `security.retentionpolicy`
- `security.dataclassification` --governs--> `security.secureresource`
- `security.dataclassification` --requires--> `security.countermeasure`
- `security.evidence` --mitigates--> `security.threat`
- `security.evidence` --realizes--> `security.auditconfig`
- `security.informationentity` --constrained-by--> `security.dataclassification`
- `security.informationentity` --constrained-by--> `security.retentionpolicy`
- `security.retentionpolicy` --constrains--> `security.informationentity`
- `security.retentionpolicy` --governs--> `security.auditconfig`
- `security.retentionpolicy` --governs--> `security.evidence`
- `security.retentionpolicy` --mandates--> `security.countermeasure`
- `security.retentionpolicy` --requires--> `security.countermeasure`
- `security.threat` --accesses--> `security.secureresource`
- `security.threat` --aggregates--> `security.countermeasure`
- `security.threat` --targets--> `security.informationentity`
- `security.threat` --targets--> `security.secureresource`

**To other security-layer classes:**

- `security.auditconfig` --fulfills--> `security.accountabilityrequirement`
- `security.countermeasure` --implements--> `security.securitypolicy`
- `security.dataclassification` --governs--> `security.fieldaccesscontrol`
- `security.dataclassification` --supports--> `security.securitypolicy`
- `security.evidence` --supports--> `security.accountabilityrequirement`
- `security.evidence` --validates--> `security.policyrule`
- `security.informationentity` --governs--> `security.informationright`
- `security.informationentity` --requires--> `security.accountabilityrequirement`
- `security.secureresource` --aggregates--> `security.fieldaccesscontrol`
- `security.secureresource` --aggregates--> `security.resourceoperation`
- `security.securityconstraints` --aggregates--> `security.bindingofduty`
- `security.securityconstraints` --aggregates--> `security.needtoknow`
- `security.securityconstraints` --aggregates--> `security.separationofduty`
- `security.securityconstraints` --constrains--> `security.role`
- `security.securityconstraints` --enforces--> `security.securitypolicy`
- …(+1 more in `schemas/relationships/security/`)

**Cross-layer edges:**

- `security.countermeasure` --protects--> `business.businessprocess`
- `security.countermeasure` --realizes--> `motivation.goal`
- `security.countermeasure` --satisfies--> `motivation.requirement`
- `security.secureresource` --references--> `business.businessobject`
- `security.securityconstraints` --implements--> `motivation.constraint`
- `security.threat` --constrains--> `access-condition`
- `security.threat` --influence--> `data-classification`
- `security.threat` --influence--> `security-policy`
- `security.threat` --maps-to--> `motivation.requirement`
- `security.threat` --realizes--> `motivation.driver`
- `security.threat` --targets--> `business.businessprocess`
- `security.threat` --targets--> `business.businessservice`
- `security.threat` --triggers--> `audit-config`

**Thin-tail predicates to deliberately exercise here:** `governs`, `constrains`, `protects`, `mitigates` — the corpus
currently has <3 GT instances of these; using them stabilizes strict predicate
scoring.

## Authoring checklist

1. Write `input.json` `text`: a coherent security-focused note/spec about Waypoint.
2. `expected.json` `result.triples`: one `is_a` triple per distinct individual
   (object = a class ref above), then relationship triples between individuals
   (predicates from the lists above). Every triple must be text-supported;
   `confidence: 1.0`. Delete the `_comment` template objects.
3. `expected.json` `result.excluded`: >=1 true-negative (a plausible edge the
   text contradicts) with a `note`.
4. `distractors.json`: one near-miss triple (confidence ~0.2).
5. Aim for ~15-25 triples (matches the Wave 2/3 scenarios).

## Graduation (moves it into the scored split)

Once GT is authored:
1. Record its `default` cassette: `pytest --refresh-cassettes -k "test_quality_scenario_with_metrics and sme_waypoint_security_data_protection"` (needs live LLM).
2. In `_harness/dataset_split.py`, move `"sme_waypoint_security_data_protection"` from `WAVE5_PENDING_SCENARIOS` into `WAVE5_SME_HOLDOUT_SCENARIOS` (uncomment the wiring) so it joins `INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS` + `SCENARIO_ONTOLOGY`.
3. `pytest tests/unit/test_harness_dataset_split.py` to confirm the split is valid.
