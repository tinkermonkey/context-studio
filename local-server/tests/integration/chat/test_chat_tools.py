"""
Integration tests for the chat tools over real SQLite repositories with a
DR-shaped workspace. Every entity in a result must carry id/kind/title, and the
outcome's entity refs must be exactly what the result shows.
"""

import json

import pytest

from adapters.chat.tools import MAX_RESULT_CHARS, MAX_VISION_CHARS, build_chat_tools
from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from domain.chat.value_objects import EntityRef
from domain.ontology.entities import Individual
from tests.integration.chat.conftest import (
    ADMIN_HEALTH_ID,
    API_SCHEME_ID,
    DR_VISION,
    HEALTH_MONITORING_ID,
    LIST_CLASSES_ID,
    OPERATION_ID,
    REALIZES_ID,
    SERVICE_CLASS_ID,
    TAXONOMY_ID,
)


@pytest.fixture
def tools(dr_workspace):
    return {t.spec.name: t for t in build_chat_tools(dr_workspace.ontology, dr_workspace.graph)}


async def call(tools, name, **args):
    outcome = await tools[name].execute(args)
    return outcome, json.loads(outcome.content)


def ref_ids(outcome):
    return {e.id for e in outcome.entities}


def test_read_tools_with_schemas(tools):
    assert list(tools) == [
        "list_taxonomies",
        "search_entities",
        "get_entity",
        "list_children",
        "list_relationships",
        "list_relationship_types",
        "get_neighbors",
        "find_path",
    ]
    for tool in tools.values():
        assert tool.spec.description
        assert tool.spec.input_schema["type"] == "object"


class TestSearchEntities:
    async def test_finds_class_by_title_with_parent(self, tools):
        outcome, result = await call(tools, "search_entities", query="Operation")

        first = result["results"][0]
        assert first == {
            "id": OPERATION_ID,
            "kind": "class",
            "title": "Operation",
            "score": 1.0,
            "parent_title": "API Layer",
        }
        assert EntityRef(OPERATION_ID, "class", "Operation") in outcome.entities
        assert not outcome.is_error

    async def test_kinds_filter_and_individual_parent(self, tools):
        outcome, result = await call(tools, "search_entities", query="health", kinds=["individual"])

        assert {r["id"] for r in result["results"]} == {ADMIN_HEALTH_ID, HEALTH_MONITORING_ID}
        assert {r["kind"] for r in result["results"]} == {"individual"}
        admin = next(r for r in result["results"] if r["id"] == ADMIN_HEALTH_ID)
        assert admin["parent_title"] == "Operation"
        assert ref_ids(outcome) == {ADMIN_HEALTH_ID, HEALTH_MONITORING_ID}

    async def test_finds_taxonomy_scheme_and_property(self, tools):
        _, taxonomy = await call(tools, "search_entities", query="Documentation")
        _, prop = await call(tools, "search_entities", query="realizes", kinds=["property"])

        assert taxonomy["results"][0]["kind"] == "taxonomy"
        assert prop["results"][0] == {
            "id": REALIZES_ID,
            "kind": "property",
            "title": "api.operation realizes business.service",
            "score": 0.9,
        }

    async def test_invalid_arguments_are_error_outcomes(self, tools):
        outcome, result = await call(tools, "search_entities", query="")
        assert outcome.is_error and "query" in result["error"]

        outcome, _ = await call(tools, "search_entities", query="x", kinds=["table"])
        assert outcome.is_error


class MappedEmbedding:
    """Deterministic embeddings: listed texts get fixed vectors, the rest are orthogonal."""

    VECTORS = {
        "Operation": [1.0, 0.0, 0.0],
        "An API operation (endpoint + method)": [1.0, 0.0, 0.0],
        "web endpoint": [0.95, 0.05, 0.0],
        "Admin Health": [0.0, 1.0, 0.0],
        "service status check": [0.0, 0.98, 0.1],
    }

    def embed(self, text):
        return self.VECTORS.get(text, [0.0, 0.0, 1.0])

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]

    def similarity(self, a, b):
        raise NotImplementedError


async def test_search_uses_vector_indexes_for_meaning(dr_workspace):
    embedding = MappedEmbedding()
    schema_index = SqliteSchemaVectorIndex(dr_workspace.session_factory, embedding)
    schema_index.reindex_all()
    individual_index = SqliteIndividualVectorIndex(dr_workspace.session_factory, embedding)
    individual_index.reindex_all_individuals()
    tools = {
        t.spec.name: t
        for t in build_chat_tools(
            dr_workspace.ontology,
            dr_workspace.graph,
            embedding=embedding,
            schema_index=schema_index,
            individual_index=individual_index,
        )
    }

    class_outcome, classes = await call(tools, "search_entities", query="web endpoint")
    _, individuals = await call(tools, "search_entities", query="service status check")

    assert classes["results"][0]["id"] == OPERATION_ID  # no title contains the query
    assert 0.9 < classes["results"][0]["score"] < 1.0
    assert OPERATION_ID in ref_ids(class_outcome)
    assert individuals["results"][0]["id"] == ADMIN_HEALTH_ID


class TestListTaxonomies:
    async def test_lists_taxonomies_with_summary_and_vision_flag(self, tools):
        outcome, result = await call(tools, "list_taxonomies")

        assert result["total"] == 1
        [taxonomy] = result["taxonomies"]
        assert taxonomy["id"] == TAXONOMY_ID and taxonomy["kind"] == "taxonomy"
        assert taxonomy["summary"] == "Architecture model layers"
        assert taxonomy["has_vision"] is True
        assert taxonomy["schemes"] == 2
        assert ref_ids(outcome) == {TAXONOMY_ID}


class TestGetEntity:
    async def test_taxonomy_details_include_vision(self, tools):
        outcome, result = await call(tools, "get_entity", id=TAXONOMY_ID)

        assert result["kind"] == "taxonomy"
        assert result["description"] == "Architecture model layers"
        assert result["vision"] == DR_VISION
        assert result["counts"]["schemes"] == 2
        assert ref_ids(outcome) == {TAXONOMY_ID}

    async def test_long_vision_is_capped_with_a_note(self, tools, dr_workspace):
        dr_workspace.ontology.update_taxonomy(TAXONOMY_ID, vision="x" * (MAX_VISION_CHARS + 500))

        _, result = await call(tools, "get_entity", id=TAXONOMY_ID)

        assert result["vision"].startswith("x" * MAX_VISION_CHARS)
        assert f"truncated at {MAX_VISION_CHARS}" in result["vision"]

    async def test_class_details(self, tools):
        outcome, result = await call(tools, "get_entity", id=OPERATION_ID)

        assert result["kind"] == "class" and result["identifier"] == "operation"
        assert result["description"] == "An API operation (endpoint + method)"
        assert [p["id"] for p in result["parents"]] == [API_SCHEME_ID, TAXONOMY_ID]
        assert result["counts"]["individuals"] == 2
        assert ref_ids(outcome) == {OPERATION_ID, API_SCHEME_ID, TAXONOMY_ID}

    async def test_individual_details(self, tools):
        outcome, result = await call(tools, "get_entity", id=ADMIN_HEALTH_ID)

        assert result["kind"] == "individual"
        assert result["classes"] == [{"id": OPERATION_ID, "kind": "class", "title": "Operation"}]
        assert result["counts"]["relationships_out"] == 1
        assert ref_ids(outcome) == {ADMIN_HEALTH_ID, OPERATION_ID}

    async def test_property_details(self, tools):
        _, result = await call(tools, "get_entity", id=REALIZES_ID)

        assert result["kind"] == "property"
        assert result["domain"][0]["id"] == OPERATION_ID
        assert result["range"][0]["id"] == SERVICE_CLASS_ID
        assert result["counts"]["relationships"] == 1

    async def test_unknown_id_is_error(self, tools):
        outcome, result = await call(tools, "get_entity", id="missing-id")

        assert outcome.is_error
        assert "missing-id" in result["error"]


class TestListChildren:
    async def test_taxonomy_schemes(self, tools):
        outcome, result = await call(tools, "list_children", id=TAXONOMY_ID)

        assert [i["title"] for i in result["items"]] == ["API Layer", "Business Layer"]
        assert result["total"] == 2
        assert {i["kind"] for i in result["items"]} == {"scheme"}
        assert TAXONOMY_ID in ref_ids(outcome)

    async def test_class_individuals_with_paging(self, tools):
        _, page_one = await call(tools, "list_children", id=OPERATION_ID, limit=1)
        _, page_two = await call(tools, "list_children", id=OPERATION_ID, limit=1, offset=1)

        assert page_one["total"] == 2
        assert [i["id"] for i in page_one["items"]] == [ADMIN_HEALTH_ID]
        assert [i["id"] for i in page_two["items"]] == [LIST_CLASSES_ID]

    async def test_individual_has_no_children(self, tools):
        outcome, result = await call(tools, "list_children", id=ADMIN_HEALTH_ID)

        assert outcome.is_error and "list_relationships" in result["error"]


class TestRelationships:
    async def test_list_relationships_both_directions(self, tools):
        out_outcome, outgoing = await call(
            tools, "list_relationships", entity_id=ADMIN_HEALTH_ID, direction="out"
        )
        _, incoming = await call(
            tools, "list_relationships", entity_id=ADMIN_HEALTH_ID, direction="in"
        )

        rel = outgoing["relationships"][0]
        assert rel["property"]["id"] == REALIZES_ID and rel["property"]["kind"] == "property"
        assert rel["source"]["id"] == ADMIN_HEALTH_ID
        assert rel["target"] == {
            "id": HEALTH_MONITORING_ID,
            "kind": "individual",
            "title": "Health Monitoring",
        }
        assert incoming["relationships"] == []
        assert ref_ids(out_outcome) == {ADMIN_HEALTH_ID, HEALTH_MONITORING_ID, REALIZES_ID}

    async def test_list_relationship_types(self, tools):
        outcome, result = await call(tools, "list_relationship_types", query="realizes")

        item = result["items"][0]
        assert item["id"] == REALIZES_ID
        assert item["domain"]["id"] == OPERATION_ID
        assert item["range"]["id"] == SERVICE_CLASS_ID
        assert ref_ids(outcome) == {REALIZES_ID, OPERATION_ID, SERVICE_CLASS_ID}


class TestGraphTools:
    async def test_neighbors(self, tools):
        outcome, result = await call(tools, "get_neighbors", id=ADMIN_HEALTH_ID)

        ids = {n["id"] for n in result["neighbors"]}
        assert {HEALTH_MONITORING_ID, OPERATION_ID} <= ids  # relationship + class membership
        assert ids <= ref_ids(outcome)

    async def test_find_path(self, tools):
        outcome, result = await call(
            tools, "find_path", source_id=ADMIN_HEALTH_ID, target_id=HEALTH_MONITORING_ID
        )

        assert [n["id"] for n in result["path"]] == [ADMIN_HEALTH_ID, HEALTH_MONITORING_ID]
        assert result["relationships"] == ["api.operation realizes business.service"]
        assert ref_ids(outcome) == {ADMIN_HEALTH_ID, HEALTH_MONITORING_ID}


async def test_long_results_are_truncated_to_valid_json(dr_workspace, tools):
    # Long titles make a 50-item result far larger than the cap
    for i in range(50):
        dr_workspace.repository.save_individual(
            Individual(
                id=f"ind-{i:03d}", class_ids=[OPERATION_ID], title=f"Endpoint {i} " + "x" * 120
            )
        )

    outcome, result = await call(tools, "list_children", id=OPERATION_ID, limit=50)

    assert len(outcome.content) <= MAX_RESULT_CHARS
    assert "truncated" in result
    assert ref_ids(outcome) == {OPERATION_ID, *(i["id"] for i in result["items"])}
