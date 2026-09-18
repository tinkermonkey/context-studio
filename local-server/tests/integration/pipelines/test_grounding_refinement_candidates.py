"""
Integration tests for Grounding and Refinement Candidate Endpoints.

Tests verify the grounding and refinement candidate endpoints correctly:
1. Map grounding and refinement data to GroundingCandidate and RefinementCandidate objects
2. Handle provenance normalization
3. Validate pipeline type (return 422 for wrong types)
4. Return 404 for missing runs
5. Return empty lists when output_summary lacks expected data keys
"""

import hashlib
from uuid import uuid4

import pytest
from starlette import status

from adapters.web.pipelines_routes import (
    _map_grounding_candidate,
    _map_refinement_candidate,
)
from adapters.web.schemas.pipelines import GroundingCandidate, RefinementCandidate


class TestGroundingCandidateMapping:
    """Tests for the _map_grounding_candidate function."""

    def test_map_grounding_candidate_basic(self):
        """Grounding dict with basic fields maps to GroundingCandidate."""
        grounding_dict = {
            "uri": "http://dbpedia.org/resource/Python_(programming_language)",
            "label": "Python Programming Language",
            "description": "A high-level programming language",
            "source": "DBpedia",
            "confidence": 0.92,
            "provenance": [],
        }

        result = _map_grounding_candidate(grounding_dict)

        assert isinstance(result, GroundingCandidate)
        assert result.candidate_type == "grounding"
        assert result.uri == "http://dbpedia.org/resource/Python_(programming_language)"
        assert result.label == "Python Programming Language"
        assert result.description == "A high-level programming language"
        assert result.source == "DBpedia"
        assert result.confidence == 0.92

    def test_map_grounding_candidate_with_provenance(self):
        """Grounding candidate with provenance list normalizes to SourceSpanSchema."""
        grounding_dict = {
            "uri": "http://dbpedia.org/resource/Alice",
            "label": "Alice",
            "description": "A person",
            "source": "Wikipedia",
            "confidence": 0.88,
            "provenance": [{"quote": "Alice is a person", "start": 0, "end": 17}],
        }

        result = _map_grounding_candidate(grounding_dict)

        assert len(result.provenance) == 1
        assert result.provenance[0].quote == "Alice is a person"
        assert result.provenance[0].start == 0
        assert result.provenance[0].end == 17

    def test_map_grounding_candidate_with_missing_fields(self):
        """Missing optional fields default gracefully."""
        grounding_dict = {
            "uri": "http://example.org/concept",
            "label": "Concept",
            # Missing description, source
        }

        result = _map_grounding_candidate(grounding_dict)

        assert result.uri == "http://example.org/concept"
        assert result.label == "Concept"
        assert result.description == ""
        assert result.source == ""
        assert result.confidence == 0.5  # Default
        assert result.provenance == []


class TestRefinementCandidateMapping:
    """Tests for the _map_refinement_candidate function."""

    def test_map_refinement_candidate_definition(self):
        """Definition refinement dict maps to RefinementCandidate."""
        refinement_dict = {
            "content": "An improved definition of the class",
            "scope_id": "class_123",
            "confidence": 0.87,
            "provenance": [],
        }

        result = _map_refinement_candidate(refinement_dict)

        assert isinstance(result, RefinementCandidate)
        assert result.candidate_type == "refinement"
        assert result.content == "An improved definition of the class"
        assert result.scope_id == "class_123"
        assert result.confidence == 0.87

    def test_map_refinement_candidate_connection(self):
        """Connection refinement dict maps to RefinementCandidate."""
        refinement_dict = {
            "content": "Subject -> improved_predicate -> Object",
            "scope_id": "connection_456",
            "confidence": 0.91,
            "provenance": [{"quote": "improved_predicate is better", "start": 10, "end": 38}],
        }

        result = _map_refinement_candidate(refinement_dict)

        assert result.content == "Subject -> improved_predicate -> Object"
        assert result.scope_id == "connection_456"
        assert result.confidence == 0.91
        assert len(result.provenance) == 1

    def test_map_refinement_candidate_with_missing_fields(self):
        """Missing optional fields default gracefully."""
        refinement_dict = {
            "content": "Refined content",
            # Missing scope_id
        }

        result = _map_refinement_candidate(refinement_dict)

        assert result.content == "Refined content"
        assert result.scope_id is None
        assert result.confidence == 0.5  # Default
        assert result.provenance == []


class TestSchemaCroundingCandidatesEndpoint:
    """Tests for GET /api/pipelines/runs/{run_id}/schema-grounding-candidates endpoint."""

    def test_schema_grounding_candidates_404_for_missing_run(self, client):
        """Returns 404 when run does not exist."""
        nonexistent_run_id = str(uuid4())
        response = client.get(
            f"/api/pipelines/runs/{nonexistent_run_id}/schema-grounding-candidates"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_schema_grounding_candidates_422_for_wrong_pipeline_type(
        self, client, pipeline_run_repo, batch_repo
    ):
        """Returns 422 when run is not schema_node_grounding type."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        # Create a no-op run (different pipeline type)
        batch = batch_repo.create()
        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.NO_OP,
            implementation_id="default",
            configuration_ref="noop-default",
            configuration_slug="noop-default",
            configuration_version=1,
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        # Call endpoint with wrong pipeline type
        response = client.get(
            f"/api/pipelines/runs/{run.id}/schema-grounding-candidates"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_schema_grounding_candidates_with_dbpedia_groundings(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /schema-grounding-candidates for SCHEMA_NODE_GROUNDING returns GroundingCandidate items."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        # Create a batch and run
        batch = batch_repo.create()
        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            implementation_id="default",
            configuration_ref="schema-grounding-default",
            configuration_slug="schema-grounding-default",
            configuration_version=1,
        )

        # Set output_summary with groundings from DBpedia
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={
                "groundings": [
                    {
                        "uri": "http://dbpedia.org/resource/Person",
                        "label": "Person",
                        "description": "A human being",
                        "source": "DBpedia",
                        "confidence": 0.95,
                        "provenance": [
                            {"quote": "A human being", "start": 0, "end": 13}
                        ],
                    },
                    {
                        "uri": "http://dbpedia.org/resource/Organization",
                        "label": "Organization",
                        "description": "An organized group of people",
                        "source": "DBpedia",
                        "confidence": 0.89,
                        "provenance": [
                            {
                                "quote": "An organized group of people",
                                "start": 0,
                                "end": 29,
                            }
                        ],
                    },
                ]
            },
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        # Call the endpoint
        response = client.get(
            f"/api/pipelines/runs/{run.id}/schema-grounding-candidates"
        )
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 2

        # Verify first grounding
        grounding1 = candidates[0]
        assert grounding1["candidate_type"] == "grounding"
        assert grounding1["uri"] == "http://dbpedia.org/resource/Person"
        assert grounding1["label"] == "Person"
        assert grounding1["description"] == "A human being"
        assert grounding1["source"] == "DBpedia"
        assert grounding1["confidence"] == 0.95
        assert len(grounding1["provenance"]) == 1
        assert grounding1["provenance"][0]["quote"] == "A human being"

        # Verify second grounding
        grounding2 = candidates[1]
        assert grounding2["uri"] == "http://dbpedia.org/resource/Organization"
        assert grounding2["label"] == "Organization"
        assert grounding2["confidence"] == 0.89

    def test_schema_grounding_candidates_with_wikidata_groundings(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /schema-grounding-candidates for Wikidata groundings returns GroundingCandidate items."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        batch = batch_repo.create()
        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            implementation_id="default",
            configuration_ref="schema-grounding-default",
            configuration_slug="schema-grounding-default",
            configuration_version=1,
        )

        # Set output_summary with Wikidata groundings
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={
                "groundings": [
                    {
                        "uri": "http://www.wikidata.org/entity/Q5",
                        "label": "Human",
                        "description": "Homo sapiens",
                        "source": "Wikidata",
                        "confidence": 0.98,
                        "provenance": [
                            {"quote": "Homo sapiens", "start": 0, "end": 12}
                        ],
                    }
                ]
            },
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        response = client.get(
            f"/api/pipelines/runs/{run.id}/schema-grounding-candidates"
        )
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert len(candidates) == 1
        assert candidates[0]["source"] == "Wikidata"
        assert candidates[0]["uri"] == "http://www.wikidata.org/entity/Q5"

    def test_schema_grounding_empty_groundings_returns_empty_list(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /schema-grounding-candidates with no groundings returns empty list."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        batch = batch_repo.create()
        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            implementation_id="default",
            configuration_ref="schema-grounding-default",
            configuration_slug="schema-grounding-default",
            configuration_version=1,
        )

        # Set output_summary with empty groundings
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={"groundings": []},
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        response = client.get(
            f"/api/pipelines/runs/{run.id}/schema-grounding-candidates"
        )
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 0


class TestSchemaRefinementCandidatesEndpoint:
    """Tests for GET /api/pipelines/runs/{run_id}/schema-refinement-candidates endpoint."""

    def test_schema_refinement_candidates_404_for_missing_run(self, client):
        """Returns 404 when run does not exist."""
        nonexistent_run_id = str(uuid4())
        response = client.get(
            f"/api/pipelines/runs/{nonexistent_run_id}/schema-refinement-candidates"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_schema_refinement_candidates_422_for_wrong_pipeline_type(
        self, client, pipeline_run_repo, batch_repo
    ):
        """Returns 422 when run is not a refinement type."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        # Create a no-op run (not a refinement type)
        batch = batch_repo.create()
        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.NO_OP,
            implementation_id="default",
            configuration_ref="noop-default",
            configuration_slug="noop-default",
            configuration_version=1,
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        # Call endpoint with wrong pipeline type
        response = client.get(
            f"/api/pipelines/runs/{run.id}/schema-refinement-candidates"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_schema_definition_refinement_candidates(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /schema-refinement-candidates for SCHEMA_NODE_DEFINITION_REFINEMENT returns RefinementCandidate items."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        # Create a batch and run for definition refinement
        batch = batch_repo.create()
        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            implementation_id="default",
            configuration_ref="schema-refinement-default",
            configuration_slug="schema-refinement-default",
            configuration_version=1,
        )

        # Set output_summary with refined definitions in "candidates" key
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={
                "candidates": [
                    {
                        "content": "An improved, more precise definition of the Person class",
                        "scope_id": "class_123",
                        "confidence": 0.92,
                        "provenance": [
                            {
                                "quote": "An improved, more precise definition",
                                "start": 0,
                                "end": 36,
                            }
                        ],
                    },
                    {
                        "content": "Alternative definition emphasizing human characteristics",
                        "scope_id": "class_123",
                        "confidence": 0.85,
                        "provenance": [
                            {
                                "quote": "Alternative definition",
                                "start": 0,
                                "end": 21,
                            }
                        ],
                    },
                ]
            },
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        # Call the endpoint
        response = client.get(
            f"/api/pipelines/runs/{run.id}/schema-refinement-candidates"
        )
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 2

        # Verify first refinement
        refinement1 = candidates[0]
        assert refinement1["candidate_type"] == "refinement"
        assert (
            refinement1["content"]
            == "An improved, more precise definition of the Person class"
        )
        assert refinement1["scope_id"] == "class_123"
        assert refinement1["confidence"] == 0.92
        assert len(refinement1["provenance"]) == 1

        # Verify second refinement
        refinement2 = candidates[1]
        assert (
            refinement2["content"]
            == "Alternative definition emphasizing human characteristics"
        )
        assert refinement2["confidence"] == 0.85

    def test_schema_connection_refinement_candidates(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /schema-refinement-candidates for SCHEMA_NODE_CONNECTION_REFINEMENT returns RefinementCandidate items."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        # Create a batch and run for connection refinement
        batch = batch_repo.create()
        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            implementation_id="default",
            configuration_ref="schema-refinement-default",
            configuration_slug="schema-refinement-default",
            configuration_version=1,
        )

        # Set output_summary with refined connections in "deltas" key
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={
                "deltas": [
                    {
                        "content": "Person -> improvedRelationship -> Organization",
                        "scope_id": "conn_456",
                        "confidence": 0.88,
                        "provenance": [
                            {
                                "quote": "improvedRelationship",
                                "start": 9,
                                "end": 29,
                            }
                        ],
                    },
                    {
                        "content": "Person -> betterPredicate -> Company",
                        "scope_id": "conn_456",
                        "confidence": 0.82,
                        "provenance": [],
                    },
                ]
            },
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        # Call the endpoint
        response = client.get(
            f"/api/pipelines/runs/{run.id}/schema-refinement-candidates"
        )
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 2

        # Verify first connection refinement
        delta1 = candidates[0]
        assert delta1["candidate_type"] == "refinement"
        assert delta1["content"] == "Person -> improvedRelationship -> Organization"
        assert delta1["scope_id"] == "conn_456"
        assert delta1["confidence"] == 0.88

        # Verify second connection refinement
        delta2 = candidates[1]
        assert delta2["content"] == "Person -> betterPredicate -> Company"
        assert delta2["confidence"] == 0.82

    def test_schema_refinement_empty_candidates_returns_empty_list(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /schema-refinement-candidates with no candidates/deltas returns empty list."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        batch = batch_repo.create()
        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            implementation_id="default",
            configuration_ref="schema-refinement-default",
            configuration_slug="schema-refinement-default",
            configuration_version=1,
        )

        # Set output_summary with empty candidates
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={"candidates": []},
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        response = client.get(
            f"/api/pipelines/runs/{run.id}/schema-refinement-candidates"
        )
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 0
