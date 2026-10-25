"""
Read-only tools for the chat assistant.

Each tool implements the chat ChatTool port over the ontology service, the
graph service and the vector indexes. Every entity in a result carries `id`,
`kind` and `title`, with kinds that map 1:1 to the UI's entity pages
(taxonomy, scheme, class, individual; property for property definitions), and
the outcome lists those entities so answers can link to them.

Results are compact JSON capped at about 4,000 characters: when a result is
longer, its item list is cut and the result says so.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Optional, Sequence

from domain.chat.value_objects import ENTITY_KINDS, EntityRef, ToolOutcome, ToolSpec
from domain.graph.exceptions import NodeNotFoundError
from domain.graph.services import GraphAnalysisService
from domain.ontology.entities import Class, ConceptScheme, Individual, PropertyDefinition, Taxonomy
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.ports import EmbeddingService, IndividualVectorIndex, SchemaVectorIndex
from domain.ontology.services import OntologyService
from utils.async_executor import run_sync_in_executor

MAX_RESULT_CHARS = 4000
DEFAULT_LIMIT = 20
MAX_LIMIT = 50
# Minimum cosine similarity for a vector-search hit to be returned.
VECTOR_THRESHOLD = 0.35

Entity = Taxonomy | ConceptScheme | Class | Individual | PropertyDefinition


class ToolArgumentError(ValueError):
    """The model passed invalid tool arguments."""


# ============================================================================
# Entity resolution
# ============================================================================


def kind_of(entity: Entity) -> str:
    """The link kind for an ontology entity."""
    if isinstance(entity, Taxonomy):
        return "taxonomy"
    if isinstance(entity, ConceptScheme):
        return "scheme"
    if isinstance(entity, Class):
        return "class"
    if isinstance(entity, Individual):
        return "individual"
    return "property"


def ref_of(entity: Entity) -> EntityRef:
    """The link reference for an ontology entity."""
    return EntityRef(id=str(entity.id), kind=kind_of(entity), title=entity.title)


class EntityResolver:
    """Finds ontology entities by id without knowing their kind."""

    def __init__(self, ontology: OntologyService) -> None:
        self._ontology = ontology

    def get(self, entity_id: str) -> Entity:
        """
        Return the entity with this id, whatever its kind.

        Raises:
            EntityNotFoundError: If no taxonomy, scheme, class, individual or
                property definition has this id
        """
        getters: Sequence[Callable[[str], Entity]] = (
            self._ontology.get_class,
            self._ontology.get_individual,
            self._ontology.get_concept_scheme,
            self._ontology.get_taxonomy,
            self._ontology.get_property_definition,
        )
        for getter in getters:
            try:
                return getter(entity_id)
            except EntityNotFoundError:
                continue
        raise EntityNotFoundError("Entity", entity_id)

    def get_many(self, ids: Sequence[str]) -> dict[str, Entity]:
        """Return the entities with these ids; ids that don't resolve are omitted."""
        wanted = list(dict.fromkeys(str(i) for i in ids if i))
        if not wanted:
            return {}
        found: dict[str, Entity] = {}
        batches: Sequence[Callable[[], Sequence[Entity]]] = (
            lambda: self._ontology.list_classes(ids=wanted, limit=len(wanted)),
            lambda: self._ontology.list_individuals(ids=wanted, limit=None),
            lambda: self._ontology.list_property_definitions(ids=wanted, limit=None),
        )
        for batch in batches:
            for entity in batch():
                found[str(entity.id)] = entity
        for entity_id in wanted:
            if entity_id not in found:
                try:
                    found[entity_id] = self.get(entity_id)
                except EntityNotFoundError:
                    pass
        return found

    def parent_titles(self, entities: Sequence[Entity]) -> dict[str, str]:
        """Map entity id to its parent's title (scheme's taxonomy, class's scheme, ...)."""
        parent_ids: dict[str, str] = {}
        for entity in entities:
            parent_id = _parent_id(entity)
            if parent_id:
                parent_ids[str(entity.id)] = parent_id
        parents = self.get_many(list(parent_ids.values()))
        return {
            entity_id: parents[parent_id].title
            for entity_id, parent_id in parent_ids.items()
            if parent_id in parents
        }


def _parent_id(entity: Entity) -> Optional[str]:
    if isinstance(entity, ConceptScheme):
        return entity.taxonomy_id
    if isinstance(entity, Class):
        return entity.parent_class_id or entity.concept_scheme_id
    if isinstance(entity, Individual):
        return entity.class_ids[0] if entity.class_ids else None
    return None


# ============================================================================
# Tool base and helpers
# ============================================================================


class _Tool:
    """Base for tools: runs the synchronous lookup in the thread pool."""

    name: str = ""
    description: str = ""
    input_schema: Mapping[str, Any] = {}

    def __init__(self, ontology: OntologyService, resolver: EntityResolver) -> None:
        self._ontology = ontology
        self._resolver = resolver

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name, description=self.description, input_schema=self.input_schema
        )

    async def execute(self, args: Mapping[str, Any]) -> ToolOutcome:
        return await run_sync_in_executor(self._run_safely, dict(args))

    def _run_safely(self, args: dict[str, Any]) -> ToolOutcome:
        try:
            return self.run(args)
        except ToolArgumentError as e:
            return _error(f"Invalid arguments: {e}", f"{self.name}: invalid arguments")
        except (EntityNotFoundError, NodeNotFoundError):
            entity_id = next((v for k, v in args.items() if k.endswith("id")), "")
            return _error(f"No entity found with id {entity_id!r}.", "Entity not found")

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        raise NotImplementedError


def _error(message: str, summary: str) -> ToolOutcome:
    return ToolOutcome(content=json.dumps({"error": message}), summary=summary, is_error=True)


def _required_str(args: Mapping[str, Any], name: str) -> str:
    value = args.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ToolArgumentError(f"'{name}' must be a non-empty string")
    return value.strip()


def _optional_str(args: Mapping[str, Any], name: str) -> Optional[str]:
    value = args.get(name)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ToolArgumentError(f"'{name}' must be a string")
    return value.strip() or None


def _int_arg(args: Mapping[str, Any], name: str, default: int, low: int, high: int) -> int:
    value = args.get(name, default)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolArgumentError(f"'{name}' must be a number")
    return max(low, min(high, int(value)))


def _choice(args: Mapping[str, Any], name: str, choices: Sequence[str], default: str) -> str:
    value = args.get(name) or default
    if value not in choices:
        raise ToolArgumentError(f"'{name}' must be one of {', '.join(choices)}")
    return str(value)


def _ref_dict(ref: EntityRef) -> dict[str, str]:
    return {"id": ref.id, "kind": ref.kind, "title": ref.title}


def _outcome(
    payload: dict[str, Any],
    list_key: Optional[str],
    summary: str,
    entities: Sequence[EntityRef],
) -> ToolOutcome:
    """Serialize a result, cutting its item list until it fits MAX_RESULT_CHARS."""
    content = _dumps(payload)
    if list_key is not None and len(content) > MAX_RESULT_CHARS:
        items = list(payload[list_key])
        while items and len(content) > MAX_RESULT_CHARS:
            items = items[: max(len(items) * 3 // 4, len(items) - 1)]
            payload = {
                **payload,
                list_key: items,
                "truncated": f"showing {len(items)} items; ask for fewer or page with offset",
            }
            content = _dumps(payload)
    shown = set(_ids_in(payload))
    return ToolOutcome(
        content=content,
        summary=summary,
        entities=tuple(dict.fromkeys(e for e in entities if e.id in shown)),
    )


def _dumps(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, default=str)


def _ids_in(value: Any):
    """Yield every entity id in a result (any dict with id, kind and title)."""
    if isinstance(value, dict):
        if {"id", "kind", "title"} <= value.keys():
            yield str(value["id"])
        for item in value.values():
            yield from _ids_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from _ids_in(item)


_LIMIT_SCHEMA = {
    "type": "integer",
    "minimum": 1,
    "maximum": MAX_LIMIT,
    "description": f"Maximum results (default {DEFAULT_LIMIT}, max {MAX_LIMIT})",
}


# ============================================================================
# Tools
# ============================================================================


class SearchEntitiesTool(_Tool):
    """Find entities by title text and by meaning."""

    name = "search_entities"
    description = (
        "Search the workspace for taxonomies, concept schemes, classes, individuals and"
        " relationship types (property) by name or meaning. Returns id, kind, title,"
        " a similarity score and the parent's title. Start here to find the id of"
        " anything the user names."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Name or description to look for"},
            "kinds": {
                "type": "array",
                "items": {"type": "string", "enum": list(ENTITY_KINDS)},
                "description": "Only return these kinds (default: all)",
            },
            "limit": _LIMIT_SCHEMA,
        },
        "required": ["query"],
    }

    def __init__(
        self,
        ontology: OntologyService,
        resolver: EntityResolver,
        embedding: Optional[EmbeddingService] = None,
        schema_index: Optional[SchemaVectorIndex] = None,
        individual_index: Optional[IndividualVectorIndex] = None,
    ) -> None:
        super().__init__(ontology, resolver)
        self._embedding = embedding
        self._schema_index = schema_index
        self._individual_index = individual_index

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        query = _required_str(args, "query")
        limit = _int_arg(args, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
        kinds = args.get("kinds") or list(ENTITY_KINDS)
        if not isinstance(kinds, list) or any(k not in ENTITY_KINDS for k in kinds):
            raise ToolArgumentError(f"'kinds' must be a list of {', '.join(ENTITY_KINDS)}")

        scores: dict[str, float] = {}
        entities: dict[str, Entity] = {}
        for entity in self._text_matches(query, kinds, limit):
            entities[str(entity.id)] = entity
            exact = entity.title.strip().lower() == query.lower()
            scores[str(entity.id)] = 1.0 if exact else 0.9
        vector_scores = self._vector_matches(query, kinds, limit)
        missing = [i for i in vector_scores if i not in entities]
        entities.update(self._resolver.get_many(missing))
        for entity_id, score in vector_scores.items():
            if entity_id in entities and entity_id not in scores:
                scores[entity_id] = score

        ranked = sorted(
            (entities[i] for i in scores if kind_of(entities[i]) in kinds),
            key=lambda e: (-scores[str(e.id)], len(e.title), e.title),
        )[:limit]
        parents = self._resolver.parent_titles(ranked)
        results = []
        for entity in ranked:
            item: dict[str, Any] = {
                **_ref_dict(ref_of(entity)),
                "score": round(scores[str(entity.id)], 3),
            }
            if str(entity.id) in parents:
                item["parent_title"] = parents[str(entity.id)]
            results.append(item)
        return _outcome(
            {"query": query, "results": results},
            "results",
            f"Found {len(results)} for “{query}”",
            [ref_of(e) for e in ranked],
        )

    def _text_matches(self, query: str, kinds: Sequence[str], limit: int) -> list[Entity]:
        listers: dict[str, Callable[[], Sequence[Entity]]] = {
            "taxonomy": lambda: self._ontology.list_taxonomies(query=query, limit=limit),
            "scheme": lambda: self._ontology.list_concept_schemes(query=query, limit=limit),
            "class": lambda: self._ontology.list_classes(query=query, limit=limit),
            "individual": lambda: self._ontology.list_individuals(query=query, limit=limit),
            "property": lambda: self._ontology.list_property_definitions(query=query, limit=limit),
        }
        matches: list[Entity] = []
        for kind in kinds:
            matches.extend(listers[kind]())
        return matches

    def _vector_matches(self, query: str, kinds: Sequence[str], limit: int) -> dict[str, float]:
        if self._embedding is None:
            return {}
        embedding = self._embedding.embed(query)
        scores: dict[str, float] = {}
        schema_kinds = [
            k
            for k, wanted in (("class", "class"), ("property_definition", "property"))
            if wanted in kinds
        ]
        if self._schema_index is not None and schema_kinds:
            for match in self._schema_index.search(
                embedding, kinds=schema_kinds, top_k=limit, threshold=VECTOR_THRESHOLD
            ):
                scores[match.entity_id] = max(scores.get(match.entity_id, 0.0), match.score)
        if self._individual_index is not None and "individual" in kinds:
            for match in self._individual_index.search(
                embedding, class_ids=[], top_k=limit, threshold=VECTOR_THRESHOLD
            ):
                scores[match.individual_id] = match.score
        return scores


class GetEntityTool(_Tool):
    """Details of one entity."""

    name = "get_entity"
    description = (
        "Get one entity by id: title, identifier, description, parents (taxonomy,"
        " scheme, parent class), classes of an individual, data properties, and counts"
        " of children and relationships."
    )
    input_schema = {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Entity id"}},
        "required": ["id"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        entity = self._resolver.get(_required_str(args, "id"))
        ref = ref_of(entity)
        result: dict[str, Any] = {
            **_ref_dict(ref),
            "identifier": getattr(entity, "identifier", None),
            "description": entity.description,
        }
        related: list[EntityRef] = [ref]
        counts: dict[str, int] = {}

        def link(field: str, ids: Sequence[Optional[str]]) -> None:
            found = self._resolver.get_many([i for i in ids if i])
            refs = [ref_of(found[i]) for i in ids if i and i in found]
            related.extend(refs)
            result[field] = [_ref_dict(r) for r in refs]

        if isinstance(entity, Taxonomy):
            counts["schemes"] = self._ontology.count_concept_schemes(taxonomy_id=entity.id)
        elif isinstance(entity, ConceptScheme):
            link("parents", [entity.taxonomy_id])
            counts["classes"] = self._ontology.count_classes(concept_scheme_id=entity.id)
        elif isinstance(entity, Class):
            link("parents", [entity.parent_class_id, entity.concept_scheme_id, entity.taxonomy_id])
            counts["subclasses"] = self._ontology.count_classes(parent_class_id=entity.id)
            counts["individuals"] = self._ontology.count_individuals(class_id=entity.id)
            result["properties"] = _data_properties(entity)
        elif isinstance(entity, Individual):
            link("classes", list(entity.class_ids))
            result["properties"] = _data_properties(entity)
        elif isinstance(entity, PropertyDefinition):
            link("domain", [entity.domain_class_id])
            link("range", [entity.range_class_id])
            counts["relationships"] = self._ontology.count_relationships(property_id=entity.id)
        if not isinstance(entity, (Taxonomy, ConceptScheme, PropertyDefinition)):
            counts["relationships_out"] = self._ontology.count_relationships(source_id=entity.id)
            counts["relationships_in"] = self._ontology.count_relationships(target_id=entity.id)
        result["counts"] = counts
        return _outcome(result, None, f"{ref.title} ({ref.kind})", related)


def _data_properties(entity: Class | Individual) -> dict[str, Any]:
    return {p.property_identifier: p.value for p in entity.data_properties}


class ListChildrenTool(_Tool):
    """Children of a taxonomy, scheme or class."""

    name = "list_children"
    description = (
        "List what is under an entity: the schemes of a taxonomy, the classes of a"
        " scheme, or the subclasses and then the individuals of a class. Pages with"
        " limit and offset; returns the total."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Taxonomy, scheme or class id"},
            "limit": _LIMIT_SCHEMA,
            "offset": {"type": "integer", "minimum": 0, "description": "Items to skip"},
        },
        "required": ["id"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        entity = self._resolver.get(_required_str(args, "id"))
        limit = _int_arg(args, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
        offset = _int_arg(args, "offset", 0, 0, 1_000_000)

        children: list[Entity]
        if isinstance(entity, Taxonomy):
            total = self._ontology.count_concept_schemes(taxonomy_id=entity.id)
            children = list(
                self._ontology.list_concept_schemes(
                    taxonomy_id=entity.id, limit=limit, offset=offset, sort_by="title"
                )
            )
        elif isinstance(entity, ConceptScheme):
            total = self._ontology.count_classes(concept_scheme_id=entity.id)
            children = list(
                self._ontology.list_classes(
                    concept_scheme_id=entity.id, limit=limit, offset=offset, sort_by="title"
                )
            )
        elif isinstance(entity, Class):
            subclass_total = self._ontology.count_classes(parent_class_id=entity.id)
            individual_total = self._ontology.count_individuals(class_id=entity.id)
            total = subclass_total + individual_total
            children = []
            if offset < subclass_total:
                children = list(
                    self._ontology.list_classes(
                        parent_class_id=entity.id, limit=limit, offset=offset, sort_by="title"
                    )
                )
            remaining = limit - len(children)
            if remaining > 0:
                children += self._ontology.list_individuals(
                    class_id=entity.id,
                    limit=remaining,
                    offset=max(0, offset - subclass_total),
                    sort_by="title",
                )
        else:
            raise ToolArgumentError(f"a {kind_of(entity)} has no children; use list_relationships")

        items = [_ref_dict(ref_of(c)) for c in children]
        parent = ref_of(entity)
        return _outcome(
            {"parent": _ref_dict(parent), "items": items, "total": total, "offset": offset},
            "items",
            f"{len(items)} of {total} under {parent.title}",
            [parent, *(ref_of(c) for c in children)],
        )


class ListRelationshipsTool(_Tool):
    """Typed relationships of an entity."""

    name = "list_relationships"
    description = (
        "List the typed relationships of an entity: outgoing (entity is the source),"
        " incoming (entity is the target) or both, optionally of one relationship"
        " type (property id). Each has the relationship type and both ends."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "entity_id": {"type": "string", "description": "Entity id"},
            "direction": {"type": "string", "enum": ["out", "in", "both"]},
            "property_id": {"type": "string", "description": "Only this relationship type"},
            "limit": _LIMIT_SCHEMA,
        },
        "required": ["entity_id"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        entity = self._resolver.get(_required_str(args, "entity_id"))
        direction = _choice(args, "direction", ("out", "in", "both"), "both")
        property_id = _optional_str(args, "property_id")
        limit = _int_arg(args, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)

        relationships = []
        total = 0
        if direction in ("out", "both"):
            relationships += self._ontology.list_relationships(
                source_id=entity.id, property_id=property_id, limit=limit
            )
            total += self._ontology.count_relationships(
                source_id=entity.id, property_id=property_id
            )
        if direction in ("in", "both"):
            relationships += self._ontology.list_relationships(
                target_id=entity.id, property_id=property_id, limit=limit
            )
            total += self._ontology.count_relationships(
                target_id=entity.id, property_id=property_id
            )
        relationships = relationships[:limit]

        ids = [r.source_id for r in relationships] + [r.target_id for r in relationships]
        ids += [r.property_definition_id for r in relationships]
        found = self._resolver.get_many(ids)
        refs: list[EntityRef] = [ref_of(entity)]
        items = []
        for rel in relationships:
            end_ids = (rel.property_definition_id, rel.source_id, rel.target_id)
            ends = [found.get(str(i)) for i in end_ids]
            if any(e is None for e in ends):
                continue
            prop, source, target = (ref_of(e) for e in ends)  # type: ignore[arg-type]
            refs += [prop, source, target]
            items.append(
                {
                    "id": str(rel.id),
                    "property": _ref_dict(prop),
                    "source": _ref_dict(source),
                    "target": _ref_dict(target),
                }
            )
        return _outcome(
            {"entity": _ref_dict(refs[0]), "relationships": items, "total": total},
            "relationships",
            f"{len(items)} of {total} relationships of {refs[0].title}",
            refs,
        )


class ListRelationshipTypesTool(_Tool):
    """Relationship types (property definitions)."""

    name = "list_relationship_types"
    description = (
        "List relationship types (property definitions), optionally filtered by text,"
        " with their domain and range classes."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Text the title or identifier contains"},
            "limit": _LIMIT_SCHEMA,
        },
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        query = _optional_str(args, "query")
        limit = _int_arg(args, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
        properties = self._ontology.list_property_definitions(
            query=query, limit=limit, sort_by="title"
        )
        total = self._ontology.count_property_definitions(query=query)
        found = self._resolver.get_many(
            [p.domain_class_id for p in properties if p.domain_class_id]
            + [p.range_class_id for p in properties if p.range_class_id]
        )
        refs: list[EntityRef] = []
        items = []
        for prop in properties:
            ref = ref_of(prop)
            refs.append(ref)
            item: dict[str, Any] = {**_ref_dict(ref), "identifier": prop.identifier}
            ends = (("domain", prop.domain_class_id), ("range", prop.range_class_id))
            for field, class_id in ends:
                if class_id and class_id in found:
                    end = ref_of(found[class_id])
                    refs.append(end)
                    item[field] = _ref_dict(end)
            items.append(item)
        label = f" matching “{query}”" if query else ""
        return _outcome(
            {"items": items, "total": total},
            "items",
            f"{len(items)} of {total} relationship types{label}",
            refs,
        )


class GetNeighborsTool(_Tool):
    """Entities connected to an entity in the graph."""

    name = "get_neighbors"
    description = (
        "List entities connected to an entity in the knowledge graph, through any"
        " relationship or class membership, up to 2 hops away."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Entity id"},
            "direction": {"type": "string", "enum": ["out", "in", "both"]},
            "depth": {"type": "integer", "minimum": 1, "maximum": 2},
            "limit": _LIMIT_SCHEMA,
        },
        "required": ["id"],
    }

    def __init__(
        self, ontology: OntologyService, resolver: EntityResolver, graph: GraphAnalysisService
    ) -> None:
        super().__init__(ontology, resolver)
        self._graph = graph

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        entity = self._resolver.get(_required_str(args, "id"))
        direction = _choice(args, "direction", ("out", "in", "both"), "both")
        depth = _int_arg(args, "depth", 1, 1, 2)
        limit = _int_arg(args, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
        neighbor_ids = self._graph.get_neighbors(str(entity.id), direction=direction, depth=depth)
        found = self._resolver.get_many(sorted(neighbor_ids))
        neighbors = sorted(found.values(), key=lambda e: (kind_of(e), e.title))[:limit]
        center = ref_of(entity)
        return _outcome(
            {
                "entity": _ref_dict(center),
                "neighbors": [_ref_dict(ref_of(n)) for n in neighbors],
                "total": len(found),
            },
            "neighbors",
            f"{len(neighbors)} of {len(found)} neighbors of {center.title}",
            [center, *(ref_of(n) for n in neighbors)],
        )


class FindPathTool(_Tool):
    """Shortest path between two entities."""

    name = "find_path"
    description = (
        "Find the shortest path between two entities in the knowledge graph. Returns"
        " the entities along the path in order and the relationship types between them,"
        " or path null when they are not connected."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "source_id": {"type": "string", "description": "Start entity id"},
            "target_id": {"type": "string", "description": "End entity id"},
        },
        "required": ["source_id", "target_id"],
    }

    def __init__(
        self, ontology: OntologyService, resolver: EntityResolver, graph: GraphAnalysisService
    ) -> None:
        super().__init__(ontology, resolver)
        self._graph = graph

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        source = self._resolver.get(_required_str(args, "source_id"))
        target = self._resolver.get(_required_str(args, "target_id"))
        ends = [ref_of(source), ref_of(target)]
        path = self._graph.find_shortest_path(str(source.id), str(target.id))
        if path is None:
            return _outcome(
                {"source": _ref_dict(ends[0]), "target": _ref_dict(ends[1]), "path": None},
                None,
                f"No path from {ends[0].title} to {ends[1].title}",
                ends,
            )
        found = self._resolver.get_many(path.path)
        nodes = [ref_of(found[i]) for i in path.path if i in found]
        return _outcome(
            {
                "path": [_ref_dict(n) for n in nodes],
                "relationships": list(path.relationships),
                "length": path.length,
            },
            None,
            f"Path of {path.length} steps from {ends[0].title} to {ends[1].title}",
            nodes,
        )


def build_chat_tools(
    ontology: OntologyService,
    graph: GraphAnalysisService,
    embedding: Optional[EmbeddingService] = None,
    schema_index: Optional[SchemaVectorIndex] = None,
    individual_index: Optional[IndividualVectorIndex] = None,
) -> list[_Tool]:
    """The seven read-only v1 tools, in the order offered to the model."""
    resolver = EntityResolver(ontology)
    return [
        SearchEntitiesTool(ontology, resolver, embedding, schema_index, individual_index),
        GetEntityTool(ontology, resolver),
        ListChildrenTool(ontology, resolver),
        ListRelationshipsTool(ontology, resolver),
        ListRelationshipTypesTool(ontology, resolver),
        GetNeighborsTool(ontology, resolver, graph),
        FindPathTool(ontology, resolver, graph),
    ]
