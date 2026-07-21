# SME Fixture (Wave 5, SCAFFOLD): sme_waypoint_tech_deployment_topology

> **STATUS: PROSE DRAFTED + `is_a` TRIPLES PREFILLED — RELATIONSHIP GT NOT YET
> AUTHORED.** `input.json` holds candidate prose (review/edit); `expected.json`
> has one `is_a` typing triple per named individual (review them) plus a TODO
> placeholder where you add the relationship triples + the `excluded`
> true-negative; `distractors.json` is still a TODO template. This scenario is
> **not** in the scored split yet (see graduation at the bottom).

**Intent:** Waypoint's runtime deployment topology: the compute nodes, system software, and technology services that host the dispatch platform, and how they connect.

**Source:** SME-authored prose for "Waypoint," the fictional field-service
scheduling/dispatch platform used by the Wave 2/3 corpus. Continue that product;
restate any entity introduced elsewhere (each scenario's GT must be
self-contained — prose-only sourcing rule, design doc §3).

**Wave:** 5 — SME-authored coverage-growth scenarios (holdout thickening +
`security`-layer coverage). Folded into the scored dev/holdout split on
graduation, like Wave 2/3 (NOT a diagnostic tier).

**Split:** `holdout` — gives the holdout veto power over the technology layer (currently dev-only).

**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`).

**Layer focus:** `technology`.

## DR class palette for this layer (is_a `object` targets)

Use these fully-qualified refs as the `object.label` on each individual's `is_a`
triple (full layer list: DR spec `schemas/nodes/technology/`):

- `technology.node`
- `technology.systemsoftware`
- `technology.technologyservice`
- `technology.communicationnetwork`
- `technology.device`
- `technology.technologycollaboration`
- `technology.artifact`

## Valid relationship predicates

Spec-valid `(subject_class, predicate, object_class)` edges sourced from this
scenario's classes. Object refs are fully qualified — a `technology.` object stays
in this layer; anything else is a legitimate cross-layer edge you may use if the
prose supports it.

**Within this scenario's focused classes:**

- `technology.artifact` --aggregates--> `technology.artifact`
- `technology.artifact` --associated-with--> `technology.systemsoftware`
- `technology.artifact` --composes--> `technology.artifact`
- `technology.artifact` --depends-on--> `technology.artifact`
- `technology.artifact` --realizes--> `technology.technologyservice`
- `technology.communicationnetwork` --aggregates--> `technology.communicationnetwork`
- `technology.communicationnetwork` --assigned-to--> `technology.technologycollaboration`
- `technology.communicationnetwork` --associated-with--> `technology.systemsoftware`
- `technology.communicationnetwork` --connects--> `technology.node`
- `technology.communicationnetwork` --serves--> `technology.device`
- `technology.communicationnetwork` --serves--> `technology.node`
- `technology.communicationnetwork` --supports--> `technology.technologyservice`
- `technology.device` --composes--> `technology.node`
- `technology.device` --composes--> `technology.systemsoftware`
- `technology.node` --composes--> `technology.artifact`
- `technology.node` --composes--> `technology.device`
- `technology.node` --composes--> `technology.systemsoftware`
- `technology.node` --realizes--> `technology.technologyservice`
- `technology.systemsoftware` --accesses--> `technology.artifact`
- `technology.systemsoftware` --composes--> `technology.artifact`
- `technology.systemsoftware` --depends-on--> `technology.device`
- `technology.systemsoftware` --depends-on--> `technology.systemsoftware`
- `technology.systemsoftware` --realizes--> `technology.technologyservice`
- `technology.systemsoftware` --uses--> `technology.communicationnetwork`
- `technology.technologycollaboration` --accesses--> `technology.artifact`
- `technology.technologycollaboration` --aggregates--> `technology.node`
- `technology.technologycollaboration` --associated-with--> `technology.technologycollaboration`
- `technology.technologycollaboration` --realizes--> `technology.technologyservice`
- `technology.technologycollaboration` --uses--> `technology.communicationnetwork`
- `technology.technologyservice` --associated-with--> `technology.technologycollaboration`
- …(+6 more in `schemas/relationships/technology/`)

**To other technology-layer classes:**

- `technology.artifact` --flows-to--> `technology.technologyprocess`
- `technology.communicationnetwork` --aggregates--> `technology.path`
- `technology.communicationnetwork` --provides--> `technology.technologyinterface`
- `technology.node` --assigned-to--> `technology.technologyfunction`
- `technology.node` --composes--> `technology.technologyinterface`
- `technology.systemsoftware` --assigned-to--> `technology.technologyfunction`
- `technology.systemsoftware` --provides--> `technology.technologyinterface`
- `technology.systemsoftware` --serves--> `technology.technologyfunction`
- `technology.systemsoftware` --triggers--> `technology.technologyevent`
- `technology.systemsoftware` --uses--> `technology.path`
- `technology.technologycollaboration` --aggregates--> `technology.technologyinterface`
- `technology.technologycollaboration` --performs--> `technology.technologyinteraction`
- `technology.technologycollaboration` --triggers--> `technology.technologyevent`
- `technology.technologycollaboration` --uses--> `technology.path`
- `technology.technologyservice` --aggregates--> `technology.technologyfunction`
- …(+4 more in `schemas/relationships/technology/`)

**Cross-layer edges:**

- `technology.device` --satisfies--> `security.securitypolicy`
- `technology.device` --serves--> `application.applicationcomponent`
- `technology.node` --satisfies--> `motivation.constraint`
- `technology.node` --satisfies--> `security.securitypolicy`
- `technology.node` --serves--> `application.applicationcomponent`
- `technology.node` --serves--> `business.businessprocess`
- `technology.systemsoftware` --implements--> `security.countermeasure`
- `technology.systemsoftware` --implements--> `motivation.principle`
- `technology.systemsoftware` --mitigates--> `security.threat`
- `technology.systemsoftware` --realizes--> `application.applicationservice`
- `technology.systemsoftware` --realizes--> `business.businessservice`
- `technology.systemsoftware` --realizes--> `motivation.goal`
- `technology.systemsoftware` --realizes--> `security.securitypolicy`
- `technology.systemsoftware` --satisfies--> `motivation.constraint`
- `technology.systemsoftware` --satisfies--> `motivation.requirement`
- …(+13 more in `schemas/relationships/technology/`)

**Thin-tail predicates to deliberately exercise here:** `assigned-to` — the corpus
currently has <3 GT instances of these; using them stabilizes strict predicate
scoring.

## Authoring checklist

1. Write `input.json` `text`: a coherent technology-focused note/spec about Waypoint.
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
1. Record its `default` cassette: `pytest --refresh-cassettes -k "test_quality_scenario_with_metrics and sme_waypoint_tech_deployment_topology"` (needs live LLM).
2. In `_harness/dataset_split.py`, move `"sme_waypoint_tech_deployment_topology"` from `WAVE5_PENDING_SCENARIOS` into `WAVE5_SME_HOLDOUT_SCENARIOS` (uncomment the wiring) so it joins `INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS` + `SCENARIO_ONTOLOGY`.
3. `pytest tests/unit/test_harness_dataset_split.py` to confirm the split is valid.
