# Arxiv CRDT Networks Fixture (DR-relabeled)

**Source:** Arxiv-style research-paper abstract about relay-based synchronization of CRDTs in opportunistic networks (specific paper/authors not attributed in the source fixture).
**Promoted from:** `fixture_crdt_networks_paper.json`
**License:** Educational use, fair use for testing
**Curator:** Human-reviewed relabel against the DR ontology (see `../LEGACY_CORPUS_DISPOSITION.md`).

## Overview
Relabeled from free-form GT to a **DR-native ground truth** (`ontology_id:
dr_spec`). Every triple is spec-valid: `is_a` groundings to real DR/ArchiMate
classes + relationships using DR predicates the spec defines between those
classes.

## Modeling notes
- `Opportunistic Network`→`technology.communicationnetwork`,
  `Mobile Device`→`technology.device`, `CRDT`/`Replica`→`application.dataobject`,
  `Anti-Entropy Algorithm`→`application.applicationfunction`.
- Relationships (all spec-valid): `communicationnetwork --serves--> device`,
  `applicationfunction --accesses--> dataobject` (the algorithm synchronizes the
  replicas), `dataobject --realizes--> dataobject` (a replica realizes the CRDT
  type).
- Relations with no DR edge for their class pair were intentionally omitted
  (e.g. mobile-relay → convergence, CRDT → opportunistic-network).
- `excluded`: a wrong-direction `serves` (device → network) — DR only defines
  `serves` network→device.
- Re-skim before treating as a hard accept/reject signal.
