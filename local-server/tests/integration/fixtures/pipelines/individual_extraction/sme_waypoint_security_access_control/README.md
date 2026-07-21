# SME Fixture (Wave 5, SCAFFOLD): sme_waypoint_security_access_control

> **STATUS: PROSE DRAFTED + `is_a` TRIPLES PREFILLED — RELATIONSHIP GT NOT YET
> AUTHORED.** `input.json` holds candidate prose (review/edit); `expected.json`
> has one `is_a` typing triple per named individual (review them) plus a TODO
> placeholder where you add the relationship triples + the `excluded`
> true-negative; `distractors.json` is still a TODO template. This scenario is
> **not** in the scored split yet (see graduation at the bottom).

**Intent:** Waypoint's access-control model: the actors, roles, and permissions governing which secure resources a field technician vs. dispatcher may act on, and the policies that constrain them.

**Source:** SME-authored prose for "Waypoint," the fictional field-service
scheduling/dispatch platform used by the Wave 2/3 corpus. Continue that product;
restate any entity introduced elsewhere (each scenario's GT must be
self-contained — prose-only sourcing rule, design doc §3).

**Wave:** 5 — SME-authored coverage-growth scenarios (holdout thickening +
`security`-layer coverage). Folded into the scored dev/holdout split on
graduation, like Wave 2/3 (NOT a diagnostic tier).

**Split:** `dev` — adds security-layer training coverage (currently zero).

**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`).

**Layer focus:** `security`.

## DR class palette for this layer (is_a `object` targets)

Use these fully-qualified refs as the `object.label` on each individual's `is_a`
triple (full layer list: DR spec `schemas/nodes/security/`):

- `security.actor`
- `security.role`
- `security.permission`
- `security.secureresource`
- `security.accesscondition`
- `security.authenticationconfig`
- `security.policyrule`
- `security.securitypolicy`
- `security.resourceoperation`

## Valid relationship predicates

Spec-valid `(subject_class, predicate, object_class)` edges sourced from this
scenario's classes. Object refs are fully qualified — a `security.` object stays
in this layer; anything else is a legitimate cross-layer edge you may use if the
prose supports it.

**Within this scenario's focused classes:**

- `security.accesscondition` --composes--> `security.policyrule`
- `security.accesscondition` --constrains--> `security.permission`
- `security.accesscondition` --references--> `security.secureresource`
- `security.actor` --accesses--> `security.secureresource`
- `security.actor` --assigned-to--> `security.role`
- `security.actor` --governed-by--> `security.authenticationconfig`
- `security.actor` --requires--> `security.authenticationconfig`
- `security.authenticationconfig` --authenticates--> `security.actor`
- `security.authenticationconfig` --constrained-by--> `security.securitypolicy`
- `security.authenticationconfig` --protects--> `security.secureresource`
- `security.permission` --authorizes--> `security.resourceoperation`
- `security.policyrule` --authorizes--> `security.permission`
- `security.policyrule` --composes--> `security.securitypolicy`
- `security.policyrule` --protects--> `security.secureresource`
- `security.policyrule` --uses--> `security.accesscondition`
- `security.resourceoperation` --accesses--> `security.secureresource`
- `security.resourceoperation` --constrained-by--> `security.accesscondition`
- `security.resourceoperation` --governs--> `security.secureresource`
- `security.role` --accesses--> `security.secureresource`
- `security.role` --aggregates--> `security.permission`
- `security.role` --authorizes--> `security.permission`
- `security.role` --provides--> `security.permission`
- `security.role` --specializes--> `security.role`
- `security.secureresource` --aggregates--> `security.resourceoperation`
- `security.securitypolicy` --aggregates--> `security.policyrule`
- `security.securitypolicy` --constrains--> `security.permission`
- `security.securitypolicy` --enforces-requirement--> `security.accesscondition`
- `security.securitypolicy` --governs--> `security.secureresource`

**To other security-layer classes:**

- `security.accesscondition` --governs--> `security.fieldaccesscontrol`
- `security.accesscondition` --uses--> `security.validationrule`
- `security.actor` --associated-with--> `security.delegation`
- `security.actor` --associated-with--> `security.threat`
- `security.actor` --constrained-by--> `security.securityconstraints`
- `security.actor` --references--> `security.delegation`
- `security.authenticationconfig` --depends-on--> `security.auditconfig`
- `security.authenticationconfig` --references--> `security.passwordpolicy`
- `security.authenticationconfig` --uses--> `security.passwordpolicy`
- `security.policyrule` --generates--> `security.evidence`
- `security.policyrule` --governs--> `security.informationright`
- `security.policyrule` --mandates--> `security.countermeasure`
- `security.policyrule` --requires--> `security.countermeasure`
- `security.policyrule` --triggers--> `security.policyaction`
- `security.policyrule` --uses--> `security.condition`
- …(+7 more in `schemas/relationships/security/`)

**Cross-layer edges:**

- `security.role` --maps-to--> `business.businessrole`
- `security.secureresource` --references--> `business.businessobject`
- `security.securitypolicy` --constrains--> `business.businessprocess`
- `security.securitypolicy` --governs--> `business.businessservice`
- `security.securitypolicy` --realizes--> `motivation.principle`
- `security.securitypolicy` --satisfies--> `motivation.requirement`

**Thin-tail predicates to deliberately exercise here:** `governs`, `constrains`, `protects` — the corpus
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
1. Record its `default` cassette: `pytest --refresh-cassettes -k "test_quality_scenario_with_metrics and sme_waypoint_security_access_control"` (needs live LLM).
2. In `_harness/dataset_split.py`, move `"sme_waypoint_security_access_control"` from `WAVE5_PENDING_SCENARIOS` into `WAVE5_SME_DEV_SCENARIOS` (uncomment the wiring) so it joins `INDIVIDUAL_EXTRACTION_DEV_SCENARIOS` + `SCENARIO_ONTOLOGY`.
3. `pytest tests/unit/test_harness_dataset_split.py` to confirm the split is valid.
