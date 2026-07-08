# SME Fixture: Waypoint Navigation Flows

**Source:** Originally authored navigation-map prose for "Waypoint," a
plausible field-service scheduling and dispatch platform (fictional product,
written in the register of a typical navigation/IA specification document).
**Wave:** 2 -- upper-layer SME-authored scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §6, #1109 Phase 6).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** navigation (route, navigationflow, flowstep,
navigationguard, guardcondition), with incidental ux/business/motivation
touches (view, businessprocess, requirement, outcome) where the navigation
layer's own relationship schemas cross into those layers (e.g.
`navigation.route.maps-to.ux.view`).

## Overview

`expected.json` was hand-adjudicated directly against the Wave 0 DR
ontology's classes and relationship types -- no LLM-drafted intermediate
ground truth. Every relationship triple's `(subject_class, predicate,
object_class)` combination was checked against a real DR relationship
schema before being included.

## Distractors

`distractors.json` contains two near-misses: the Authenticated Technician
Guard protecting the Complete Job Route (the text says it protects the Job
Detail Route specifically), and the Technician Route mapping to the Job
Detail view (the text states that relationship for the Job Detail Route, not
the Technician Route).
