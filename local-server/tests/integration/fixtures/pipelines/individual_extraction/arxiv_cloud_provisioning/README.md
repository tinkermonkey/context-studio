# Arxiv Cloud Provisioning Fixture (DR-relabeled)

**Source:** Arxiv-style research-paper abstract about AI-driven multi-region cloud spot-fleet provisioning, originally bundled as an unused NLP-pipeline test fixture (specific paper/authors not attributed in the source fixture).
**Promoted from:** `fixture_cloud_provisioning_paper.json`
**License:** Educational use, fair use for testing
**Curator:** Human-reviewed relabel against the DR ontology (see `../LEGACY_CORPUS_DISPOSITION.md`).

## Overview
This scenario was **relabeled from its original free-form GT to a DR-native
ground truth** graded against the imported Documentation Robotics ontology
(`ontology_id: dr_spec`). The original auto-drafted GT used free-form,
un-clamped predicates (`provides`, `estimates`, …) against the placeholder
ontology; the human review (`../NEEDS_HUMAN_REVIEW.md`) retired the other arxiv
scenarios and relabeled this one against the DR spec.

## Annotation notes — DR-native GT
- **Every triple is spec-valid.** Each `is_a` grounds an individual to a real
  DR class (ArchiMate element, e.g. `technology.node`,
  `application.applicationcomponent`), and each relationship uses a DR predicate
  that the spec actually defines between the two individuals' classes
  (`node --realizes--> technologyservice`, `applicationcomponent --accesses-->
  dataobject`, `technologyservice --satisfies--> requirement`, …).
- **Modeling decisions** (recorded during the review): `elastic_infrastructure`
  → `technology.technologycollaboration` (an aggregate/pool per its definition,
  not a discrete service); "platform relies on infrastructure" modeled as
  `Elastic Infrastructure --realizes--> Cloud Service Platform`. The
  "AI service combines predictive models" relation was intentionally dropped —
  the DR spec offers no clean edge between `technologyservice` and
  `applicationcomponent` in that direction; the models instead appear via
  `Predictive Models --accesses--> Fleet Configuration`.
- The `excluded` example (`EC2 Spot Service --satisfies--> Multi-Region
  Requirement`) uses a *valid* predicate but a text-contradicted instance: the
  EC2 Spot Service restricts to a single region — only the proposed AI service
  meets the multi-region requirement.
- This GT was authored with the DR ontology's class + predicate definitions in
  view; it should still be re-skimmed by a human before being treated as a
  hard accept/reject signal.
