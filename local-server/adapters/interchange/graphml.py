"""
GraphML adapter for exporting and importing ontology data.

Implements OntologySerializer and OntologyDeserializer ports to handle
GraphML (Graph Markup Language) format for visual tools (Cytoscape, Gephi, yEd, Neo4j).

Mapping strategy:
- Every entity (Taxonomy, Scheme, Class, Individual, PropertyDefinition) → <node> with a `kind` attribute
- Every Relationship and structural edge → <edge> with a `kind` attribute
- Entity attributes flatten to <data> elements with namespaced keys: cs:title, cs:description, cs:created_at, etc.
- external_references → reserved <data key="cs:external_references"> element, JSON-encoded array
- For Individuals with multi-class membership, class memberships are edges with <data key="cs:class_order">N</data>
- Layout coordinates (x, y) are ignored on import
"""

from __future__ import annotations

import hashlib
import json
import io
from typing import Optional, Dict, Any

import networkx as nx

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
    Relationship,
    PropertyDefinition,
)
from domain.ontology.value_objects import ExternalReference
from adapters.interchange.persistence_helpers import persist_incoming_entities

logger = get_logger(__name__)


class GraphMLSerializer(OntologySerializer):
    """
    Serializes ontology entities to GraphML format.

    Supports multiple serialization scopes:
    - whole_graph: all entities and relationships
    - taxonomy: single taxonomy and its descendants
    - scheme: single concept scheme and its classes
    - entity_set: specified entities only
    """

    def __init__(self, ontology_repo):
        """
        Initialize the GraphML serializer.

        Args:
            ontology_repo: Repository for querying ontology entities
        """
        self.ontology_repo = ontology_repo
        self.graph: Optional[nx.MultiDiGraph] = None

    def serialize(self, scope: SerializationScope) -> bytes:
        """
        Serialize the ontology according to the given scope.

        Args:
            scope: Describes what to serialize

        Returns:
            Serialized ontology as bytes in GraphML format

        Raises:
            ValueError: If the scope is invalid
            RuntimeError: If serialization fails
        """
        scope.validate()

        self.graph = nx.MultiDiGraph()

        try:
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

            # Write to in-memory BytesIO
            output = io.BytesIO()
            nx.write_graphml(self.graph, output)
            return output.getvalue()

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"GraphML serialization error: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"GraphML serialization failed: {str(e)}") from e

    def _serialize_whole_graph(self) -> None:
        """Serialize all entities and relationships."""
        # Add all taxonomies
        taxonomies = self.ontology_repo.list_taxonomies()
        for taxonomy in taxonomies:
            self._add_taxonomy(taxonomy)

        # Add all concept schemes
        schemes = self.ontology_repo.list_concept_schemes()
        for scheme in schemes:
            self._add_concept_scheme(scheme)

        # Add all classes
        classes = self.ontology_repo.list_classes(limit=10000)
        for cls in classes:
            self._add_class(cls)

        # Add all property definitions
        properties = self.ontology_repo.list_property_definitions()
        for prop in properties:
            self._add_property_definition(prop)

        # Add all individuals
        individuals = self.ontology_repo.list_individuals()
        for individual in individuals:
            self._add_individual(individual)

        # Add structural edges
        self._add_structural_edges(taxonomies, schemes, classes, individuals)

        # Add relationships
        relationships = self.ontology_repo.list_relationships()
        for rel in relationships:
            self._add_relationship(rel)

    def _serialize_taxonomy(self, taxonomy_id: str) -> None:
        """Serialize a single taxonomy and its descendants."""
        taxonomy = self.ontology_repo.get_taxonomy(taxonomy_id)
        if not taxonomy:
            raise ValueError(f"Taxonomy not found: {taxonomy_id}")

        self._add_taxonomy(taxonomy)

        # Add concept schemes in this taxonomy
        schemes = self.ontology_repo.list_concept_schemes(taxonomy_id=taxonomy.id)
        for scheme in schemes:
            self._add_concept_scheme(scheme)
            # Add classes in this scheme
            classes = self.ontology_repo.list_classes(
                concept_scheme_id=scheme.id, limit=10000
            )
            for cls in classes:
                self._add_class(cls)

        # Add relationships within this taxonomy
        self._add_structural_edges_for_taxonomy(taxonomy, schemes)

    def _serialize_scheme(self, scheme_id: str, include_descendants: bool = True) -> None:
        """Serialize a single concept scheme and optionally its classes.

        Args:
            scheme_id: The concept scheme ID
            include_descendants: If True, include classes within the scheme; if False, only serialize the scheme itself
        """
        scheme = self.ontology_repo.get_concept_scheme(scheme_id)
        if not scheme:
            raise ValueError(f"Concept scheme not found: {scheme_id}")

        # Add the parent taxonomy
        taxonomy = self.ontology_repo.get_taxonomy(scheme.taxonomy_id)
        if taxonomy:
            self._add_taxonomy(taxonomy)

        self._add_concept_scheme(scheme)

        # Add classes in this scheme only if include_descendants is True
        classes = []
        if include_descendants:
            classes = self.ontology_repo.list_classes(
                concept_scheme_id=scheme.id, limit=10000
            )
            for cls in classes:
                self._add_class(cls)

        # Add structural edges
        self._add_structural_edges_for_scheme(scheme, classes)

    def _serialize_entity_set(self, entity_ids: Optional[tuple[str, ...]]) -> None:
        """Serialize a specified set of entities."""
        if not entity_ids:
            return

        processed_ids = set()

        for entity_id in entity_ids:
            if entity_id in processed_ids:
                continue

            # Try each entity type
            taxonomy = self.ontology_repo.get_taxonomy(entity_id)
            if taxonomy:
                self._add_taxonomy(taxonomy)
                processed_ids.add(entity_id)
                continue

            scheme = self.ontology_repo.get_concept_scheme(entity_id)
            if scheme:
                self._add_concept_scheme(scheme)
                processed_ids.add(entity_id)
                continue

            cls = self.ontology_repo.get_class(entity_id)
            if cls:
                self._add_class(cls)
                processed_ids.add(entity_id)
                continue

            individual = self.ontology_repo.get_individual(entity_id)
            if individual:
                self._add_individual(individual)
                processed_ids.add(entity_id)
                continue

            prop = self.ontology_repo.get_property_definition(entity_id)
            if prop:
                self._add_property_definition(prop)
                processed_ids.add(entity_id)
                continue

            logger.warning(f"Entity {entity_id} does not match any known type during GraphML serialization; skipping")

    def _add_taxonomy(self, taxonomy: Taxonomy) -> None:
        """Add a taxonomy node to the graph."""
        assert self.graph is not None
        node_id = taxonomy.id
        self.graph.add_node(node_id)
        self._set_node_attributes(
            node_id,
            {
                "kind": "taxonomy",
                "cs:title": taxonomy.title,
                "cs:description": taxonomy.description or "",
                "cs:created_at": (
                    taxonomy.created_at.isoformat() if taxonomy.created_at else ""
                ),
                "cs:last_modified": (
                    taxonomy.last_modified.isoformat() if taxonomy.last_modified else ""
                ),
            },
        )

    def _add_concept_scheme(self, scheme: ConceptScheme) -> None:
        """Add a concept scheme node to the graph."""
        assert self.graph is not None
        node_id = scheme.id
        self.graph.add_node(node_id)
        self._set_node_attributes(
            node_id,
            {
                "kind": "concept_scheme",
                "cs:title": scheme.title,
                "cs:description": scheme.description or "",
                "cs:created_at": (
                    scheme.created_at.isoformat() if scheme.created_at else ""
                ),
                "cs:last_modified": (
                    scheme.last_modified.isoformat() if scheme.last_modified else ""
                ),
            },
        )

    def _add_class(self, cls: Class) -> None:
        """Add a class node to the graph."""
        assert self.graph is not None
        node_id = cls.id
        self.graph.add_node(node_id)

        ext_refs_json = json.dumps(
            [
                {
                    "source": ref.source,
                    "identifier": ref.identifier,
                    "uri": ref.uri,
                }
                for ref in cls.external_references
            ]
        )

        self._set_node_attributes(
            node_id,
            {
                "kind": "class",
                "cs:title": cls.title,
                "cs:description": cls.description or "",
                "cs:created_at": (cls.created_at.isoformat() if cls.created_at else ""),
                "cs:last_modified": (
                    cls.last_modified.isoformat() if cls.last_modified else ""
                ),
                "cs:external_references": ext_refs_json,
            },
        )

    def _add_individual(self, individual: Individual) -> None:
        """Add an individual node to the graph."""
        assert self.graph is not None
        node_id = individual.id
        self.graph.add_node(node_id)

        ext_refs_json = json.dumps(
            [
                {
                    "source": ref.source,
                    "identifier": ref.identifier,
                    "uri": ref.uri,
                }
                for ref in individual.external_references
            ]
        )

        self._set_node_attributes(
            node_id,
            {
                "kind": "individual",
                "cs:title": individual.title,
                "cs:description": individual.description or "",
                "cs:created_at": (
                    individual.created_at.isoformat() if individual.created_at else ""
                ),
                "cs:last_modified": (
                    individual.last_modified.isoformat()
                    if individual.last_modified
                    else ""
                ),
                "cs:external_references": ext_refs_json,
            },
        )

    def _add_property_definition(self, prop: PropertyDefinition) -> None:
        """Add a property definition node to the graph."""
        assert self.graph is not None
        node_id = prop.id
        self.graph.add_node(node_id)

        self._set_node_attributes(
            node_id,
            {
                "kind": "property_definition",
                "cs:title": prop.title,
                "cs:identifier": prop.identifier,
                "cs:description": prop.description or "",
                "cs:is_relevant": (
                    str(prop.is_relevant) if prop.is_relevant is not None else ""
                ),
                "cs:created_at": (
                    prop.created_at.isoformat() if prop.created_at else ""
                ),
                "cs:last_modified": (
                    prop.last_modified.isoformat() if prop.last_modified else ""
                ),
            },
        )

    def _add_structural_edges(
        self,
        taxonomies: list[Taxonomy],
        schemes: list[ConceptScheme],
        classes: list[Class],
        individuals: list[Individual],
    ) -> None:
        """Add structural edges (parent relationships, scheme membership, etc.)."""
        assert self.graph is not None

        # Taxonomy → ConceptScheme edges
        for scheme in schemes:
            if self.graph.has_node(scheme.id) and self.graph.has_node(
                scheme.taxonomy_id
            ):
                self.graph.add_edge(
                    scheme.taxonomy_id, scheme.id, key="has_scheme", kind="has_scheme"
                )

        # Class → ConceptScheme edges
        for cls in classes:
            if self.graph.has_node(cls.id) and self.graph.has_node(
                cls.concept_scheme_id
            ):
                self.graph.add_edge(
                    cls.concept_scheme_id, cls.id, key="has_class", kind="has_class"
                )

        # Class → Parent Class edges
        for cls in classes:
            if (
                cls.parent_class_id
                and self.graph.has_node(cls.id)
                and self.graph.has_node(cls.parent_class_id)
            ):
                self.graph.add_edge(
                    cls.id, cls.parent_class_id, key="parent_class", kind="parent_class"
                )

        # Individual → Class edges
        for individual in individuals:
            for idx, class_id in enumerate(individual.class_ids):
                if self.graph.has_node(individual.id) and self.graph.has_node(class_id):
                    self.graph.add_edge(
                        individual.id,
                        class_id,
                        key=f"class_membership_{idx}",
                        kind="class_membership",
                        **{"cs:class_order": str(idx)},
                    )

    def _add_structural_edges_for_taxonomy(
        self,
        taxonomy: Taxonomy,
        schemes: list[ConceptScheme],
    ) -> None:
        """Add structural edges for a specific taxonomy scope."""
        assert self.graph is not None

        for scheme in schemes:
            if self.graph.has_node(scheme.id) and self.graph.has_node(
                scheme.taxonomy_id
            ):
                self.graph.add_edge(
                    scheme.taxonomy_id, scheme.id, key="has_scheme", kind="has_scheme"
                )

    def _add_structural_edges_for_scheme(
        self,
        scheme: ConceptScheme,
        classes: list[Class],
    ) -> None:
        """Add structural edges for a specific scheme scope."""
        assert self.graph is not None

        for cls in classes:
            if self.graph.has_node(cls.id) and self.graph.has_node(
                cls.concept_scheme_id
            ):
                self.graph.add_edge(
                    cls.concept_scheme_id, cls.id, key="has_class", kind="has_class"
                )

            if (
                cls.parent_class_id
                and self.graph.has_node(cls.id)
                and self.graph.has_node(cls.parent_class_id)
            ):
                self.graph.add_edge(
                    cls.id, cls.parent_class_id, key="parent_class", kind="parent_class"
                )

    def _add_relationship(self, rel: Relationship) -> None:
        """Add a relationship edge to the graph."""
        assert self.graph is not None

        if self.graph.has_node(rel.source_id) and self.graph.has_node(rel.target_id):
            self.graph.add_edge(
                rel.source_id,
                rel.target_id,
                key=rel.id,
                kind="relationship",
                **{"cs:property_definition_id": rel.property_definition_id},
            )

    def _set_node_attributes(self, node_id: str, attributes: Dict[str, str]) -> None:
        """Set attributes on a node."""
        assert self.graph is not None
        for key, value in attributes.items():
            if value is not None:
                self.graph.nodes[node_id][key] = value


class GraphMLDeserializer(OntologyDeserializer):
    """
    Deserializes GraphML data into ontology entities and produces an ImportPlan.

    Parses GraphML and:
    1. Populates external_references from cs:external_references before conflict detection
    2. Detects conflicts using the cascade (external_reference → uuid → title)
    3. Reconstructs multi-class Individual ordering from cs:class_order edge attributes
    4. Ignores layout coordinates (x, y) without error
    5. Records unknown <data> keys in warnings
    """

    def __init__(self, ontology_repo, interchange_repo=None):
        """
        Initialize the GraphML deserializer.

        Args:
            ontology_repo: Repository for querying and persisting ontology entities
            interchange_repo: Optional repository for persisting import runs
        """
        self.ontology_repo = ontology_repo
        self.interchange_repo = interchange_repo
        self.graph: Optional[nx.MultiDiGraph] = None
        self.warnings: list[str] = []
        self.incoming_entities: Dict[str, Dict[str, Any]] = {}
        self._classes_cache: Optional[list[Class]] = None
        self._individuals_cache: Optional[list[Individual]] = None

    def deserialize(self, source: bytes | str, dry_run: bool = True, resolutions: list[ResolutionRecord] | None = None) -> ImportPlan:
        """
        Deserialize GraphML data and produce an import plan.

        Args:
            source: Serialized GraphML as bytes or string
            dry_run: If True, returns plan without persisting
            resolutions: Optional list of ResolutionRecord objects to apply when committing

        Returns:
            ImportPlan describing what the import would/did do

        Raises:
            ValueError: If the source is malformed or resolutions are invalid
            RuntimeError: If deserialization fails
        """
        try:
            self.warnings = []
            self.incoming_entities = {}
            self._classes_cache = None
            self._individuals_cache = None

            # Ensure source is bytes for hashing
            if isinstance(source, str):
                source_bytes = source.encode("utf-8")
            else:
                source_bytes = source

            # Parse GraphML
            try:
                # Read from in-memory BytesIO
                input_stream = io.BytesIO(source_bytes)
                loaded_graph = nx.read_graphml(input_stream)
                # Convert to MultiDiGraph to support multiple edges between nodes
                if not isinstance(loaded_graph, nx.MultiDiGraph):
                    self.graph = nx.MultiDiGraph(loaded_graph)
                else:
                    self.graph = loaded_graph
            except Exception as e:
                raise ValueError(f"Failed to parse GraphML: {str(e)}") from e

            # Extract entities from GraphML
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
            logger.error(f"GraphML deserialization error: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"GraphML deserialization failed: {str(e)}") from e

    def _commit_with_resolutions(
        self,
        conflicts: list[ImportConflict],
        source_hash: str,
        resolutions: Optional[list[ResolutionRecord]] = None,
    ) -> str:
        """
        Commit the import by applying resolutions and persisting entities.

        Args:
            conflicts: List of detected conflicts
            source_hash: SHA256 hash of the imported source
            resolutions: Optional list of ResolutionRecord objects from the user

        Returns:
            The ID of the created ImportRun

        Raises:
            ValueError: If any conflict lacks a resolution or has invalid resolution data
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
            format=SerializationFormat.GRAPHML,
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
        """Extract entities from the GraphML graph."""
        assert self.graph is not None

        for node_id, node_attrs in self.graph.nodes(data=True):
            kind = node_attrs.get("kind")

            if kind == "taxonomy":
                self._extract_taxonomy(node_id, node_attrs)
            elif kind == "concept_scheme":
                self._extract_concept_scheme(node_id, node_attrs)
            elif kind == "class":
                self._extract_class(node_id, node_attrs)
            elif kind == "individual":
                self._extract_individual(node_id, node_attrs)
            elif kind == "property_definition":
                self._extract_property_definition(node_id, node_attrs)
            else:
                logger.warning(f"Node {node_id} has unknown kind attribute: {kind}; skipping")

    def _check_unknown_attributes(
        self, node_id: str, attrs: Dict[str, Any], known_keys: set[str]
    ) -> None:
        """
        Check for unknown data keys and record warnings.

        Args:
            node_id: The node ID being checked
            attrs: The node attributes
            known_keys: Set of known attribute keys to exclude from warnings
        """
        # Layout attributes that should be silently ignored
        layout_keys = {"x", "y", "z", "label", "graphics"}

        for key in attrs.keys():
            if key not in known_keys and key not in layout_keys:
                self.warnings.append(f"Node {node_id} has unknown data key: {key}")

    def _extract_taxonomy(self, node_id: str, attrs: Dict[str, Any]) -> None:
        """Extract a Taxonomy from a node."""
        title = attrs.get("cs:title")
        if not title:
            self.warnings.append(f"Taxonomy {node_id} has no cs:title")
            return

        known_keys = {
            "kind",
            "cs:title",
            "cs:description",
            "cs:created_at",
            "cs:last_modified",
        }
        self._check_unknown_attributes(node_id, attrs, known_keys)

        entity_dict = {
            "id": node_id,
            "title": title,
            "description": attrs.get("cs:description") or None,
            "type": "taxonomy",
        }
        self.incoming_entities[node_id] = entity_dict

    def _extract_concept_scheme(self, node_id: str, attrs: Dict[str, Any]) -> None:
        """Extract a ConceptScheme from a node."""
        title = attrs.get("cs:title")
        if not title:
            self.warnings.append(f"ConceptScheme {node_id} has no cs:title")
            return

        # Find parent taxonomy via incoming edges
        assert self.graph is not None
        taxonomy_id = None
        for pred, _, _ in self.graph.in_edges(node_id, keys=True):
            if self.graph.nodes[pred].get("kind") == "taxonomy":
                taxonomy_id = pred
                break

        if not taxonomy_id:
            self.warnings.append(f"ConceptScheme {node_id} has no parent taxonomy")
            return

        known_keys = {
            "kind",
            "cs:title",
            "cs:description",
            "cs:created_at",
            "cs:last_modified",
        }
        self._check_unknown_attributes(node_id, attrs, known_keys)

        entity_dict = {
            "id": node_id,
            "title": title,
            "description": attrs.get("cs:description") or None,
            "type": "concept_scheme",
            "taxonomy_id": taxonomy_id,
        }
        self.incoming_entities[node_id] = entity_dict

    def _extract_class(self, node_id: str, attrs: Dict[str, Any]) -> None:
        """Extract a Class from a node."""
        title = attrs.get("cs:title")
        if not title:
            self.warnings.append(f"Class {node_id} has no cs:title")
            return

        assert self.graph is not None

        # Find parent concept scheme via incoming edges
        concept_scheme_id = None
        for pred, _, _ in self.graph.in_edges(node_id, keys=True):
            if self.graph.nodes[pred].get("kind") == "concept_scheme":
                concept_scheme_id = pred
                break

        if not concept_scheme_id:
            self.warnings.append(f"Class {node_id} has no parent concept scheme")
            return

        # Find parent class via outgoing edges
        parent_class_id = None
        for _, succ, _, edge_attrs in self.graph.out_edges(
            node_id, data=True, keys=True
        ):
            if edge_attrs.get("kind") == "parent_class":
                parent_class_id = succ
                break

        # Extract external references
        external_references = []
        ext_refs_json = attrs.get("cs:external_references")
        if ext_refs_json:
            try:
                refs = json.loads(ext_refs_json)
                for ref in refs:
                    external_references.append(
                        {
                            "source": ref["source"],
                            "identifier": ref["identifier"],
                            "uri": ref["uri"],
                        }
                    )
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Class {node_id} has malformed cs:external_references JSON: {e}"
                ) from e
            except KeyError as e:
                raise ValueError(
                    f"Class {node_id} external reference missing required field: {e}"
                ) from e

        known_keys = {
            "kind",
            "cs:title",
            "cs:description",
            "cs:created_at",
            "cs:last_modified",
            "cs:external_references",
        }
        self._check_unknown_attributes(node_id, attrs, known_keys)

        entity_dict = {
            "id": node_id,
            "title": title,
            "description": attrs.get("cs:description") or None,
            "type": "class",
            "concept_scheme_id": concept_scheme_id,
            "parent_class_id": parent_class_id,
            "external_references": external_references,
        }
        self.incoming_entities[node_id] = entity_dict

    def _extract_individual(self, node_id: str, attrs: Dict[str, Any]) -> None:
        """Extract an Individual from a node."""
        title = attrs.get("cs:title")
        if not title:
            self.warnings.append(f"Individual {node_id} has no cs:title")
            return

        assert self.graph is not None

        # Find parent classes via outgoing edges, maintaining order
        class_ids = []
        class_orders = []
        for _, succ, _, edge_attrs in self.graph.out_edges(
            node_id, data=True, keys=True
        ):
            if edge_attrs.get("kind") == "class_membership":
                class_order = edge_attrs.get("cs:class_order")
                if class_order is not None:
                    try:
                        class_orders.append((int(class_order), succ))
                    except ValueError:
                        self.warnings.append(
                            f"Individual {node_id} has invalid cs:class_order: {class_order}"
                        )
                        class_ids.append(succ)
                else:
                    self.warnings.append(
                        f"Individual {node_id} missing cs:class_order on class membership edge"
                    )
                    class_ids.append(succ)

        # Sort by order if we have ordering info
        if class_orders:
            class_orders.sort(key=lambda x: x[0])
            class_ids = [cid for _, cid in class_orders]

        if not class_ids:
            self.warnings.append(f"Individual {node_id} has no parent classes")
            return

        # Extract external references
        external_references = []
        ext_refs_json = attrs.get("cs:external_references")
        if ext_refs_json:
            try:
                refs = json.loads(ext_refs_json)
                for ref in refs:
                    external_references.append(
                        {
                            "source": ref["source"],
                            "identifier": ref["identifier"],
                            "uri": ref["uri"],
                        }
                    )
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Individual {node_id} has malformed cs:external_references JSON: {e}"
                ) from e
            except KeyError as e:
                raise ValueError(
                    f"Individual {node_id} external reference missing required field: {e}"
                ) from e

        known_keys = {
            "kind",
            "cs:title",
            "cs:description",
            "cs:created_at",
            "cs:last_modified",
            "cs:external_references",
        }
        self._check_unknown_attributes(node_id, attrs, known_keys)

        entity_dict = {
            "id": node_id,
            "title": title,
            "description": attrs.get("cs:description") or None,
            "type": "individual",
            "class_ids": class_ids,
            "external_references": external_references,
        }
        self.incoming_entities[node_id] = entity_dict

    def _extract_property_definition(self, node_id: str, attrs: Dict[str, Any]) -> None:
        """Extract a PropertyDefinition from a node."""
        title = attrs.get("cs:title")
        identifier = attrs.get("cs:identifier")
        if not title or not identifier:
            self.warnings.append(
                f"PropertyDefinition {node_id} missing cs:title or cs:identifier"
            )
            return

        is_relevant_str = attrs.get("cs:is_relevant", "")
        is_relevant = None
        if is_relevant_str:
            is_relevant = is_relevant_str.lower() == "true"

        known_keys = {
            "kind",
            "cs:title",
            "cs:identifier",
            "cs:description",
            "cs:is_relevant",
            "cs:created_at",
            "cs:last_modified",
        }
        self._check_unknown_attributes(node_id, attrs, known_keys)

        entity_dict = {
            "id": node_id,
            "title": title,
            "identifier": identifier,
            "description": attrs.get("cs:description") or None,
            "type": "property_definition",
            "is_relevant": is_relevant,
        }
        self.incoming_entities[node_id] = entity_dict

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
                        else:
                            existing_by_uuid = self.ontology_repo.get_individual(
                                entity_id
                            )
                            if existing_by_uuid:
                                existing_entity = existing_by_uuid.id
                                match_kind = MatchKind.UUID
                            else:
                                existing_by_uuid = (
                                    self.ontology_repo.get_property_definition(
                                        entity_id
                                    )
                                )
                                if existing_by_uuid:
                                    existing_entity = existing_by_uuid.id
                                    match_kind = MatchKind.UUID

            # If no UUID match, try by title (only for classes)
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
            self._classes_cache = self.ontology_repo.list_classes(limit=10000)

        for class_entity in self._classes_cache:
            for ext_ref in class_entity.external_references:
                if ext_ref.source == source and ext_ref.identifier == identifier:
                    return class_entity.id

        if self._individuals_cache is None:
            self._individuals_cache = self.ontology_repo.list_individuals()

        for individual in self._individuals_cache:
            for ext_ref in individual.external_references:
                if ext_ref.source == source and ext_ref.identifier == identifier:
                    return individual.id

        return None

    def _find_class_by_title(
        self, title: str, concept_scheme_id: Optional[str]
    ) -> Optional[Class]:
        """Find an existing class by title (and optional scheme)."""
        all_classes = self.ontology_repo.list_classes(
            concept_scheme_id=concept_scheme_id, limit=10000
        )
        for class_entity in all_classes:
            if class_entity.title == title:
                return class_entity
        return None
