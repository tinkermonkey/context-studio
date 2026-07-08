# SME Fixture: Waypoint Business Operations

**Source:** Originally authored operations-runbook prose for "Waypoint," a
plausible field-service scheduling and dispatch platform (fictional product,
written in the register of a typical internal operations runbook).
**Wave:** 2 -- upper-layer SME-authored scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §6, #1109 Phase 6).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** business (product, businessservice, businessactor,
businessrole, businessprocess, businessevent, businessinterface,
businessfunction, contract), with incidental motivation-layer touches
(stakeholder, goal, requirement) where the business layer's own relationship
schemas cross into motivation (e.g. `business.businessrole.serves.
motivation.stakeholder`).

## Overview

`expected.json` was hand-adjudicated directly against the Wave 0 DR
ontology's classes and relationship types -- no LLM-drafted intermediate
ground truth. Every relationship triple's `(subject_class, predicate,
object_class)` combination was checked against a real DR relationship
schema before being included.

The text also contains one explicit negation -- the Regional Operations
Manager is assigned to the Dispatcher role, **not** to the Field Technician
role -- captured as an `excluded` triple in `expected.json` rather than a
positive one, so an extractor that over-generates the wrong assignment is
penalized rather than credited.

## Distractors

`distractors.json` contains two near-misses: the Field Technician role
performing Work Order Fulfillment (the text assigns that process to the
Dispatcher role; Field Technician performs Route Optimization instead), and
the Regional Operations Manager "serving" the Dispatcher role (the text
states the reverse assignment direction, `assigned-to`, not `serves`).
