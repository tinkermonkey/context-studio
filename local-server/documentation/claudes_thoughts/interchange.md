# Data Interchange: GraphML, SKOS, and OWL Adapters

This document describes the data interchange formats supported by Context Studio and the manual testing procedures for validation.

## Supported Formats

### SKOS (Simple Knowledge Organization System)

SKOS is an RDF-based format for representing taxonomies, concept schemes, and class hierarchies. It's useful for interoperability with semantic web tools and vocabularies.

**Supported scopes:**
- whole_graph: All taxonomies, concept schemes, and classes
- taxonomy: Single taxonomy and its descendants
- scheme: Single concept scheme and its classes
- entity_set: Specific entities by ID

### OWL (Web Ontology Language)

OWL is the most expressive RDF-based format, designed for full ontology definition. It represents all entity types including individuals and relationships with semantic constraints.

**Exported entities:**
- Taxonomy nodes (as `skos:ConceptScheme`)
- ConceptScheme nodes (as `skos:ConceptScheme` with `dct:isPartOf` parent)
- Class nodes (as `owl:Class`)
- Individual nodes (as `owl:NamedIndividual`)
- PropertyDefinition nodes (as `owl:ObjectProperty`)
- Relationship edges (as RDF triples using property URIs)

**Data encoding:**
- Entity attributes are stored as RDF properties (rdfs:label, rdfs:comment, etc.)
- external_references are encoded using `owl:sameAs` for entity identity
- Multi-class Individual membership is preserved in order using indexed predicates (LOCAL:hasClass_0, LOCAL:hasClass_1, etc.)

**Supported scopes:**
- whole_graph: All entities and relationships
- taxonomy: Single taxonomy with descendants
- scheme: Single concept scheme with classes
- entity_set: Specific entities by ID

### GraphML (Graph Markup Language)

GraphML serializes the populated ontology graph for visualization tools such as Cytoscape, Gephi, yEd, and Neo4j. Unlike SKOS, GraphML preserves instance data (Individuals) and supports directed relationships between any entities.

**Exported entities:**
- Taxonomy nodes (with kind="taxonomy")
- ConceptScheme nodes (with kind="concept_scheme")
- Class nodes (with kind="class")
- Individual nodes (with kind="individual")
- PropertyDefinition nodes (with kind="property_definition")
- Relationship edges (with kind="relationship")

**Exported structural edges:**
- has_scheme: Taxonomy → ConceptScheme
- has_class: ConceptScheme → Class
- parent_class: Class → Parent Class
- class_membership: Individual → Class (with cs:class_order attribute for multi-class ordering)

**Data encoding:**
- Entity attributes are stored as `<data>` elements with namespaced keys (cs:title, cs:description, etc.)
- external_references are JSON-encoded in a reserved cs:external_references data element
- Layout coordinates (x, y) are ignored on import (let the visualization tool decide)

**Supported scopes:**
- whole_graph: All entities and relationships
- taxonomy: Single taxonomy with descendants
- scheme: Single concept scheme with classes
- entity_set: Specific entities by ID

## Manual External-Tool Smoke Test

This test validates that GraphML exports can be consumed by external visualization tools and re-imported without data loss.

### Procedure

1. **Export a graph from Context Studio:**
   ```bash
   # Using the GraphML adapter to export the whole graph
   curl -X POST http://localhost:8000/api/ontology/export \
     -H "Content-Type: application/json" \
     -d '{"format": "graphml", "scope": "whole_graph"}' \
     > /tmp/context_studio.graphml
   ```

2. **Open in a visualization tool:**
   - **Cytoscape:** File → Open → select `/tmp/context_studio.graphml`
   - **Gephi:** File → Open → select `/tmp/context_studio.graphml`
   - **yEd:** File → Open → select `/tmp/context_studio.graphml`
   - **Neo4j Desktop:** Create a new database, import via the GraphML importer

3. **Verify visualization:**
   - All entities appear as nodes with their titles
   - Relationships and parent-child edges appear as directed edges
   - Multi-class Individuals have multiple edges to their parent classes (with order preserved)
   - Entities with external references are properly labeled

4. **Save from the external tool:**
   - In Cytoscape: File → Save → save as graphml (coordinates will be auto-added by the tool)
   - In Gephi: File → Save → graphml format
   - In yEd: File → Save → graphml format

5. **Re-import into Context Studio:**
   ```bash
   # Using the GraphML adapter to import the modified graph
   curl -X POST http://localhost:8000/api/ontology/import \
     -H "Content-Type: application/json" \
     -d '{"format": "graphml", "file": "/tmp/context_studio.graphml"}' \
   ```

6. **Verify round-trip integrity:**
   - Entity titles, descriptions, and external references are preserved
   - Class hierarchies (parent_class relationships) are preserved
   - Individual multi-class memberships and ordering are preserved
   - Layout coordinates added by the external tool are silently ignored
   - No warnings about missing or corrupted data (except for unknown data keys, which are acceptable)

### Expected Results

- **Entity count:** Same as original export
- **External references:** All preserved (no loss of source/identifier pairs)
- **Hierarchies:** Parent-child relationships intact
- **Individual ordering:** Multi-class individuals maintain class membership order
- **Warnings:** Only for unhandled data keys (e.g., custom tool-specific attributes)

### Troubleshooting

- **Missing nodes/edges:** Verify the external tool properly parsed the GraphML schema
- **Corrupted external references:** Check that the cs:external_references JSON is valid UTF-8
- **Ordering issues:** Verify cs:class_order attributes are present on class_membership edges
- **Tool-specific errors:** Layout coordinates are safe to ignore; the importer strips them automatically

## Programmatic Usage

### Export

```python
from adapters.interchange.graphml import GraphMLSerializer
from domain.interchange.value_objects import SerializationScope, SerializationScopeType

serializer = GraphMLSerializer(ontology_repo)
scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
graphml_bytes = serializer.serialize(scope)

with open("output.graphml", "wb") as f:
    f.write(graphml_bytes)
```

### Import

```python
from adapters.interchange.graphml import GraphMLDeserializer

deserializer = GraphMLDeserializer(ontology_repo)
with open("input.graphml", "rb") as f:
    file_contents = f.read()

plan = deserializer.deserialize(file_contents, dry_run=True)

# Review conflicts in plan.conflicts
# Then commit the import
plan = deserializer.deserialize(file_contents, dry_run=False)
```
