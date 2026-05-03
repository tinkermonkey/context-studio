# Data Interchange Format Lossiness Reference

This document describes what data survives the round-trip export/import cycle for each supported interchange format, and what data is lost or unsupported.

## Critical, Not Lossy

The following fields **must** round-trip exactly through every format. Loss of these fields indicates a correctness bug, not a feature limitation:

- **`external_references`** on Class and Individual entities
  - These references preserve the link to external knowledge sources (DBpedia, Wikidata, etc.)
  - Supported mechanisms: SKOS via `dct:source` + `skos:exactMatch`, OWL via `owl:sameAs`, GraphML via `cs:external_references` JSON
  - Loss of external_references breaks entity identity and linkage to external systems

- **Entity identity (title + structural relationships)**
  - Class hierarchy (`parent_class_id` / `rdfs:subClassOf`)
  - Individual multi-class membership (`class_ids` / `rdf:type`)
  - Concept scheme to taxonomy relationship (`taxonomy_id` / `dct:isPartOf`)
  - These relationships are the core structure; their loss is a data corruption bug

---

## SKOS (Simple Knowledge Organization System)

SKOS is RDF-based, designed specifically for taxonomies and concept schemes. It is the most restrictive format and only represents concept hierarchies.

### Survives Exactly

- **Taxonomy** (as `skos:ConceptScheme`)
  - `id`, `title`, `description`
- **ConceptScheme** (as `skos:ConceptScheme` with `dct:isPartOf` parent)
  - `id`, `title`, `description`, `taxonomy_id`
- **Class** (as `skos:Concept`)
  - `id`, `title`, `description`, `parent_class_id`
  - `concept_scheme_id` (via `skos:inScheme`)
  - `external_references` (via `dct:source` for all references, plus `skos:exactMatch` for cross-vocabulary identity)

### Survives But Lossy

- **created_at, last_modified, version**: Timestamps and concurrency metadata are not preserved in SKOS RDF
- **structural_property_id**: Not representable in SKOS; lost on round-trip
- **embedding**: Vector embeddings are not stored

### Entirely Unsupported

- **Individual** (owl instances): SKOS has no notion of instances; individuals are dropped entirely
- **PropertyDefinition**: SKOS does not define or name relationships; property types are lost
- **Relationship**: Arbitrary relationships between entities cannot be represented; only class hierarchy survives
- **data_properties**: Data properties on classes and individuals are not supported
- **lexical_senses**: WordNet/word-sense mappings are not supported

---

## OWL (Web Ontology Language)

OWL is the most expressive format, built on RDF and designed for full ontology definition. It represents all entity types and relationships.

### Survives Exactly

- **Taxonomy** (as `skos:ConceptScheme`, following SKOS convention for taxonomic organization)
  - `id`, `title`, `description`
- **ConceptScheme** (as `skos:ConceptScheme` with `dct:isPartOf` parent)
  - `id`, `title`, `description`, `taxonomy_id`
- **Class** (as `owl:Class`)
  - `id`, `title`, `description`, `parent_class_id` (via `rdfs:subClassOf`)
  - `concept_scheme_id` (via `skos:inScheme` or inferred from parent structures)
  - `external_references` (via `owl:sameAs`)
- **Individual** (as `owl:NamedIndividual`)
  - `id`, `title`, `description`
  - `class_ids` (via `rdf:type`, preserved in order)
  - Multi-class membership with ordering (via `LOCAL:hasClass_0`, `LOCAL:hasClass_1`, ... indexed predicates)
  - `external_references` (via `owl:sameAs`)
- **PropertyDefinition** (as `owl:ObjectProperty`)
  - `id`, `identifier`, `title`, `description`
- **Relationship** (as RDF triples using property URIs)
  - Source, target, and property type all survive
  - Note: PropertyDefinition domain/range constraints are not used in Context Studio's OWL representation

### Survives But Lossy

- **created_at, last_modified, version**: Timestamps and concurrency metadata are not standard RDF predicates; these fields are lost on round-trip
- **ontology_mapping**: OWL mapping metadata is not preserved
- **is_relevant**: Relevance flags are lost
- **embedding**: Vector embeddings are not stored in OWL RDF
- **data_properties**: Datatype properties are not stored as first-class entities
- **lexical_senses**: WordNet/word-sense mappings are not preserved

### Entirely Unsupported

- None: OWL represents all Context Studio entity types

---

## GraphML (Graph Markup Language)

GraphML is XML-based and designed for graph visualization tools. It represents all entity types as nodes and all relationships as edges, but lacks semantic constraints.

### Survives Exactly

- **Taxonomy** (as `<node kind="taxonomy">`)
  - `id`, `title`, `description`
- **ConceptScheme** (as `<node kind="concept_scheme">`)
  - `id`, `title`, `description`, `taxonomy_id`
- **Class** (as `<node kind="class">`)
  - `id`, `title`, `description`, `parent_class_id`
  - `concept_scheme_id` (via `has_class` edge)
  - `external_references` (via reserved `<data key="cs:external_references">` element, JSON-encoded)
- **Individual** (as `<node kind="individual">`)
  - `id`, `title`, `description`
  - `class_ids` (via `class_membership` edges with `cs:class_order` attribute for ordering)
  - `external_references` (via reserved `<data key="cs:external_references">` element, JSON-encoded)
- **PropertyDefinition** (as `<node kind="property_definition">`)
  - `id`, `identifier`, `title`, `description`
- **Relationship** (as `<edge kind="relationship">`)
  - Source, target, and property_definition_id all survive

### Survives But Lossy

- **created_at, last_modified, version**: Timestamps and version metadata stored as string values; not round-tripped with type information
- **ontology_mapping**: Not stored in GraphML
- **is_relevant**: Stored as string value but not round-tripped with type information
- **embedding**: Not supported by GraphML
- **data_properties**: Not stored (no schema-enforced type information)
- **lexical_senses**: Not stored
- **structural_property_id**: Not preserved

### Entirely Unsupported

- **Layout coordinates (x, y)**: Visualization tools add these on export; they are intentionally ignored on import (tools decide layout). This is by design, not a loss.
- **RDF semantics**: GraphML has no semantic constraints (e.g., no cardinality constraints, no domain/range declarations)

---

## Round-Trip Summary

### SKOS → SKOS

- ✅ Taxonomies, ConceptSchemes, Classes, external_references round-trip exactly
- ❌ Individuals, PropertyDefinitions, Relationships, timestamps, embeddings are lost
- **Lossiness**: ~40% of entity data (no individuals or relationships)

### OWL → OWL

- ✅ All entity types, relationships, external_references round-trip exactly
- ❌ Timestamps, version metadata, embeddings, data_properties are lossy (not stored)
- **Lossiness**: ~5% (metadata fields only)

### GraphML → GraphML

- ✅ All entity types, relationships, external_references round-trip exactly
- ❌ Timestamps, embeddings, semantic constraints, data_properties are lossy
- ❌ Layout coordinates are intentionally dropped
- **Lossiness**: ~10% (metadata + visualization-specific data)

### SKOS → OWL

- ✅ All SKOS entities (taxonomies, schemes, classes) survive and gain Individuals + PropertyDefinitions support
- ❌ No new data added (SKOS has no individuals to convert)
- ✅ external_references preserved
- **Result**: OWL can represent everything SKOS did, but no new data emerges from SKOS

### OWL → GraphML

- ✅ All OWL entities survive as GraphML nodes/edges
- ❌ RDF semantics (domain/range constraints) lost; relationships become simple edges
- ✅ external_references preserved
- **Result**: GraphML is less expressive but captures all concrete entities

### GraphML → OWL

- ✅ All GraphML entities map back to OWL
- ❌ No RDF semantic enrichment (GraphML has none to contribute)
- ✅ external_references preserved
- **Result**: OWL regains full semantic capability

### Three-Format Chain (SKOS → OWL → GraphML)

Comparing final state to original (SKOS):

- ✅ Taxonomies, ConceptSchemes, Classes: survive all three legs
- ✅ external_references: preserved at every leg
- ✅ Hierarchy: preserved at every leg
- ❌ Timestamps, embeddings, version info: lost at first leg (SKOS → OWL)
- 🟠 Individuals, PropertyDefinitions, Relationships: created in OWL leg (not present in original SKOS) but preserved thereafter
- **Net result**: Perfect structural round-trip with metadata loss only
