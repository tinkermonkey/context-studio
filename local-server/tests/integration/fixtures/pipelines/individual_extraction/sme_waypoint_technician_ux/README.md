# SME Fixture: Waypoint Technician UX

**Source:** Originally authored UX-spec-excerpt prose for "Waypoint," a
plausible field-service scheduling and dispatch platform (fictional product,
written in the register of a typical UX specification document).
**Wave:** 2 -- upper-layer SME-authored scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §6, #1109 Phase 6).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** ux (uxapplication, uxspec, view, componentinstance,
actioncomponent, subview, errorconfig), with incidental business/motivation
touches (businessevent, businessrole, requirement) where the ux layer's own
relationship schemas cross into those layers (e.g.
`ux.actioncomponent.triggers.business.businessevent`).

## Overview

`expected.json` was hand-adjudicated directly against the Wave 0 DR
ontology's classes and relationship types -- no LLM-drafted intermediate
ground truth. Every relationship triple's `(subject_class, predicate,
object_class)` combination was checked against a real DR relationship
schema before being included.

## Distractors

`distractors.json` contains two near-misses: the Complete Job button
navigating to the Job Detail view (the text says the Complete Job button
*triggers a business event*, not that it navigates anywhere -- it is the
separate View Job button that navigates to Job Detail), and the Today's
Jobs view serving the Field Technician business role (the text states that
relationship for the Job Detail view, not Today's Jobs).
