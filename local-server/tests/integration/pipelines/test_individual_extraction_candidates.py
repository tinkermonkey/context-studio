"""
Unit tests for Phase 3: Individual Extraction Structured Triples Candidates.

Tests verify the TripleCandidate mapping function handles the correct schema
and data transformation. Integration tests that create actual individual_extraction
runs are tested separately (in test_individual_extraction_structural.py).

Tests verify:
1. _map_triple_candidate converts raw dict to TripleCandidate with correct schema
2. TripleCandidate has structured subject/predicate/object with NodeReference sub-objects
3. Mapped nodes have non-empty id; new nodes have empty/None id
4. Provenance normalized to SourceSpanSchema format
5. Literal objects with kind=literal, value, datatype are supported
"""

import hashlib
from uuid import uuid4

import pytest
from starlette import status

from adapters.web.pipelines_routes import _map_triple_candidate
from adapters.web.schemas.pipelines import (
    NodeReference,
    PredicateReference,
    TripleCandidate,
)


class TestTripleCandidateMapping:
    """Tests for the _map_triple_candidate function."""

    def test_map_triple_candidate_with_mapped_nodes(self):
        """Triple with mapped subject and object produces NodeReference with non-empty id."""
        triple_dict = {
            "subject": {
                "kind": "individual",
                "id": "john_doe",
                "label": "John Doe",
                "class_ids": ["person"]
            },
            "predicate": {
                "property_definition_id": "works_for",
                "label": "works for"
            },
            "object": {
                "kind": "individual",
                "id": "acme_corp",
                "label": "ACME Corp",
                "class_ids": ["organization"]
            },
            "confidence": 0.95,
            "provenance": []
        }

        result = _map_triple_candidate(triple_dict)

        # Verify result is TripleCandidate
        assert isinstance(result, TripleCandidate)
        assert result.candidate_type == "triple"

        # Verify subject
        assert isinstance(result.subject, NodeReference)
        assert result.subject.kind == "individual"
        assert result.subject.label == "John Doe"
        assert result.subject.id == "john_doe"  # Mapped
        assert result.subject.class_ids == ["person"]

        # Verify predicate
        assert isinstance(result.predicate, PredicateReference)
        assert result.predicate.label == "works for"
        assert result.predicate.property_definition_id == "works_for"  # Mapped

        # Verify object
        assert isinstance(result.object, NodeReference)
        assert result.object.kind == "individual"
        assert result.object.label == "ACME Corp"
        assert result.object.id == "acme_corp"  # Mapped
        assert result.object.class_ids == ["organization"]

        # Verify confidence
        assert result.confidence == 0.95

    def test_map_triple_candidate_with_new_nodes(self):
        """Triple with new (unmapped) nodes produces NodeReference with None id."""
        triple_dict = {
            "subject": {
                "kind": "individual",
                "label": "Jane Smith"
            },
            "predicate": {
                "label": "manages"
            },
            "object": {
                "kind": "individual",
                "label": "Project X"
            },
            "confidence": 0.85,
            "provenance": []
        }

        result = _map_triple_candidate(triple_dict)

        # Verify subject (new)
        assert result.subject.kind == "individual"
        assert result.subject.label == "Jane Smith"
        assert result.subject.id is None  # New node

        # Verify predicate (new)
        assert result.predicate.label == "manages"
        assert result.predicate.property_definition_id is None  # New predicate

        # Verify object (new)
        assert result.object.kind == "individual"
        assert result.object.label == "Project X"
        assert result.object.id is None  # New node

    def test_map_triple_candidate_with_literal_object(self):
        """Triple with literal object has kind=literal, value, datatype."""
        triple_dict = {
            "subject": {
                "kind": "individual",
                "id": "person_1",
                "label": "John Doe"
            },
            "predicate": {
                "property_definition_id": "age",
                "label": "has age"
            },
            "object": {
                "kind": "literal",
                "value": "30",
                "datatype": "integer"
            },
            "confidence": 0.99,
            "provenance": []
        }

        result = _map_triple_candidate(triple_dict)

        # Verify object is literal
        assert result.object.kind == "literal"
        assert result.object.value == "30"
        assert result.object.datatype == "integer"
        # Literals should not have id/label from mapping
        assert result.object.id is None

    def test_map_triple_candidate_with_provenance_dict_in_list(self):
        """Provenance as list with dict containing text_offset_start/end/raw normalized to SourceSpanSchema."""
        triple_dict = {
            "subject": {
                "kind": "individual",
                "id": "john",
                "label": "John"
            },
            "predicate": {
                "property_definition_id": "works_for",
                "label": "works for"
            },
            "object": {
                "kind": "individual",
                "id": "acme",
                "label": "ACME"
            },
            "confidence": 0.9,
            "provenance": [
                {
                    "text_offset_start": 0,
                    "text_offset_end": 25,
                    "raw": "John works for ACME Corp"
                }
            ]
        }

        result = _map_triple_candidate(triple_dict)

        # Verify provenance is normalized
        assert len(result.provenance) == 1
        span = result.provenance[0]
        assert span.quote == "John works for ACME Corp"
        assert span.start == 0
        assert span.end == 25

    def test_map_triple_candidate_with_provenance_list(self):
        """Provenance as list of dicts normalized to SourceSpanSchema list."""
        triple_dict = {
            "subject": {"kind": "individual", "id": "s1", "label": "Subject"},
            "predicate": {"label": "relates_to"},
            "object": {"kind": "individual", "id": "o1", "label": "Object"},
            "confidence": 0.8,
            "provenance": [
                {"quote": "first occurrence", "start": 0, "end": 16},
                {"quote": "second occurrence", "start": 30, "end": 47}
            ]
        }

        result = _map_triple_candidate(triple_dict)

        assert len(result.provenance) == 2
        assert result.provenance[0].quote == "first occurrence"
        assert result.provenance[0].start == 0
        assert result.provenance[1].quote == "second occurrence"
        assert result.provenance[1].start == 30

    def test_map_triple_candidate_confidence_bounds(self):
        """Confidence validates as float between 0.0-1.0; out-of-bounds values are rejected."""
        triple_dict = {
            "subject": {"kind": "individual", "id": "s", "label": "S"},
            "predicate": {"label": "p"},
            "object": {"kind": "individual", "id": "o", "label": "O"},
            "confidence": 0.5,
            "provenance": []
        }

        result = _map_triple_candidate(triple_dict)
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    def test_map_triple_candidate_confidence_out_of_bounds_rejected(self):
        """Confidence value outside 0.0-1.0 is rejected with ValidationError."""
        triple_dict = {
            "subject": {"kind": "individual", "id": "s", "label": "S"},
            "predicate": {"label": "p"},
            "object": {"kind": "individual", "id": "o", "label": "O"},
            "confidence": 1.5,  # Out of bounds
            "provenance": []
        }

        # Pydantic's ge=0.0, le=1.0 constraint rejects out-of-bounds values
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            _map_triple_candidate(triple_dict)

    def test_map_triple_candidate_with_missing_fields(self):
        """Missing optional fields default gracefully."""
        # Minimal triple with only required fields
        triple_dict = {
            "subject": {"kind": "individual", "label": "Subject"},
            "predicate": {"label": "predicate"},
            "object": {"kind": "individual", "label": "Object"},
            # No confidence, provenance
        }

        result = _map_triple_candidate(triple_dict)

        # Should default confidence to 0.5
        assert result.confidence == 0.5

        # Should have empty provenance list
        assert result.provenance == []

        # Unmapped nodes should have None id
        assert result.subject.id is None
        assert result.object.id is None
        assert result.predicate.property_definition_id is None

    def test_map_triple_candidate_empty_dict_values(self):
        """Empty/None dict values handled gracefully."""
        triple_dict = {
            "subject": None,  # None dict
            "predicate": {},  # Empty dict
            "object": {"kind": "individual", "label": "O"},
            "confidence": 0.7,
            "provenance": None  # None provenance
        }

        result = _map_triple_candidate(triple_dict)

        # Should handle gracefully
        assert result.subject.label == ""  # Default from missing label
        assert result.predicate.label == ""  # Default from missing label
        assert result.object.label == "O"
        assert result.confidence == 0.7
        assert result.provenance == []


class TestIndividualExtractionCandidatesEndpoint:
    """Tests for GET /api/pipelines/runs/{run_id}/candidates endpoint."""

    def test_no_op_run_returns_empty_candidates(self, client):
        """No-op pipeline run returns empty candidate list."""
        create_response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "text": "Sample text",
                "ontology_id": "test-ontology",
                "implementation_id": "default",
                "configuration_ref": "noop-default",
            },
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        run_id = create_response.json()["id"]

        response = client.get(f"/api/pipelines/runs/{run_id}/candidates")
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 0

    def test_candidates_endpoint_404_for_missing_run(self, client):
        """Returns 404 when run does not exist."""
        nonexistent_run_id = str(uuid4())
        response = client.get(f"/api/pipelines/runs/{nonexistent_run_id}/candidates")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_individual_extraction_candidates_with_mapped_nodes(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /candidates for INDIVIDUAL_EXTRACTION run returns TripleCandidate items with mapped nodes."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        # Create a batch and run
        batch = batch_repo.create()
        source_text = "John Doe works for ACME Corp"
        source_text_hash = hashlib.sha256(source_text.encode()).hexdigest()

        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="default",
            configuration_ref="individual-extraction-default",
            configuration_slug="individual-extraction-default",
            configuration_version=1,
            specific_data={"source_text_hash": source_text_hash},
        )

        # Set output_summary with triples containing mapped nodes
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={
                "triples": [
                    {
                        "subject": {
                            "kind": "individual",
                            "id": "john_doe",
                            "label": "John Doe",
                            "class_ids": ["person"]
                        },
                        "predicate": {
                            "property_definition_id": "works_for",
                            "label": "works for"
                        },
                        "object": {
                            "kind": "individual",
                            "id": "acme_corp",
                            "label": "ACME Corp",
                            "class_ids": ["organization"]
                        },
                        "confidence": 0.95,
                        "provenance": [
                            {
                                "quote": "John Doe works for ACME Corp",
                                "start": 0,
                                "end": 30
                            }
                        ]
                    }
                ]
            },
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        # Call the endpoint
        response = client.get(f"/api/pipelines/runs/{run.id}/candidates")
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 1

        # Verify TripleCandidate structure
        triple = candidates[0]
        assert triple["candidate_type"] == "triple"

        # Verify subject (mapped)
        assert triple["subject"]["kind"] == "individual"
        assert triple["subject"]["id"] == "john_doe"
        assert triple["subject"]["label"] == "John Doe"
        assert triple["subject"]["class_ids"] == ["person"]

        # Verify predicate (mapped)
        assert triple["predicate"]["property_definition_id"] == "works_for"
        assert triple["predicate"]["label"] == "works for"

        # Verify object (mapped)
        assert triple["object"]["kind"] == "individual"
        assert triple["object"]["id"] == "acme_corp"
        assert triple["object"]["label"] == "ACME Corp"
        assert triple["object"]["class_ids"] == ["organization"]

        # Verify confidence and provenance
        assert triple["confidence"] == 0.95
        assert len(triple["provenance"]) == 1
        assert triple["provenance"][0]["quote"] == "John Doe works for ACME Corp"
        assert triple["provenance"][0]["start"] == 0
        assert triple["provenance"][0]["end"] == 30

    def test_individual_extraction_candidates_with_new_nodes(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /candidates for INDIVIDUAL_EXTRACTION run returns TripleCandidate items with new (unmapped) nodes."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        # Create a batch and run
        batch = batch_repo.create()
        source_text = "Jane Smith manages Project Alpha"
        source_text_hash = hashlib.sha256(source_text.encode()).hexdigest()

        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="default",
            configuration_ref="individual-extraction-default",
            configuration_slug="individual-extraction-default",
            configuration_version=1,
            specific_data={"source_text_hash": source_text_hash},
        )

        # Set output_summary with triples containing new (unmapped) nodes
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={
                "triples": [
                    {
                        "subject": {
                            "kind": "individual",
                            "label": "Jane Smith"
                        },
                        "predicate": {
                            "label": "manages"
                        },
                        "object": {
                            "kind": "individual",
                            "label": "Project Alpha"
                        },
                        "confidence": 0.85,
                        "provenance": [
                            {
                                "quote": "Jane Smith manages Project Alpha",
                                "start": 0,
                                "end": 32
                            }
                        ]
                    }
                ]
            },
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        # Call the endpoint
        response = client.get(f"/api/pipelines/runs/{run.id}/candidates")
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 1

        # Verify TripleCandidate structure with new nodes
        triple = candidates[0]
        assert triple["candidate_type"] == "triple"

        # Verify subject (new - no id)
        assert triple["subject"]["kind"] == "individual"
        assert triple["subject"]["id"] is None
        assert triple["subject"]["label"] == "Jane Smith"

        # Verify predicate (new - no property_definition_id)
        assert triple["predicate"]["property_definition_id"] is None
        assert triple["predicate"]["label"] == "manages"

        # Verify object (new - no id)
        assert triple["object"]["kind"] == "individual"
        assert triple["object"]["id"] is None
        assert triple["object"]["label"] == "Project Alpha"

        # Verify confidence and provenance
        assert triple["confidence"] == 0.85
        assert len(triple["provenance"]) == 1
        assert triple["provenance"][0]["quote"] == "Jane Smith manages Project Alpha"

    def test_individual_extraction_empty_triples_returns_empty_list(
        self, client, pipeline_run_repo, batch_repo
    ):
        """GET /candidates for INDIVIDUAL_EXTRACTION run with no triples returns empty list."""
        from domain.pipelines.entities import PipelineRunStatus, PipelineType

        # Create a batch and run
        batch = batch_repo.create()
        source_text = "Test text"
        source_text_hash = hashlib.sha256(source_text.encode()).hexdigest()

        run = pipeline_run_repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="default",
            configuration_ref="individual-extraction-default",
            configuration_slug="individual-extraction-default",
            configuration_version=1,
            specific_data={"source_text_hash": source_text_hash},
        )

        # Set output_summary with empty triples
        pipeline_run_repo.update_summaries(
            run.id,
            output_summary={"triples": []},
        )
        pipeline_run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)

        # Call the endpoint
        response = client.get(f"/api/pipelines/runs/{run.id}/candidates")
        assert response.status_code == status.HTTP_200_OK

        candidates = response.json()
        assert isinstance(candidates, list)
        assert len(candidates) == 0

