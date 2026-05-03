"""
OWL adapter for exporting and importing ontology data.

Implements OntologySerializer and OntologyDeserializer ports to handle
OWL (Web Ontology Language) RDF-based interchange format.

Mapping strategy:
- Taxonomy → skos:ConceptScheme (OWL uses SKOS for taxonomic organization)
- ConceptScheme → skos:ConceptScheme (with parent reference via dct:isPartOf)
- Class → owl:Class (with rdfs:subClassOf for hierarchy)
- Individual → owl:NamedIndividual (with rdf:type indicating class membership)
- PropertyDefinition → owl:ObjectProperty or owl:DatatypeProperty (inferred from usage)
- Relationship → RDF triple using the property predicate
- external_references → owl:sameAs (for entity identity) and dct:source (for references)
"""

from __future__ import annotations

import hashlib
from typing import Optional, Dict, Any

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS
from rdflib.term import Node

from domain.interchange.ports import OntologySerializer, OntologyDeserializer
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    ImportPlan,
    ImportConflict,
    MatchKind,
    ResolutionKind,
)
from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
    PropertyDefinition,
    Relationship,
)
from domain.ontology.value_objects import ExternalReference


# RDF Namespaces
OWL = Namespace("http://www.w3.org/2002/07/owl#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DCT = Namespace("http://purl.org/dc/terms/")
LOCAL = Namespace("http://context-studio.local/ontology/")


class OWLSerializer(OntologySerializer):
    """
    Serializes ontology entities to OWL RDF format.

    OWL provides more expressive power than SKOS for representing class hierarchies,
    individuals, and property definitions. Unlike SKOS (concepts), OWL uses owl:Class
    for type definitions and owl:NamedIndividual for instances.

    Supports multiple serialization scopes:
    - whole_graph: all taxonomies, concept schemes, classes, individuals, and properties
    - taxonomy: single taxonomy and its descendants
    - scheme: single concept scheme and its classes
    - entity_set: specified entities only
    """

    def __init__(
        self,
        ontology_repo,
        format: str = "turtle",
    ):
        """
        Initialize the OWL serializer.

        Args:
            ontology_repo: Repository for querying ontology entities
            format: Output format ('turtle', 'xml', 'json-ld')
        """
        self.ontology_repo = ontology_repo
        self.format = format
        self.graph: Optional[Graph] = None

    def serialize(self, scope: SerializationScope) -> bytes:
        """
        Serialize the ontology according to the given scope.

        Args:
            scope: Describes what to serialize

        Returns:
            Serialized ontology as bytes in OWL RDF format

        Raises:
            ValueError: If the scope is invalid
            RuntimeError: If serialization fails
        """
        scope.validate()

        self.graph = Graph()
        assert self.graph is not None
        self.graph.bind("owl", OWL)
        self.graph.bind("skos", SKOS)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("dct", DCT)
        self.graph.bind("local", LOCAL)

        try:
            match scope.scope_type:
                case SerializationScopeType.WHOLE_GRAPH:
                    self._serialize_whole_graph()
                case SerializationScopeType.TAXONOMY:
                    assert scope.taxonomy_id is not None
                    self._serialize_taxonomy(scope.taxonomy_id)
                case SerializationScopeType.SCHEME:
                    assert scope.scheme_id is not None
                    self._serialize_scheme(scope.scheme_id)
                case SerializationScopeType.ENTITY_SET:
                    self._serialize_entity_set(scope.entity_ids)

            format_map = {
                "turtle": "turtle",
                "xml": "xml",
                "json-ld": "json-ld",
            }
            format_str = format_map.get(self.format, "turtle")
            result = self.graph.serialize(format=format_str)
            if isinstance(result, str):
                return result.encode('utf-8')
            return result
        except Exception as e:
            raise RuntimeError(f"OWL serialization failed: {str(e)}") from e

    def _serialize_whole_graph(self) -> None:
        """Serialize all taxonomies, concept schemes, classes, individuals, and properties."""
        # Add all property definitions first (referenced by relationships)
        properties = self.ontology_repo.list_property_definitions()
        for prop in properties:
            self._add_property_to_graph(prop)

        # Add all taxonomies and their descendants
        taxonomies = self.ontology_repo.list_taxonomies()
        for taxonomy in taxonomies:
            self._add_taxonomy_to_graph(taxonomy)

        # Add all individuals
        individuals = self.ontology_repo.list_individuals()
        for individual in individuals:
            self._add_individual_to_graph(individual)

        # Add all relationships
        relationships = self.ontology_repo.list_relationships()
        for relationship in relationships:
            self._add_relationship_to_graph(relationship)

    def _serialize_taxonomy(self, taxonomy_id: str) -> None:
        """Serialize a single taxonomy and its descendants."""
        taxonomy = self.ontology_repo.get_taxonomy(taxonomy_id)
        if not taxonomy:
            raise ValueError(f"Taxonomy not found: {taxonomy_id}")

        self._add_taxonomy_to_graph(taxonomy)

    def _serialize_scheme(self, scheme_id: str) -> None:
        """Serialize a single concept scheme and its classes."""
        scheme = self.ontology_repo.get_concept_scheme(scheme_id)
        if not scheme:
            raise ValueError(f"Concept scheme not found: {scheme_id}")

        self._add_concept_scheme_to_graph(scheme, include_parent_taxonomy=True)

    def _serialize_entity_set(self, entity_ids: Optional[tuple[str, ...]]) -> None:
        """Serialize a specified set of entities."""
        if not entity_ids:
            return

        for entity_id in entity_ids:
            # Try each entity type
            taxonomy = self.ontology_repo.get_taxonomy(entity_id)
            if taxonomy:
                self._add_taxonomy_to_graph(taxonomy)
                continue

            scheme = self.ontology_repo.get_concept_scheme(entity_id)
            if scheme:
                self._add_concept_scheme_to_graph(scheme, include_parent_taxonomy=False)
                continue

            class_entity = self.ontology_repo.get_class(entity_id)
            if class_entity:
                self._add_class_to_graph(class_entity)
                continue

            individual = self.ontology_repo.get_individual(entity_id)
            if individual:
                self._add_individual_to_graph(individual)
                continue

            prop = self.ontology_repo.get_property_definition(entity_id)
            if prop:
                self._add_property_to_graph(prop)

    def _add_taxonomy_to_graph(self, taxonomy: Taxonomy) -> None:
        """Add a taxonomy and its descendants to the graph."""
        assert self.graph is not None
        tax_uri = self._entity_uri(taxonomy.id)
        self.graph.add((tax_uri, RDF.type, SKOS.ConceptScheme))
        self.graph.add((tax_uri, SKOS.prefLabel, Literal(taxonomy.title)))
        if taxonomy.description:
            self.graph.add((tax_uri, SKOS.definition, Literal(taxonomy.description)))

        # Add concept schemes that belong to this taxonomy
        schemes = self.ontology_repo.list_concept_schemes(taxonomy_id=taxonomy.id)
        for scheme in schemes:
            self._add_concept_scheme_to_graph(scheme, include_parent_taxonomy=True)

    def _add_concept_scheme_to_graph(
        self, scheme: ConceptScheme, include_parent_taxonomy: bool = True
    ) -> None:
        """Add a concept scheme and its classes to the graph."""
        assert self.graph is not None
        scheme_uri = self._entity_uri(scheme.id)
        self.graph.add((scheme_uri, RDF.type, SKOS.ConceptScheme))
        self.graph.add((scheme_uri, SKOS.prefLabel, Literal(scheme.title)))
        if scheme.description:
            self.graph.add((scheme_uri, SKOS.definition, Literal(scheme.description)))

        if include_parent_taxonomy:
            taxonomy_uri = self._entity_uri(scheme.taxonomy_id)
            self.graph.add((scheme_uri, DCT.isPartOf, taxonomy_uri))

        # Add classes that belong to this scheme
        classes = self.ontology_repo.list_classes(concept_scheme_id=scheme.id)
        for class_entity in classes:
            self._add_class_to_graph(class_entity)

    def _add_class_to_graph(self, class_entity: Class) -> None:
        """Add a class to the graph."""
        assert self.graph is not None
        class_uri = self._entity_uri(class_entity.id)
        self.graph.add((class_uri, RDF.type, OWL.Class))
        self.graph.add((class_uri, RDFS.label, Literal(class_entity.title)))
        if class_entity.description:
            self.graph.add((class_uri, RDFS.comment, Literal(class_entity.description)))

        # Add parent class relationship
        if class_entity.parent_class_id:
            parent_uri = self._entity_uri(class_entity.parent_class_id)
            self.graph.add((class_uri, RDFS.subClassOf, parent_uri))

        # Add external references
        for ext_ref in class_entity.external_references:
            self._add_external_reference_to_graph(class_uri, ext_ref)

    def _add_individual_to_graph(self, individual: Individual) -> None:
        """Add an individual to the graph."""
        assert self.graph is not None
        ind_uri = self._entity_uri(individual.id)
        self.graph.add((ind_uri, RDF.type, OWL.NamedIndividual))
        self.graph.add((ind_uri, RDFS.label, Literal(individual.title)))
        if individual.description:
            self.graph.add((ind_uri, RDFS.comment, Literal(individual.description)))

        # Add class memberships
        for i, class_id in enumerate(individual.class_ids):
            class_uri = self._entity_uri(class_id)
            self.graph.add((ind_uri, RDF.type, class_uri))
            # Store class order as a triple for multi-class ordering
            order_uri = URIRef(str(ind_uri) + f"#class_order_{i}")
            self.graph.add((ind_uri, LOCAL.classOrder, Literal(i)))

        # Add external references
        for ext_ref in individual.external_references:
            self._add_external_reference_to_graph(ind_uri, ext_ref)

    def _add_property_to_graph(self, prop: PropertyDefinition) -> None:
        """Add a property definition to the graph."""
        assert self.graph is not None
        prop_uri = self._entity_uri(prop.id)
        self.graph.add((prop_uri, RDF.type, OWL.ObjectProperty))
        self.graph.add((prop_uri, RDFS.label, Literal(prop.title)))
        self.graph.add((prop_uri, RDFS.isDefinedBy, LOCAL.ontology))
        if prop.description:
            self.graph.add((prop_uri, RDFS.comment, Literal(prop.description)))

    def _add_relationship_to_graph(self, relationship: Relationship) -> None:
        """Add a relationship to the graph."""
        assert self.graph is not None
        source_uri = self._entity_uri(relationship.source_id)
        target_uri = self._entity_uri(relationship.target_id)
        prop_uri = self._entity_uri(relationship.property_definition_id)

        self.graph.add((source_uri, prop_uri, target_uri))

    def _add_external_reference_to_graph(self, entity_uri: URIRef, ext_ref: ExternalReference) -> None:
        """Add an external reference to an entity."""
        assert self.graph is not None
        if ext_ref.uri:
            # Use owl:sameAs for exact matches to external entities
            self.graph.add((entity_uri, OWL.sameAs, URIRef(ext_ref.uri)))
        # Also add dct:source for tracking the source
        source_literal = Literal(f"{ext_ref.source}:{ext_ref.identifier}")
        self.graph.add((entity_uri, DCT.source, source_literal))

    def _entity_uri(self, entity_id: str) -> URIRef:
        """Convert an entity ID to a URI."""
        return LOCAL[entity_id]


class OWLDeserializer(OntologyDeserializer):
    """
    Deserializes ontology data from OWL RDF format.

    Reverse mapping:
    - skos:ConceptScheme → Taxonomy or ConceptScheme (discriminated by dct:isPartOf)
    - owl:Class → Class
    - owl:NamedIndividual → Individual
    - owl:ObjectProperty → PropertyDefinition
    - owl:sameAs / dct:source → external_references
    - rdfs:subClassOf → parent_class_id
    - rdf:type (when object is owl:NamedIndividual) → class membership
    """

    def __init__(self, ontology_repo, interchange_repo=None):
        """
        Initialize the OWL deserializer.

        Args:
            ontology_repo: Repository for persisting ontology entities
            interchange_repo: Optional repository for tracking imports
        """
        self.ontology_repo = ontology_repo
        self.interchange_repo = interchange_repo
        self.graph: Optional[Graph] = None
        self._entity_map: Dict[str, str] = {}  # URI -> local entity ID
        self.incoming_entities: Dict[str, Dict[str, Any]] = {}

    def deserialize(
        self, source: bytes | str, dry_run: bool = True
    ) -> ImportPlan:
        """
        Deserialize OWL data and produce an import plan.

        Args:
            source: Serialized OWL as bytes or string
            dry_run: If True, returns ImportPlan without persisting (no-op for deserializers)

        Returns:
            ImportPlan describing what the import would/did do
        """
        try:
            import uuid as uuid_module

            self.graph = Graph()
            self.incoming_entities = {}
            self._entity_map = {}

            if isinstance(source, bytes):
                self.graph.parse(data=source, format="turtle")
            else:
                self.graph.parse(data=source, format="turtle")

            # Process concept schemes first (taxonomies/conceptschemes)
            for scheme_uri in self.graph.subjects(RDF.type, SKOS.ConceptScheme):
                self._process_concept_scheme_entity(scheme_uri)

            # Process classes
            for class_uri in self.graph.subjects(RDF.type, OWL.Class):
                self._process_class_entity(class_uri)

            # Process individuals
            for ind_uri in self.graph.subjects(RDF.type, OWL.NamedIndividual):
                self._process_individual_entity(ind_uri)

            # Compute source hash
            if isinstance(source, str):
                source_bytes = source.encode('utf-8')
            else:
                source_bytes = source
            source_hash = hashlib.sha256(source_bytes).hexdigest()

            # Create import plan
            plan = ImportPlan(
                conflicts=[],
                new_entity_count=len(self.incoming_entities),
                import_run_id=None,
                source_hash=source_hash,
            )

            return plan
        except Exception as e:
            raise RuntimeError(f"OWL deserialization failed: {str(e)}") from e

    def _process_concept_scheme_entity(self, scheme_uri: Node) -> None:
        """Process a SKOS ConceptScheme (Taxonomy or ConceptScheme)."""
        import uuid

        title = self._get_label(scheme_uri)
        if not title:
            return

        description = self._get_first_string(scheme_uri, RDFS.comment)
        entity_id = str(uuid.uuid4())

        # Check if it has a parent taxonomy (dct:isPartOf)
        parent_taxonomy_uri = self._get_first_object(scheme_uri, DCT.isPartOf)

        if parent_taxonomy_uri:
            # This is a ConceptScheme
            parent_taxonomy_id = self._entity_map.get(str(parent_taxonomy_uri))
            if not parent_taxonomy_id:
                # Create parent taxonomy first
                parent_tax_id = str(uuid.uuid4())
                parent_tax_title = self._get_label(parent_taxonomy_uri) or "Imported Taxonomy"
                self.incoming_entities[parent_tax_id] = {
                    "id": parent_tax_id,
                    "title": parent_tax_title,
                    "type": "taxonomy",
                }
                self._entity_map[str(parent_taxonomy_uri)] = parent_tax_id
                parent_taxonomy_id = parent_tax_id

            self.incoming_entities[entity_id] = {
                "id": entity_id,
                "title": title,
                "description": description,
                "type": "concept_scheme",
                "taxonomy_id": parent_taxonomy_id,
            }
        else:
            # This is a Taxonomy
            self.incoming_entities[entity_id] = {
                "id": entity_id,
                "title": title,
                "description": description,
                "type": "taxonomy",
            }

        self._entity_map[str(scheme_uri)] = entity_id

    def _process_class_entity(self, class_uri: Node) -> None:
        """Process an OWL Class."""
        import uuid

        title = self._get_label(class_uri)
        if not title:
            return

        description = self._get_first_string(class_uri, RDFS.comment)
        entity_id = str(uuid.uuid4())

        # Find parent class if exists
        parent_class_uri = self._get_first_object(class_uri, RDFS.subClassOf)
        parent_class_id = None
        if parent_class_uri:
            parent_class_id = self._entity_map.get(str(parent_class_uri))

        # Get external references
        external_references = self._extract_external_references_as_dicts(class_uri)

        # Try to infer scheme from skos:inScheme
        scheme_id = None
        scheme_uri = self._get_first_object(class_uri, SKOS.inScheme)
        if scheme_uri:
            scheme_id = self._entity_map.get(str(scheme_uri))

        self.incoming_entities[entity_id] = {
            "id": entity_id,
            "title": title,
            "description": description,
            "type": "class",
            "parent_class_id": parent_class_id,
            "concept_scheme_id": scheme_id,
            "external_references": external_references,
        }
        self._entity_map[str(class_uri)] = entity_id

    def _process_individual_entity(self, ind_uri: Node) -> None:
        """Process an OWL NamedIndividual."""
        import uuid

        title = self._get_label(ind_uri)
        if not title:
            return

        description = self._get_first_string(ind_uri, RDFS.comment)
        entity_id = str(uuid.uuid4())

        # Get class memberships (rdf:type pointing to owl:Class)
        class_uris = list(self.graph.objects(ind_uri, RDF.type))
        class_ids = []
        for class_uri in class_uris:
            if str(class_uri) == str(OWL.NamedIndividual):
                continue
            class_id = self._entity_map.get(str(class_uri))
            if class_id:
                class_ids.append(class_id)

        if not class_ids:
            return

        # Get external references
        external_references = self._extract_external_references_as_dicts(ind_uri)

        self.incoming_entities[entity_id] = {
            "id": entity_id,
            "title": title,
            "description": description,
            "type": "individual",
            "class_ids": class_ids,
            "external_references": external_references,
        }
        self._entity_map[str(ind_uri)] = entity_id

    def _extract_external_references_as_dicts(self, entity_uri: Node) -> list[Dict[str, Any]]:
        """Extract external references from owl:sameAs and dct:source predicates as dicts."""
        refs = []

        # Extract owl:sameAs references
        for same_as_uri in self.graph.objects(entity_uri, OWL.sameAs):
            uri_str = str(same_as_uri)
            # Try to parse source:identifier from the URI
            if "#" in uri_str:
                source, identifier = uri_str.rsplit("#", 1)
            elif "/" in uri_str:
                parts = uri_str.rsplit("/", 1)
                source, identifier = parts[0], parts[1]
            else:
                source = uri_str
                identifier = uri_str

            refs.append({
                "source": source.split("/")[-1] if "/" in source else source,
                "identifier": identifier,
                "uri": uri_str,
            })

        # Extract dct:source references
        for source_literal in self.graph.objects(entity_uri, DCT.source):
            source_str = str(source_literal)
            if ":" in source_str:
                source, identifier = source_str.split(":", 1)
            else:
                source = "external"
                identifier = source_str

            refs.append({
                "source": source,
                "identifier": identifier,
                "uri": None,
            })

        return refs

    def _get_label(self, uri: Node) -> Optional[str]:
        """Get the label for a URI (rdfs:label or skos:prefLabel)."""
        label = self._get_first_string(uri, RDFS.label)
        if label:
            return label
        return self._get_first_string(uri, SKOS.prefLabel)

    def _get_first_string(self, uri: Node, predicate: URIRef) -> Optional[str]:
        """Get the first string value for a predicate."""
        value = self._get_first_object(uri, predicate)
        if value:
            return str(value)
        return None

    def _get_first_object(self, uri: Node, predicate: URIRef) -> Optional[Node]:
        """Get the first object for a predicate."""
        for obj in self.graph.objects(uri, predicate):
            return obj
        return None
