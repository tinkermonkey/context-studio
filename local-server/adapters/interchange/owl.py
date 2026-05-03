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
- external_references → owl:sameAs (for entity identity) with URI extraction on import
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Optional, Dict, Any, cast
from datetime import datetime, timezone

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS
from rdflib.term import Node

from utils.logger import get_logger
from domain.interchange.ports import OntologySerializer, OntologyDeserializer
from domain.interchange.entities import ImportRun, ImportRunStatus
from domain.interchange.services import ImportRunService
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    ImportPlan,
    MatchKind,
    ResolutionKind,
    SerializationFormat,
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

logger = get_logger(__name__)


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
        split_mode: bool = False,
    ):
        """
        Initialize the OWL serializer.

        Args:
            ontology_repo: Repository for querying ontology entities
            format: Output format ('turtle', 'xml', 'json-ld')
            split_mode: If True, serialize only TBox (schema) without individuals (ABox)
        """
        self.ontology_repo = ontology_repo
        self.format = format
        self.split_mode = split_mode
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
            result = cast(str | bytes, self.graph.serialize(format=format_str))
            if isinstance(result, str):
                return result.encode("utf-8")
            return result
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"OWL serialization error: {type(e).__name__}: {str(e)}")
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

        # Add all individuals and relationships only if not in split (TBox-only) mode
        if not self.split_mode:
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

            # Always check for Individual to provide accurate warning messages
            individual = self.ontology_repo.get_individual(entity_id)
            if individual:
                if self.split_mode:
                    logger.warning(f"Entity {entity_id} is an Individual, skipped in TBox-only (split) mode")
                else:
                    self._add_individual_to_graph(individual)
                continue

            prop = self.ontology_repo.get_property_definition(entity_id)
            if prop:
                self._add_property_to_graph(prop)
                continue

            logger.warning(f"Entity {entity_id} does not match any known type during OWL serialization; skipping")

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

        # Add concept scheme relationship
        if class_entity.concept_scheme_id:
            scheme_uri = self._entity_uri(class_entity.concept_scheme_id)
            self.graph.add((class_uri, SKOS.inScheme, scheme_uri))

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

        # Add class memberships in order using indexed predicates to preserve ordering
        for i, class_id in enumerate(individual.class_ids):
            class_uri = self._entity_uri(class_id)
            self.graph.add((ind_uri, RDF.type, class_uri))
            # Store class with index in predicate name (e.g., hasClass_0, hasClass_1, ...)
            # This preserves the order in RDF since each triple is unique
            indexed_predicate = LOCAL[f"hasClass_{i}"]
            self.graph.add((ind_uri, indexed_predicate, class_uri))

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

    def _add_external_reference_to_graph(
        self, entity_uri: URIRef, ext_ref: ExternalReference
    ) -> None:
        """Add an external reference to an entity using only owl:sameAs to avoid duplication."""
        assert self.graph is not None
        if ext_ref.uri:
            # Use owl:sameAs as the single source of truth for external references
            self.graph.add((entity_uri, OWL.sameAs, URIRef(ext_ref.uri)))

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
    - owl:sameAs → external_references (single source of truth)
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
        self.warnings: list[str] = []

    def deserialize(self, source: bytes | str, dry_run: bool = True, resolutions: list | None = None) -> ImportPlan:
        """
        Deserialize OWL data and produce an import plan.

        Args:
            source: Serialized OWL as bytes or string
            dry_run: If True, returns ImportPlan without persisting
            resolutions: Optional list of user-chosen resolutions to apply when committing

        Returns:
            ImportPlan describing what the import would/did do
        """
        try:
            self.graph = Graph()
            self.incoming_entities = {}
            self._entity_map = {}
            self.warnings = []

            # Ensure source is bytes for hashing
            if isinstance(source, str):
                source_bytes = source.encode("utf-8")
            else:
                source_bytes = source

            # Try to parse with auto-detection of format (RDF/XML, Turtle, JSON-LD)
            parse_error = None
            for fmt in ["xml", "turtle", "json-ld"]:
                try:
                    self.graph = Graph()  # Reset graph for each format attempt
                    self.graph.parse(data=source_bytes, format=fmt)
                    break
                except Exception as e:
                    parse_error = e
                    continue
            else:
                # All formats failed
                raise ValueError(f"Failed to parse OWL RDF in any format: {str(parse_error)}")

            # Process taxonomies first (ConceptSchemes without dct:isPartOf)
            # Then concept schemes (with dct:isPartOf) to avoid duplicate creation
            self._process_taxonomies_first()

            # Process classes
            for class_uri in self.graph.subjects(RDF.type, OWL.Class):
                self._process_class_entity(class_uri)

            # Process individuals
            for ind_uri in self.graph.subjects(RDF.type, OWL.NamedIndividual):
                self._process_individual_entity(ind_uri)

            # Process property definitions
            for prop_uri in self.graph.subjects(RDF.type, OWL.ObjectProperty):
                self._process_property_entity(prop_uri)

            # Process relationships
            self._process_relationships()

            # Compute source hash
            source_hash = hashlib.sha256(source_bytes).hexdigest()

            # If committing (not dry-run), create and persist ImportRun with resolutions
            import_run_id = None
            if not dry_run:
                # Create ImportRun with resolutions
                import_run_service = ImportRunService()
                scope = SerializationScope(
                    scope_type=SerializationScopeType.WHOLE_GRAPH
                )
                import_run = import_run_service.start_run(
                    format=SerializationFormat.OWL,
                    source_hash=source_hash,
                    scope=scope,
                    source_uri=None,
                    created_by=None,
                )

                # Record user-chosen resolutions if provided
                if resolutions:
                    for resolution_data in resolutions:
                        try:
                            match_kind = MatchKind(resolution_data.get("match_kind"))
                            resolution_kind = ResolutionKind(resolution_data.get("resolution_chosen"))
                            import_run.add_resolution(
                                match_kind=match_kind,
                                entity_id=resolution_data.get("entity_id"),
                                resolution_chosen=resolution_kind,
                            )
                        except (KeyError, ValueError) as e:
                            logger.warning(f"Invalid resolution data: {resolution_data}, error: {e}")

                # Persist the ImportRun
                if self.interchange_repo:
                    import_run = self.interchange_repo.create(import_run)
                    import_run_id = import_run.id
                else:
                    logger.warning("ImportRun created but not persisted: no interchange_repo available")

            # Create import plan
            plan = ImportPlan(
                conflicts=(),
                new_entity_count=len(self.incoming_entities),
                import_run_id=import_run_id,
                warnings=tuple(self.warnings),
                source_hash=source_hash,
            )

            return plan
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"OWL deserialization error: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"OWL deserialization failed: {str(e)}") from e

    def _process_taxonomies_first(self) -> None:
        """Process taxonomies first, then concept schemes to avoid duplicate creation."""
        if self.graph is None:
            return
        # First pass: find taxonomies (ConceptSchemes without dct:isPartOf)
        for scheme_uri in self.graph.subjects(RDF.type, SKOS.ConceptScheme):
            parent_taxonomy_uri = self._get_first_object(scheme_uri, DCT.isPartOf)
            if not parent_taxonomy_uri:
                # This is a taxonomy
                self._process_concept_scheme_entity(scheme_uri, is_taxonomy=True)

        # Second pass: find concept schemes (with dct:isPartOf)
        for scheme_uri in self.graph.subjects(RDF.type, SKOS.ConceptScheme):
            parent_taxonomy_uri = self._get_first_object(scheme_uri, DCT.isPartOf)
            if parent_taxonomy_uri:
                # This is a concept scheme
                self._process_concept_scheme_entity(scheme_uri, is_taxonomy=False)

    def _process_concept_scheme_entity(
        self, scheme_uri: Node, is_taxonomy: bool
    ) -> None:
        """Process a SKOS ConceptScheme (Taxonomy or ConceptScheme)."""
        # Skip if already processed
        if str(scheme_uri) in self._entity_map:
            return

        title = self._get_label(scheme_uri)
        if not title:
            self.warnings.append(f"ConceptScheme/Taxonomy {scheme_uri} has no label (rdfs:label or skos:prefLabel)")
            return

        # Try to extract ID from LOCAL namespace URI
        entity_id = self._uri_to_id(scheme_uri)
        if not entity_id:
            entity_id = str(uuid.uuid4())

        # Read description from skos:definition, not rdfs:comment
        description = self._get_first_string(scheme_uri, SKOS.definition)

        if is_taxonomy:
            # This is a Taxonomy
            self.incoming_entities[entity_id] = {
                "id": entity_id,
                "title": title,
                "description": description,
                "type": "taxonomy",
            }
        else:
            # This is a ConceptScheme
            parent_taxonomy_uri = self._get_first_object(scheme_uri, DCT.isPartOf)
            parent_taxonomy_id = None
            if parent_taxonomy_uri:
                parent_taxonomy_id = self._entity_map.get(str(parent_taxonomy_uri))

            self.incoming_entities[entity_id] = {
                "id": entity_id,
                "title": title,
                "description": description,
                "type": "concept_scheme",
                "taxonomy_id": parent_taxonomy_id,
            }

        self._entity_map[str(scheme_uri)] = entity_id

    def _process_class_entity(self, class_uri: Node) -> None:
        """Process an OWL Class."""
        # Skip if already processed
        if str(class_uri) in self._entity_map:
            return

        title = self._get_label(class_uri)
        if not title:
            self.warnings.append(f"Class {class_uri} has no label (rdfs:label or skos:prefLabel)")
            return

        description = self._get_first_string(class_uri, RDFS.comment)

        # Try to extract ID from LOCAL namespace URI
        entity_id = self._uri_to_id(class_uri)
        if not entity_id:
            entity_id = str(uuid.uuid4())

        # Find parent class if exists
        parent_class_uri = self._get_first_object(class_uri, RDFS.subClassOf)
        parent_class_id = None
        if parent_class_uri:
            parent_class_id = self._entity_map.get(str(parent_class_uri))

        # Get external references (from owl:sameAs only)
        external_references = self._extract_external_references_as_dicts(class_uri)

        # Get concept scheme from skos:inScheme
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
        # Skip if already processed
        if str(ind_uri) in self._entity_map:
            return

        title = self._get_label(ind_uri)
        if not title:
            self.warnings.append(f"NamedIndividual {ind_uri} has no label (rdfs:label or skos:prefLabel)")
            return

        description = self._get_first_string(ind_uri, RDFS.comment)

        # Try to extract ID from LOCAL namespace URI
        entity_id = self._uri_to_id(ind_uri)
        if not entity_id:
            entity_id = str(uuid.uuid4())

        # Get class memberships in order using indexed predicates (hasClass_0, hasClass_1, etc.)
        class_entries = []

        if self.graph is not None:
            # First, try to collect ordered class references from indexed predicates
            index = 0
            while True:
                indexed_predicate = LOCAL[f"hasClass_{index}"]
                class_uris = list(self.graph.objects(ind_uri, indexed_predicate))
                if not class_uris:
                    # No more indexed predicates found
                    break

                for class_uri in class_uris:
                    if str(class_uri) != str(OWL.NamedIndividual):
                        class_id = self._entity_map.get(str(class_uri))
                        if class_id:
                            class_entries.append((index, class_id))
                index += 1

            # If no ordered entries found via indexed predicates, fall back to collecting
            # all class memberships from rdf:type (unordered, for backwards compatibility)
            if not class_entries:
                class_uris = list(self.graph.objects(ind_uri, RDF.type))
                for i, class_uri in enumerate(class_uris):
                    if str(class_uri) == str(OWL.NamedIndividual):
                        continue
                    class_id = self._entity_map.get(str(class_uri))
                    if class_id:
                        class_entries.append((i, class_id))

        # Sort by order and extract IDs
        class_entries.sort(key=lambda x: x[0])
        class_ids = [class_id for _, class_id in class_entries]

        if not class_ids:
            self.warnings.append(f"NamedIndividual {ind_uri} has no class memberships (rdf:type)")
            return

        # Get external references (from owl:sameAs only)
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

    def _process_property_entity(self, prop_uri: Node) -> None:
        """Process an OWL ObjectProperty (PropertyDefinition)."""
        # Skip if already processed
        if str(prop_uri) in self._entity_map:
            return

        title = self._get_label(prop_uri)
        if not title:
            self.warnings.append(f"ObjectProperty {prop_uri} has no label (rdfs:label)")
            return

        description = self._get_first_string(prop_uri, RDFS.comment)

        # Try to extract ID from LOCAL namespace URI
        entity_id = self._uri_to_id(prop_uri)
        if not entity_id:
            entity_id = str(uuid.uuid4())

        # Extract identifier from title or URI
        identifier = title.lower().replace(" ", "_")

        self.incoming_entities[entity_id] = {
            "id": entity_id,
            "identifier": identifier,
            "title": title,
            "description": description,
            "type": "property_definition",
        }
        self._entity_map[str(prop_uri)] = entity_id

    def _process_relationships(self) -> None:
        """Process relationships between entities using property predicates."""
        if self.graph is None:
            return
        # Get all defined properties
        property_uris = set(self.graph.subjects(RDF.type, OWL.ObjectProperty))

        for prop_uri in property_uris:
            # Find all triples using this property
            for source_uri, _, target_uri in self.graph.triples((None, prop_uri, None)):
                source_id = self._entity_map.get(str(source_uri))
                target_id = self._entity_map.get(str(target_uri))
                prop_id = self._entity_map.get(str(prop_uri))

                if source_id and target_id and prop_id:
                    rel_id = str(uuid.uuid4())
                    self.incoming_entities[rel_id] = {
                        "id": rel_id,
                        "type": "relationship",
                        "source_id": source_id,
                        "target_id": target_id,
                        "property_definition_id": prop_id,
                    }

    def _extract_external_references_as_dicts(
        self, entity_uri: Node
    ) -> list[Dict[str, Any]]:
        """Extract external references from owl:sameAs URIs as dicts."""
        refs = []

        if self.graph is not None:
            # Extract owl:sameAs references (single source of truth)
            for same_as_uri in self.graph.objects(entity_uri, OWL.sameAs):
                uri_str = str(same_as_uri)
                # Parse source:identifier from the URI
                source, identifier = self._parse_uri_for_reference(uri_str)

                refs.append(
                    {
                        "source": source,
                        "identifier": identifier,
                        "uri": uri_str,
                    }
                )

        return refs

    def _parse_uri_for_reference(self, uri_str: str) -> tuple[str, str]:
        """Parse a URI to extract source and identifier for external references."""
        # Handle common patterns like http://dbpedia.org/resource/Dog or https://www.wikidata.org/wiki/Q144
        if "#" in uri_str:
            source, identifier = uri_str.rsplit("#", 1)
            # Extract domain from full URL
            domain = self._extract_domain_from_uri(source)
            return domain, identifier
        elif "/" in uri_str:
            parts = uri_str.rsplit("/", 1)
            source_part = parts[0]
            identifier = parts[1]
            # Extract domain name from the URI
            domain = self._extract_domain_from_uri(source_part)
            return domain, identifier
        else:
            return "external", uri_str

    def _extract_domain_from_uri(self, uri_part: str) -> str:
        """Extract the domain name from a URI (e.g., 'dbpedia' from 'http://dbpedia.org')."""
        # Remove protocol (http://, https://, etc.)
        if "://" in uri_part:
            uri_part = uri_part.split("://", 1)[1]

        # Remove 'www.' prefix if present
        if uri_part.startswith("www."):
            uri_part = uri_part[4:]

        # Extract the domain name (first part before the dot or slash)
        if "/" in uri_part:
            domain = uri_part.split("/")[0]
        else:
            domain = uri_part

        # Get the main domain name (e.g., 'dbpedia' from 'dbpedia.org', 'wikidata' from 'wikidata.org')
        if "." in domain:
            domain = domain.split(".")[0]

        return domain

    def _uri_to_id(self, uri: Node) -> Optional[str]:
        """Extract entity ID from LOCAL namespace URI."""
        uri_str = str(uri)
        if uri_str.startswith(str(LOCAL)):
            # Extract the ID from the LOCAL namespace
            return uri_str[len(str(LOCAL)) :]
        return None

    def _get_label(self, uri: Node) -> Optional[str]:
        """Get the label for a URI (rdfs:label or skos:prefLabel)."""
        label = self._get_first_string(uri, RDFS.label)
        if label:
            return label
        return self._get_first_string(uri, SKOS.prefLabel)

    def _get_first_string(self, uri: Node, predicate: URIRef) -> Optional[str]:
        """Get the first string value for a predicate."""
        if self.graph is None:
            return None
        value = self._get_first_object(uri, predicate)
        if value:
            return str(value)
        return None

    def _get_first_object(self, uri: Node, predicate: URIRef) -> Optional[Node]:
        """Get the first object for a predicate."""
        if self.graph is None:
            return None
        for obj in self.graph.objects(uri, predicate):
            return obj
        return None
