"""
SKOS adapter for exporting and importing ontology data.

Implements OntologySerializer and OntologyDeserializer ports to handle
SKOS (Simple Knowledge Organization System) RDF-based interchange format.

Mapping strategy:
- Taxonomy → skos:ConceptScheme
- ConceptScheme → skos:ConceptScheme (linked to parent Taxonomy via dct:isPartOf)
- Class → skos:Concept (with skos:inScheme pointing to parent ConceptScheme)
- Class.parent_class_id → skos:broader (and inverse skos:narrower)
- Class.title → skos:prefLabel
- Class.description → skos:definition
- external_references → LOCAL:externalReferences (JSON-encoded full object with source/identifier/uri)
  - Backwards compatible with legacy dct:source + skos:exactMatch format (heuristically reconstructed on import)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional, Dict, Any

from rdflib import Graph, Namespace, URIRef, Literal, RDF, OWL
from rdflib.term import Node

from utils.logger import get_logger
from domain.interchange.ports import OntologySerializer, OntologyDeserializer
from domain.interchange.entities import ResolutionRecord
from domain.interchange.services import ImportRunService
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    ImportPlan,
    ImportConflict,
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
)
from domain.ontology.value_objects import ExternalReference
from adapters.interchange.persistence_helpers import persist_incoming_entities

# RDF Namespaces
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DCT = Namespace("http://purl.org/dc/terms/")
LOCAL = Namespace("http://context-studio.local/ontology/")

logger = get_logger(__name__)


class SKOSSerializer(OntologySerializer):
    """
    Serializes ontology entities to SKOS RDF format.

    Supports multiple serialization scopes:
    - whole_graph: all taxonomies, concept schemes, and classes
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
        Initialize the SKOS serializer.

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
            Serialized ontology as bytes in SKOS RDF format

        Raises:
            ValueError: If the scope is invalid
            RuntimeError: If serialization fails
        """
        scope.validate()

        self.graph = Graph()
        assert self.graph is not None
        self.graph.bind("skos", SKOS)
        self.graph.bind("dct", DCT)
        self.graph.bind("local", LOCAL)

        try:  # type: ignore[unreachable]
            match scope.scope_type:
                case SerializationScopeType.WHOLE_GRAPH:
                    self._serialize_whole_graph()
                case SerializationScopeType.TAXONOMY:
                    assert scope.taxonomy_id is not None
                    self._serialize_taxonomy(scope.taxonomy_id)
                case SerializationScopeType.SCHEME:
                    assert scope.scheme_id is not None
                    self._serialize_scheme(scope.scheme_id, scope.include_descendants)
                case SerializationScopeType.ENTITY_SET:
                    self._serialize_entity_set(scope.entity_ids)

            result = self.graph.serialize(format=self.format)
            # Ensure result is bytes
            if isinstance(result, str):
                return result.encode("utf-8")
            return result  # type: ignore[unreachable,return-value]
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"SKOS serialization error: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"SKOS serialization failed: {str(e)}") from e

    def _serialize_whole_graph(self) -> None:
        """Serialize all taxonomies, concept schemes, and classes."""
        taxonomies = self.ontology_repo.list_taxonomies()
        for taxonomy in taxonomies:
            self._add_taxonomy_to_graph(taxonomy)

    def _serialize_taxonomy(self, taxonomy_id: str) -> None:
        """Serialize a single taxonomy and its descendants."""
        taxonomy = self.ontology_repo.get_taxonomy(taxonomy_id)
        if not taxonomy:
            raise ValueError(f"Taxonomy not found: {taxonomy_id}")

        self._add_taxonomy_to_graph(taxonomy)

    def _serialize_scheme(self, scheme_id: str, include_descendants: bool = True) -> None:
        """Serialize a single concept scheme and optionally its classes.

        Args:
            scheme_id: The concept scheme ID
            include_descendants: If True, include classes within the scheme; if False, only serialize the scheme itself
        """
        scheme = self.ontology_repo.get_concept_scheme(scheme_id)
        if not scheme:
            raise ValueError(f"Concept scheme not found: {scheme_id}")

        self._add_concept_scheme_to_graph(scheme, include_parent_taxonomy=True, include_descendants=include_descendants)

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
                continue

            logger.warning(
                f"Entity {entity_id} does not match any known type during SKOS serialization; skipping"
            )

    def _add_taxonomy_to_graph(self, taxonomy: Taxonomy) -> None:
        """Add a taxonomy and its descendants to the graph."""
        assert self.graph is not None
        # Taxonomy → skos:ConceptScheme
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
        self, scheme: ConceptScheme, include_parent_taxonomy: bool = True, include_descendants: bool = True
    ) -> None:
        """Add a concept scheme and optionally its classes to the graph.

        Args:
            scheme: The concept scheme to add
            include_parent_taxonomy: If True, add link to parent taxonomy
            include_descendants: If True, add classes within the scheme; if False, only add the scheme itself
        """
        assert self.graph is not None
        scheme_uri = self._entity_uri(scheme.id)
        self.graph.add((scheme_uri, RDF.type, SKOS.ConceptScheme))
        self.graph.add((scheme_uri, SKOS.prefLabel, Literal(scheme.title)))
        if scheme.description:
            self.graph.add((scheme_uri, SKOS.definition, Literal(scheme.description)))

        # Link to parent taxonomy via dct:isPartOf
        if include_parent_taxonomy:
            taxonomy_uri = self._entity_uri(scheme.taxonomy_id)
            self.graph.add((scheme_uri, DCT.isPartOf, taxonomy_uri))

        # Add classes that belong to this scheme only if include_descendants is True
        if include_descendants:
            classes = self.ontology_repo.list_classes(concept_scheme_id=scheme.id)
            for class_entity in classes:
                self._add_class_to_graph(class_entity)

    def _add_class_to_graph(self, class_entity: Class) -> None:
        """Add a class as a skos:Concept to the graph."""
        assert self.graph is not None
        class_uri = self._entity_uri(class_entity.id)
        self.graph.add((class_uri, RDF.type, SKOS.Concept))
        self.graph.add((class_uri, SKOS.prefLabel, Literal(class_entity.title)))
        if class_entity.description:
            self.graph.add(
                (class_uri, SKOS.definition, Literal(class_entity.description))
            )

        # Link to concept scheme
        scheme_uri = self._entity_uri(class_entity.concept_scheme_id)
        self.graph.add((class_uri, SKOS.inScheme, scheme_uri))

        # Add parent-child relationships
        if class_entity.parent_class_id:
            parent_uri = self._entity_uri(class_entity.parent_class_id)
            self.graph.add((class_uri, SKOS.broader, parent_uri))
            self.graph.add((parent_uri, SKOS.narrower, class_uri))

        # Add external references
        for ext_ref in class_entity.external_references:
            self._add_external_reference(class_uri, ext_ref)

    def _add_individual_to_graph(self, individual: Individual) -> None:
        """Add an individual to the graph as an RDF resource."""
        assert self.graph is not None
        ind_uri = self._entity_uri(individual.id)
        # Represent individual with RDF type
        self.graph.add((ind_uri, RDF.type, OWL.NamedIndividual))
        self.graph.add((ind_uri, SKOS.prefLabel, Literal(individual.title)))
        if individual.description:
            self.graph.add((ind_uri, SKOS.definition, Literal(individual.description)))

        # Add class memberships
        for class_id in individual.class_ids:
            class_uri = self._entity_uri(class_id)
            self.graph.add((ind_uri, RDF.type, class_uri))

        # Add external references
        for ext_ref in individual.external_references:
            self._add_external_reference(ind_uri, ext_ref)

    def _add_property_to_graph(self, prop: PropertyDefinition) -> None:
        """Add a property definition to the graph."""
        assert self.graph is not None
        prop_uri = self._entity_uri(prop.id)
        # Represent property definition with RDF type
        self.graph.add((prop_uri, RDF.type, OWL.ObjectProperty))
        self.graph.add((prop_uri, SKOS.prefLabel, Literal(prop.title)))
        if prop.description:
            self.graph.add((prop_uri, SKOS.definition, Literal(prop.description)))

    def _add_external_reference(
        self, subject_uri: URIRef, ext_ref: ExternalReference
    ) -> None:
        """
        Add external references in multiple formats for round-tripping and backwards compatibility.

        Adds:
        1. LOCAL:externalReferences JSON for faithful round-tripping with full source/identifier/uri
        2. dct:source pointing to the external URI (legacy format, only if uri is not None)
        3. skos:exactMatch pointing to the external URI (legacy format, only if uri is not None)
        """
        assert self.graph is not None
        # Store full external reference object as JSON for faithful round-tripping
        # This includes source, identifier, and uri fields
        ref_dict = {
            "source": ext_ref.source,
            "identifier": ext_ref.identifier,
            "uri": ext_ref.uri,
        }
        ref_json = json.dumps(ref_dict)
        self.graph.add((subject_uri, LOCAL.externalReferences, Literal(ref_json)))

        # Add legacy predicates for backwards compatibility (only if uri is available)
        if ext_ref.uri is not None:
            ext_ref_uri = URIRef(ext_ref.uri)
            self.graph.add((subject_uri, DCT.source, ext_ref_uri))
            self.graph.add((subject_uri, SKOS.exactMatch, ext_ref_uri))

    def _entity_uri(self, entity_id: str) -> URIRef:
        """Create a URI for an entity."""
        return LOCAL[entity_id]


class SKOSDeserializer(OntologyDeserializer):
    """
    Deserializes SKOS RDF data into ontology entities and produces an ImportPlan.

    Parses SKOS RDF (Turtle, RDF/XML, JSON-LD) and:
    1. Populates external_references from dct:source and skos:exactMatch before conflict detection
    2. Detects conflicts using the cascade (external_reference → uuid → title)
    3. Creates an ImportPlan with warnings for unhandled predicates
    """

    def __init__(
        self,
        ontology_repo,
        interchange_repo=None,
    ):
        """
        Initialize the SKOS deserializer.

        Args:
            ontology_repo: Repository for querying and persisting ontology entities
            interchange_repo: Optional repository for persisting import runs
        """
        self.ontology_repo = ontology_repo
        self.interchange_repo = interchange_repo
        self.graph: Optional[Graph] = None
        self.warnings: list[str] = []
        self.incoming_entities: Dict[str, Dict[str, Any]] = {}
        self._entity_map: Dict[str, str] = {}  # URI -> local entity ID
        self._classes_cache: Optional[list[Class]] = None

    def deserialize(
        self,
        source: bytes | str,
        dry_run: bool = True,
        resolutions: list[ResolutionRecord] | None = None,
    ) -> ImportPlan:
        """
        Deserialize SKOS RDF data and produce an import plan.

        Args:
            source: Serialized SKOS RDF as bytes or string
            dry_run: If True, returns plan without persisting
            resolutions: Optional list of ResolutionRecord objects to apply when committing

        Returns:
            ImportPlan describing what the import would/did do

        Raises:
            ValueError: If the source is malformed or resolutions are invalid
            RuntimeError: If deserialization fails
        """
        try:
            self.graph = Graph()
            assert self.graph is not None
            self.warnings = []
            self.incoming_entities = {}
            self._entity_map = {}  # Reset entity map for this deserialization
            self._classes_cache = None  # Reset classes cache

            # Ensure source is bytes for hashing
            if isinstance(source, str):
                source_bytes = source.encode("utf-8")
            else:
                source_bytes = source

            # Try to parse with auto-detection of format, collecting all errors
            format_errors: list[tuple[str, Exception]] = []
            for fmt in ["turtle", "xml", "json-ld"]:
                try:
                    self.graph = Graph()
                    self.graph.parse(data=source_bytes, format=fmt)
                    break
                except Exception as e:
                    format_errors.append((fmt, e))
                    continue
            else:
                # All formats failed - build error message from all attempts
                error_parts = [f"{fmt}: {str(e)}" for fmt, e in format_errors]
                error_msg = "Failed to parse SKOS RDF in any format. " + "; ".join(
                    error_parts
                )
                raise ValueError(error_msg) from (
                    format_errors[-1][1] if format_errors else None
                )

            # Extract entities from RDF
            self._extract_entities_from_graph()

            # Detect conflicts using cascade
            conflicts = self._detect_conflicts()

            # Calculate new entity count
            new_entity_count = len(self.incoming_entities) - len(conflicts)

            # Create import plan
            source_hash = hashlib.sha256(source_bytes).hexdigest()

            # If committing (not dry-run), apply resolutions and persist entities
            import_run_id = None
            if not dry_run:
                import_run_id = self._commit_with_resolutions(
                    conflicts=conflicts,
                    source_hash=source_hash,
                    resolutions=resolutions,
                )

            plan = ImportPlan(
                conflicts=tuple(conflicts),
                new_entity_count=new_entity_count,
                import_run_id=import_run_id,
                warnings=tuple(self.warnings),
                source_hash=source_hash,
                scope=None,
            )

            return plan
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"SKOS deserialization error: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"SKOS deserialization failed: {str(e)}") from e

    def _commit_with_resolutions(
        self,
        conflicts: list[ImportConflict],
        source_hash: str,
        resolutions: Optional[list[ResolutionRecord]] = None,
    ) -> str:
        """
        Commit the import by applying resolutions and persisting entities.

        For each incoming entity:
        - If it has a SKIP resolution, skip it
        - If it has ABORT resolution or is in conflict with no resolution, raise ValueError
        - Otherwise, create/update the entity in the ontology

        Args:
            conflicts: List of detected conflicts
            source_hash: SHA256 hash of the imported source
            resolutions: Optional list of ResolutionRecord objects from the user

        Returns:
            The ID of the created ImportRun

        Raises:
            ValueError: If any conflict lacks a resolution or has invalid resolution data
            RuntimeError: If persistence fails
        """
        # Build resolution map: entity_id -> ResolutionKind
        resolution_map: Dict[str, ResolutionKind] = {}
        if resolutions:
            for res in resolutions:
                resolution_map[res.entity_id] = res.resolution_chosen

        # Validate that all conflicts have resolutions
        for conflict in conflicts:
            entity_id = conflict.incoming["id"]
            if entity_id not in resolution_map:
                raise ValueError(
                    f"Conflict for entity {entity_id} ({conflict.match_kind.value}) "
                    f"requires resolution before commit (default: {conflict.default_resolution.value})"
                )

        # Create and persist ImportRun with resolutions
        import_run_service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        import_run = import_run_service.create_with_resolutions_and_persist(
            format=SerializationFormat.SKOS,
            source_hash=source_hash,
            scope=scope,
            resolutions=resolutions,
            source_uri=None,
            created_by=None,
            interchange_repo=self.interchange_repo,
        )

        # Process entities and persist those that aren't skipped
        affected_entity_ids = persist_incoming_entities(
            self.incoming_entities,
            resolution_map,
            self.ontology_repo,
            self.warnings,
        )

        # Update ImportRun with affected entities and mark as committed
        import_run.affected_entity_ids = affected_entity_ids
        import_run.mark_committed()
        if self.interchange_repo:
            self.interchange_repo.update(import_run)

        return import_run.id

    def _extract_entities_from_graph(self) -> None:
        """Extract taxonomies, concept schemes, and classes from the RDF graph."""
        assert self.graph is not None
        # Process all skos:ConceptScheme entities
        for subject in self.graph.subjects(RDF.type, SKOS.ConceptScheme):
            self._extract_concept_scheme_or_taxonomy(subject)

        # Process all skos:Concept entities
        for subject in self.graph.subjects(RDF.type, SKOS.Concept):
            self._extract_class(subject)

    def _extract_concept_scheme_or_taxonomy(self, uri: Node) -> None:
        """Extract a ConceptScheme or Taxonomy from the graph."""
        assert self.graph is not None
        entity_id = self._uri_to_id(uri)
        if not entity_id:
            return

        # Get label and definition
        title = None
        for title_obj in self.graph.objects(uri, SKOS.prefLabel):
            title = str(title_obj)
            break

        if not title:
            self.warnings.append(f"ConceptScheme/Taxonomy {uri} has no prefLabel")
            return

        description = None
        for desc_obj in self.graph.objects(uri, SKOS.definition):
            description = str(desc_obj)
            break

        # Check if it's linked to a parent (dct:isPartOf) - if so, it's a ConceptScheme
        parent_taxonomy_id = None
        for parent in self.graph.objects(uri, DCT.isPartOf):
            parent_taxonomy_id = self._uri_to_id(parent)
            break

        entity_dict = {
            "id": entity_id,
            "title": title,
            "description": description,
            "type": "concept_scheme" if parent_taxonomy_id else "taxonomy",
        }

        if parent_taxonomy_id:
            entity_dict["taxonomy_id"] = parent_taxonomy_id

        self.incoming_entities[entity_id] = entity_dict

    def _extract_class(self, uri: Node) -> None:
        """Extract a Class (skos:Concept) from the graph."""
        assert self.graph is not None
        entity_id = self._uri_to_id(uri)
        if not entity_id:
            return

        # Get label and definition
        title = None
        for title_obj in self.graph.objects(uri, SKOS.prefLabel):
            title = str(title_obj)
            break

        if not title:
            self.warnings.append(f"Concept {uri} has no prefLabel")
            return

        description = None
        for desc_obj in self.graph.objects(uri, SKOS.definition):
            description = str(desc_obj)
            break

        # Get concept scheme
        concept_scheme_id = None
        for scheme in self.graph.objects(uri, SKOS.inScheme):
            concept_scheme_id = self._uri_to_id(scheme)
            break

        if not concept_scheme_id:
            self.warnings.append(f"Concept {uri} has no inScheme")
            return

        # Get parent class (broader)
        parent_class_id = None
        for parent in self.graph.objects(uri, SKOS.broader):
            parent_class_id = self._uri_to_id(parent)
            break

        # Extract external references from LOCAL:externalReferences JSON (primary)
        # Fall back to dct:source and skos:exactMatch for backwards compatibility
        external_references = []

        # Try to extract from LOCAL:externalReferences JSON first
        for ext_ref_lit in self.graph.objects(uri, LOCAL.externalReferences):
            try:
                ref_dict = json.loads(str(ext_ref_lit))
                external_references.append(
                    {
                        "source": ref_dict.get("source"),
                        "identifier": ref_dict.get("identifier"),
                        "uri": ref_dict.get("uri"),
                    }
                )
            except (json.JSONDecodeError, TypeError):
                self.warnings.append(
                    f"Class {uri} has malformed LOCAL:externalReferences JSON"
                )

        # If no JSON references found, fall back to legacy dct:source and skos:exactMatch
        if not external_references:
            for source_uri in self.graph.objects(uri, DCT.source):
                source_str = str(source_uri)
                # Extract source name and identifier from URI
                source_name, identifier = self._parse_external_reference_uri(source_str)
                if source_name and identifier:
                    external_references.append(
                        {
                            "source": source_name,
                            "identifier": identifier,
                            "uri": source_str,
                        }
                    )

            for match_uri in self.graph.objects(uri, SKOS.exactMatch):
                source_str = str(match_uri)
                source_name, identifier = self._parse_external_reference_uri(source_str)
                if source_name and identifier:
                    # Check if already added via dct:source
                    if not any(r["uri"] == source_str for r in external_references):
                        external_references.append(
                            {
                                "source": source_name,
                                "identifier": identifier,
                                "uri": source_str,
                            }
                        )

        entity_dict = {
            "id": entity_id,
            "title": title,
            "description": description,
            "type": "class",
            "concept_scheme_id": concept_scheme_id,
            "parent_class_id": parent_class_id,
            "external_references": external_references,
        }

        self.incoming_entities[entity_id] = entity_dict

        # Record warnings for unhandled SKOS predicates
        self._check_unhandled_predicates(uri)

    def _check_unhandled_predicates(self, uri: Node) -> None:
        """Check for SKOS predicates that aren't being handled."""
        assert self.graph is not None
        unhandled = {
            SKOS.related,
            SKOS.altLabel,
            SKOS.hiddenLabel,
            SKOS.scopeNote,
            SKOS.editorialNote,
        }

        for predicate in unhandled:
            if list(self.graph.objects(uri, predicate)):
                self.warnings.append(
                    f"Concept {uri} has unhandled predicate {predicate}; value(s) ignored"
                )

    def _uri_to_id(self, uri: Node) -> Optional[str]:
        """
        Extract the ID from a URI, using cache to maintain referential integrity.

        For LOCAL namespace URIs, extract the ID.
        For fragment-based URIs, extract the fragment.
        For external URIs without fragments, generate a UUID (cached to ensure consistency).
        """
        uri_str = str(uri)

        # Check cache first
        if uri_str in self._entity_map:
            return self._entity_map[uri_str]

        entity_id: Optional[str] = None

        if uri_str.startswith(str(LOCAL)):
            entity_id = uri_str[len(str(LOCAL)) :]
        elif "#" in uri_str:
            # If it's a UUID-like string in the fragment, extract it
            entity_id = uri_str.split("#")[-1]
        else:
            # For external URIs without fragments, generate a UUID
            entity_id = str(uuid.uuid4())

        # Cache the mapping
        if entity_id:
            self._entity_map[uri_str] = entity_id

        return entity_id

    def _parse_external_reference_uri(
        self, uri_str: str
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Parse an external reference URI to extract source name and identifier.

        Examples:
        - http://dbpedia.org/resource/Dog → ("dbpedia", "Dog")
        - https://www.wikidata.org/wiki/Q1234 → ("wikidata", "Q1234")
        """
        uri_str_lower = uri_str.lower()

        # DBpedia
        if "dbpedia.org" in uri_str_lower:
            identifier = uri_str.split("/")[-1]
            return ("dbpedia", identifier)

        # Wikidata
        if "wikidata.org" in uri_str_lower:
            identifier = uri_str.split("/")[-1]
            return ("wikidata", identifier)

        # ConceptNet
        if "conceptnet" in uri_str_lower:
            identifier = uri_str.split("/")[-1]
            return ("conceptnet", identifier)

        # Schema.org
        if "schema.org" in uri_str_lower:
            identifier = uri_str.split("/")[-1]
            return ("schema.org", identifier)

        # Generic fallback: use the last segment
        identifier = uri_str.split("/")[-1].split("#")[-1]
        return ("external", identifier)

    def _detect_conflicts(self) -> list[ImportConflict]:
        """
        Detect conflicts using the cascade: external_reference → uuid → title.

        Pre-populates external_references before checking, making round-trips idempotent.
        """
        conflicts = []

        for entity_id, entity_dict in self.incoming_entities.items():
            # Check external references first
            external_references = entity_dict.get("external_references", [])
            existing_entity: str | None = None
            match_kind: MatchKind | None = None

            if external_references:
                # Try to find existing entity by external reference
                for ext_ref in external_references:
                    existing_by_ref = self._find_by_external_reference(
                        ext_ref["source"], ext_ref["identifier"]
                    )
                    if existing_by_ref:
                        existing_entity = existing_by_ref
                        match_kind = MatchKind.EXTERNAL_REFERENCE
                        break

            # If no external reference match, try UUID
            if not existing_entity:
                existing_by_uuid = self.ontology_repo.get_taxonomy(entity_id)
                if existing_by_uuid:
                    existing_entity = existing_by_uuid.id
                    match_kind = MatchKind.UUID
                else:
                    existing_by_uuid = self.ontology_repo.get_concept_scheme(entity_id)
                    if existing_by_uuid:
                        existing_entity = existing_by_uuid.id
                        match_kind = MatchKind.UUID
                    else:
                        existing_by_uuid = self.ontology_repo.get_class(entity_id)
                        if existing_by_uuid:
                            existing_entity = existing_by_uuid.id
                            match_kind = MatchKind.UUID

            # If no UUID match, try by title
            if not existing_entity and entity_dict.get("type") == "class":
                existing_by_title = self._find_class_by_title(
                    entity_dict["title"],
                    entity_dict.get("concept_scheme_id"),
                )
                if existing_by_title:
                    existing_entity = existing_by_title.id
                    match_kind = MatchKind.TITLE

            # If conflict found, record it
            if existing_entity and match_kind:
                default_resolution = (
                    ResolutionKind.MERGE
                    if match_kind == MatchKind.EXTERNAL_REFERENCE
                    else ResolutionKind.SKIP
                )
                conflict = ImportConflict(
                    match_kind=match_kind,
                    incoming=entity_dict,
                    existing=existing_entity,
                    default_resolution=default_resolution,
                    available_resolutions=(
                        ResolutionKind.SKIP,
                        ResolutionKind.OVERWRITE,
                        ResolutionKind.MERGE,
                    ),
                )
                conflicts.append(conflict)

        return conflicts

    def _find_by_external_reference(
        self, source: str, identifier: str
    ) -> Optional[str]:
        """Find an existing entity by external reference."""
        if self._classes_cache is None:
            self._classes_cache = self.ontology_repo.list_classes()

        for class_entity in self._classes_cache:
            for ext_ref in class_entity.external_references:
                if ext_ref.source == source and ext_ref.identifier == identifier:
                    return class_entity.id
        return None

    def _find_class_by_title(
        self, title: str, concept_scheme_id: Optional[str]
    ) -> Optional[Class]:
        """Find an existing class by title (and optional scheme)."""
        all_classes = self.ontology_repo.list_classes(
            concept_scheme_id=concept_scheme_id
        )
        for class_entity in all_classes:
            if class_entity.title == title:
                return class_entity
        return None
