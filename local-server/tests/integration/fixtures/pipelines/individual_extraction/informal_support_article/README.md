# Informal Fixture: Waypoint Help Center Article

**Source:** Originally authored customer-support-knowledge-base prose for
"Waypoint," the same fictional field-service scheduling and dispatch
platform used by the Wave 2/3 SME corpus (fictional product, written in the
register of a help-center FAQ article a support agent links a confused
customer to -- never written with an ontology or architecture model in
mind).
**Wave:** 4 -- informal/incidental prose scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §8, #1109 Phase 8).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** incidental data-store (database, retentionpolicy) touches
-- backend retention mechanics explained to an end user in plain language.

## Overview

Ground truth was hand-adjudicated directly against this scenario's own
text, per the prose-only sourcing rule (design doc §3). Job Event Store is
the same proper noun used in Wave 3's `sme_waypoint_tech_database_selection`
scenario and Wave 4's `informal_marketing_copy` scenario -- it grounds
consistently across every register it appears in. "90-Day Retention
Policy" is a support-article-appropriate proper noun this document commits
to (a help article naming a specific numbered policy is realistic even in
casual prose), unlike Wave 3's "Ninety-Day Job Event Retention Policy,"
which is a distinct, independently-named individual belonging only to that
scenario's own text.

## Distractors

`distractors.json` contains three near-misses: the 90-Day Retention Policy
"governing" the Job Event Store directly (no DR relationship schema
supports `data-store.retentionpolicy.governs.data-store.database` -- only
`.governs.collection` and `.governs.namespace` exist, matching Wave 3's own
discipline of governing a `Collection`, never a `Database`, directly); the
generic lowercase phrase "cold storage" reified as its own database
individual (see Findings); and "regional operations manager" reified as a
`business.businessactor` individual (see Findings).

## Findings

- **A formally-named architecture element appears in this register only as
  described behavior, not as a named entity.** Wave 3's engineering-note
  prose names a specific retention-policy individual and states exactly
  which collection it governs. This support article describes the *same*
  underlying mechanism (age out records after ninety days, archive rather
  than delete) but, in its first two mentions, only as a policy customers
  can be told about -- the fixture text was written to still commit to one
  proper noun ("90-Day Retention Policy") because that register choice
  (support articles genuinely do name specific numbered policies) is
  realistic; a more purely narrative support article that only ever said
  "this is expected behavior after ninety days" would leave zero
  extractable individuals for this concept at all, which is worth noting as
  the more pessimistic but equally plausible version of this same document.
- **Generic role and location references stay generic across the whole
  register, not just this document.** "regional operations manager" and
  "cold storage" are both lowercase, common-noun-style references here,
  contrasting directly with Wave 2's capitalized "Regional Operations
  Manager" business actor and Wave 3's capitalized "Cold Storage Archival
  Service" technology service. A support article writing for a broad
  audience has no reason to capitalize an internal role or an
  infrastructure detail the customer will never interact with directly --
  which is exactly the kind of register-driven signal (capitalization,
  specificity of reference) the extraction pipeline cannot rely on for
  informal prose the way it safely could for the SME-authored waves.
- **The database-to-retention-policy relationship itself has no direct
  schema path**, matching Wave 3's own discipline (see Distractors) --
  this document doesn't introduce a new gap here so much as confirm that
  the same schema-shape constraint holds across registers.
