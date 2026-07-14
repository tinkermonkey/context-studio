# Arxiv Kubernetes Energy Monitoring Fixture (DR-relabeled)

**Source:** Arxiv-style research-paper abstract about process-level energy attribution for Nextflow workflows on Kubernetes (Nf-PEAK) (specific paper/authors not attributed in the source fixture).
**Promoted from:** `fixture_kubernetes_energy_monitoring.json`
**License:** Educational use, fair use for testing
**Curator:** Human-reviewed relabel against the DR ontology (see `../LEGACY_CORPUS_DISPOSITION.md`).

## Overview
Relabeled from free-form GT to a **DR-native ground truth** (`ontology_id:
dr_spec`). Every triple is spec-valid: `is_a` groundings to real DR/ArchiMate
classes + relationships using DR predicates the spec defines between those
classes.

## Modeling notes
- `Nextflow`/`Nf-PEAK`/`Kepler`→`application.applicationcomponent`,
  `Kubernetes`/`RAPL Counter`→`technology.systemsoftware`,
  `Node-Level Energy`→`application.dataobject`,
  `Scientific Workflow`→`application.applicationprocess`,
  `Workflow Pod`→`technology.node`.
- Relationships (all spec-valid): `systemsoftware --serves--> applicationcomponent`
  (Kubernetes serves Nextflow; RAPL serves Nf-PEAK),
  `applicationcomponent --accesses--> dataobject` (Nf-PEAK accesses the
  node-level energy data).
- `excluded`: `RAPL Counter --serves--> Scientific Workflow` — text-contradicted
  (RAPL reports only node-level energy; task-level attribution is the gap
  Nf-PEAK fills).
- Re-skim before treating as a hard accept/reject signal.
