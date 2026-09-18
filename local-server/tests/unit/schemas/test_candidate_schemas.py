"""
Unit tests for candidate response schemas and discriminated union.

Tests validate:
- Serialization/deserialization of each candidate variant
- Discriminated union routing via candidate_type
- Provenance round-trip (SourceSpanSchema)
- Type validation and required fields
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from adapters.web.schemas.pipelines import (
    CandidateItem,
    CandidateResponse,
    GroundingCandidate,
    NodeReference,
    PredicateReference,
    RefinementCandidate,
    SchemaClassCandidate,
    SchemaConnectionCandidate,
    SchemaPropertyCandidate,
    SourceSpanSchema,
    TripleCandidate,
)

candidate_adapter: TypeAdapter[CandidateItem] = TypeAdapter(CandidateItem)


class TestSourceSpanSchema:
    """Tests for SourceSpanSchema value object."""

    def test_fully_resolved_span(self):
        """SourceSpanSchema with all fields populated."""
        span = SourceSpanSchema(quote="Technology System", start=0, end=19)
        assert span.quote == "Technology System"
        assert span.start == 0
        assert span.end == 19

    def test_quote_only_span(self):
        """SourceSpanSchema with quote but no offsets."""
        span = SourceSpanSchema(quote="Microservice", start=None, end=None)
        assert span.quote == "Microservice"
        assert span.start is None
        assert span.end is None

    def test_unresolved_span(self):
        """SourceSpanSchema with all fields None."""
        span = SourceSpanSchema(quote=None, start=None, end=None)
        assert span.quote is None
        assert span.start is None
        assert span.end is None

    def test_span_from_dict(self):
        """SourceSpanSchema can be instantiated from dict."""
        data = {"quote": "Test", "start": 5, "end": 9}
        span = SourceSpanSchema(**data)
        assert span.quote == "Test"
        assert span.start == 5
        assert span.end == 9

    def test_span_model_dump(self):
        """SourceSpanSchema serializes to dict correctly."""
        span = SourceSpanSchema(quote="Test", start=0, end=4)
        dumped = span.model_dump()
        assert dumped == {"quote": "Test", "start": 0, "end": 4}


class TestSchemaClassCandidate:
    """Tests for SchemaClassCandidate variant."""

    def test_minimal_schema_class_candidate(self):
        """SchemaClassCandidate with required fields only."""
        candidate = SchemaClassCandidate(
            label="Example Class",
            confidence=0.95,
        )
        assert candidate.candidate_type == "schema_class"
        assert candidate.label == "Example Class"
        assert candidate.confidence == 0.95
        assert candidate.proposed_definition is None
        assert candidate.provenance == []

    def test_schema_class_candidate_with_provenance(self):
        """SchemaClassCandidate with provenance spans."""
        candidate = SchemaClassCandidate(
            label="Example Class",
            proposed_definition="A test class",
            confidence=0.9,
            provenance=[
                SourceSpanSchema(quote="Example Class", start=0, end=14),
            ],
        )
        assert len(candidate.provenance) == 1
        assert candidate.provenance[0].quote == "Example Class"
        assert candidate.provenance[0].start == 0
        assert candidate.provenance[0].end == 14
        assert candidate.proposed_definition == "A test class"

    def test_schema_class_candidate_from_dict(self):
        """SchemaClassCandidate can be instantiated from dict."""
        data = {
            "candidate_type": "schema_class",
            "label": "Test Class",
            "confidence": 0.85,
        }
        candidate = SchemaClassCandidate(**data)
        assert candidate.candidate_type == "schema_class"
        assert candidate.label == "Test Class"

    def test_schema_class_candidate_model_dump(self):
        """SchemaClassCandidate serializes correctly."""
        candidate = SchemaClassCandidate(
            label="Test Class",
            proposed_definition="A class for testing",
            confidence=0.95,
            provenance=[SourceSpanSchema(quote="Test", start=0, end=4)],
        )
        dumped = candidate.model_dump()
        assert dumped["candidate_type"] == "schema_class"
        assert dumped["label"] == "Test Class"
        assert dumped["proposed_definition"] == "A class for testing"
        assert len(dumped["provenance"]) == 1
        assert dumped["provenance"][0]["quote"] == "Test"


class TestSchemaPropertyCandidate:
    """Tests for SchemaPropertyCandidate variant."""

    def test_schema_property_candidate(self):
        """SchemaPropertyCandidate with required fields."""
        candidate = SchemaPropertyCandidate(
            label="has_name",
            proposed_definition="Relates an entity to its name",
            proposed_domain="Entity",
            proposed_range="String",
            confidence=0.88,
        )
        assert candidate.candidate_type == "schema_property"
        assert candidate.label == "has_name"
        assert candidate.proposed_definition == "Relates an entity to its name"
        assert candidate.proposed_domain == "Entity"
        assert candidate.proposed_range == "String"


class TestSchemaConnectionCandidate:
    """Tests for SchemaConnectionCandidate variant."""

    def test_schema_connection_candidate(self):
        """SchemaConnectionCandidate representing a proposed relationship."""
        candidate = SchemaConnectionCandidate(
            subject_ref="Class1",
            predicate="relatedTo",
            object_ref="Class2",
            confidence=0.82,
        )
        assert candidate.candidate_type == "schema_connection"
        assert candidate.subject_ref == "Class1"
        assert candidate.predicate == "relatedTo"
        assert candidate.object_ref == "Class2"


class TestNodeAndPredicateReferences:
    """Tests for NodeReference and PredicateReference."""

    def test_node_reference(self):
        """NodeReference represents an extracted node."""
        node = NodeReference(label="Technology", kind="individual")
        assert node.label == "Technology"
        assert node.kind == "individual"

    def test_predicate_reference(self):
        """PredicateReference represents a predicate/property."""
        pred = PredicateReference(label="is_a", kind="property")
        assert pred.label == "is_a"
        assert pred.kind == "property"


class TestTripleCandidate:
    """Tests for TripleCandidate variant."""

    def test_minimal_triple_candidate(self):
        """TripleCandidate with required fields only."""
        candidate = TripleCandidate(
            subject=NodeReference(label="Technology", kind="individual"),
            predicate=PredicateReference(label="is_a", kind="property"),
            object=NodeReference(label="System", kind="class"),
            confidence=0.92,
        )
        assert candidate.candidate_type == "triple"
        assert candidate.subject.label == "Technology"
        assert candidate.predicate.label == "is_a"
        assert candidate.object.label == "System"

    def test_triple_candidate_with_provenance(self):
        """TripleCandidate with provenance spans."""
        candidate = TripleCandidate(
            subject=NodeReference(label="Technology", kind="individual"),
            predicate=PredicateReference(label="is_a", kind="property"),
            object=NodeReference(label="System", kind="class"),
            confidence=0.92,
            provenance=[
                SourceSpanSchema(quote="Technology System", start=0, end=18),
            ],
        )
        assert len(candidate.provenance) == 1
        assert candidate.provenance[0].quote == "Technology System"

    def test_triple_candidate_from_dict(self):
        """TripleCandidate can be instantiated from dict."""
        data = {
            "candidate_type": "triple",
            "subject": {"label": "Technology", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "System", "kind": "class"},
            "confidence": 0.92,
        }
        candidate = TripleCandidate(**data)
        assert candidate.candidate_type == "triple"
        assert candidate.subject.label == "Technology"


class TestGroundingCandidate:
    """Tests for GroundingCandidate variant."""

    def test_grounding_candidate(self):
        """GroundingCandidate links to external knowledge."""
        candidate = GroundingCandidate(
            uri="http://dbpedia.org/resource/Technology",
            label="Technology (DBpedia)",
            description="Wikipedia article on technology",
            source="DBpedia",
            confidence=0.89,
        )
        assert candidate.candidate_type == "grounding"
        assert candidate.uri == "http://dbpedia.org/resource/Technology"
        assert candidate.source == "DBpedia"


class TestRefinementCandidate:
    """Tests for RefinementCandidate variant."""

    def test_refinement_candidate(self):
        """RefinementCandidate for definition refinement."""
        candidate = RefinementCandidate(
            uri="class-123",
            label="Refined Class",
            description="A refined definition of the concept",
            source="refinement_pipeline",
            confidence=0.87,
        )
        assert candidate.candidate_type == "refinement"
        assert candidate.uri == "class-123"
        assert candidate.label == "Refined Class"
        assert candidate.description == "A refined definition of the concept"
        assert candidate.source == "refinement_pipeline"

    def test_refinement_candidate_minimal(self):
        """RefinementCandidate with minimal required fields."""
        candidate = RefinementCandidate(
            uri="entity-456",
            label="Refined Definition",
            confidence=0.85,
        )
        assert candidate.uri == "entity-456"
        assert candidate.label == "Refined Definition"
        assert candidate.description == ""
        assert candidate.source == ""


class TestDiscriminatedUnion:
    """Tests for CandidateItem discriminated union."""

    def test_discriminate_schema_class(self):
        """CandidateItem correctly deserializes SchemaClassCandidate."""
        data = {
            "candidate_type": "schema_class",
            "label": "Test Class",
            "proposed_definition": "A class for testing",
            "confidence": 0.95,
        }
        candidate = candidate_adapter.validate_python(data)
        assert isinstance(candidate, SchemaClassCandidate)
        assert candidate.candidate_type == "schema_class"

    def test_discriminate_schema_property(self):
        """CandidateItem correctly deserializes SchemaPropertyCandidate."""
        data = {
            "candidate_type": "schema_property",
            "label": "has_name",
            "proposed_definition": "Relates an entity to its name",
            "confidence": 0.88,
        }
        candidate = candidate_adapter.validate_python(data)
        assert isinstance(candidate, SchemaPropertyCandidate)

    def test_discriminate_schema_connection(self):
        """CandidateItem correctly deserializes SchemaConnectionCandidate."""
        data = {
            "candidate_type": "schema_connection",
            "subject_ref": "Class1",
            "predicate": "relatedTo",
            "object_ref": "Class2",
            "confidence": 0.82,
        }
        candidate = candidate_adapter.validate_python(data)
        assert isinstance(candidate, SchemaConnectionCandidate)

    def test_discriminate_triple(self):
        """CandidateItem correctly deserializes TripleCandidate."""
        data = {
            "candidate_type": "triple",
            "subject": {"label": "Technology", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "System", "kind": "class"},
            "confidence": 0.92,
        }
        candidate = candidate_adapter.validate_python(data)
        assert isinstance(candidate, TripleCandidate)

    def test_discriminate_grounding(self):
        """CandidateItem correctly deserializes GroundingCandidate."""
        data = {
            "candidate_type": "grounding",
            "uri": "http://dbpedia.org/resource/Technology",
            "label": "Technology",
            "confidence": 0.89,
        }
        candidate = candidate_adapter.validate_python(data)
        assert isinstance(candidate, GroundingCandidate)

    def test_discriminate_refinement(self):
        """CandidateItem correctly deserializes RefinementCandidate."""
        data = {
            "candidate_type": "refinement",
            "uri": "class-123",
            "label": "Refined Definition",
            "description": "A refined definition",
            "source": "refinement_pipeline",
            "confidence": 0.87,
        }
        candidate = candidate_adapter.validate_python(data)
        assert isinstance(candidate, RefinementCandidate)

    def test_union_list_of_mixed_types(self):
        """CandidateItem list can contain mixed candidate types."""
        data = [
            {
                "candidate_type": "schema_class",
                "uri": "http://example.org/Class",
                "label": "Test Class",
                "confidence": 0.95,
            },
            {
                "candidate_type": "triple",
                "subject": {"label": "Technology", "kind": "individual"},
                "predicate": {"label": "is_a", "kind": "property"},
                "object": {"label": "System", "kind": "class"},
                "confidence": 0.92,
            },
            {
                "candidate_type": "grounding",
                "uri": "http://dbpedia.org/resource/Technology",
                "label": "Technology",
                "confidence": 0.89,
            },
        ]

        candidates = [candidate_adapter.validate_python(d) for d in data]
        assert len(candidates) == 3
        assert isinstance(candidates[0], SchemaClassCandidate)
        assert isinstance(candidates[1], TripleCandidate)
        assert isinstance(candidates[2], GroundingCandidate)


class TestLegacyCandidateResponse:
    """Tests for legacy CandidateResponse (backwards compatibility)."""

    def test_legacy_candidate_response(self):
        """Legacy CandidateResponse still works for backwards compatibility."""
        candidate = CandidateResponse(
            uri="http://example.org/Resource",
            label="Test Resource",
            description="A test resource",
            source="External DB",
            confidence=0.85,
            provenance="Found via semantic search",
        )
        assert candidate.uri == "http://example.org/Resource"
        assert candidate.provenance == "Found via semantic search"

    def test_legacy_candidate_response_minimal(self):
        """Legacy CandidateResponse with minimal required fields."""
        candidate = CandidateResponse(
            uri="http://example.org/Resource",
            label="Test",
            confidence=0.8,
        )
        assert candidate.uri == "http://example.org/Resource"
        assert candidate.description == ""


class TestProvenanceRoundTrip:
    """Tests for provenance serialization/deserialization round-trip."""

    def test_class_candidate_provenance_round_trip(self):
        """SchemaClassCandidate provenance survives round-trip."""
        original = SchemaClassCandidate(
            label="Test Class",
            proposed_definition="A test class",
            confidence=0.95,
            provenance=[
                SourceSpanSchema(quote="Test Class", start=0, end=10),
                SourceSpanSchema(quote="Class", start=None, end=None),
            ],
        )

        dumped = original.model_dump()
        restored = SchemaClassCandidate(**dumped)

        assert restored.label == original.label
        assert len(restored.provenance) == 2
        assert restored.provenance[0].quote == "Test Class"
        assert restored.provenance[0].start == 0
        assert restored.provenance[1].quote == "Class"
        assert restored.provenance[1].start is None

    def test_triple_candidate_provenance_round_trip(self):
        """TripleCandidate provenance survives round-trip."""
        original = TripleCandidate(
            subject=NodeReference(label="Technology", kind="individual"),
            predicate=PredicateReference(label="is_a", kind="property"),
            object=NodeReference(label="System", kind="class"),
            confidence=0.92,
            provenance=[
                SourceSpanSchema(quote="Technology System", start=0, end=18),
            ],
        )

        dumped = original.model_dump()
        restored = TripleCandidate(**dumped)

        assert restored.subject.label == original.subject.label
        assert restored.confidence == original.confidence
        assert restored.provenance[0].quote == "Technology System"

    def test_discriminated_union_provenance_round_trip(self):
        """Discriminated union provenance survives round-trip."""
        data = {
            "candidate_type": "schema_class",
            "uri": "http://example.org/Class",
            "label": "Test Class",
            "confidence": 0.95,
            "provenance": [
                {"quote": "Test", "start": 0, "end": 4},
            ],
        }

        candidate1 = candidate_adapter.validate_python(data)
        dumped = candidate_adapter.dump_python(candidate1)
        candidate2 = candidate_adapter.validate_python(dumped)

        assert isinstance(candidate2, SchemaClassCandidate)
        assert candidate2.provenance[0].quote == "Test"


class TestFieldValidation:
    """Tests for field validation and constraints."""

    def test_confidence_bounds(self):
        """Confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            SchemaClassCandidate(
                uri="http://example.org/Class",
                label="Test",
                confidence=1.5,
            )

        with pytest.raises(ValidationError):
            SchemaClassCandidate(
                uri="http://example.org/Class",
                label="Test",
                confidence=-0.1,
            )

    def test_span_offsets_non_negative(self):
        """Span offsets must be non-negative."""
        with pytest.raises(ValidationError):
            SourceSpanSchema(quote="Test", start=-1, end=4)

        with pytest.raises(ValidationError):
            SourceSpanSchema(quote="Test", start=0, end=-1)

    def test_required_fields(self):
        """Required fields cannot be omitted."""
        with pytest.raises(ValidationError):
            SchemaClassCandidate(confidence=0.9)

        with pytest.raises(ValidationError):
            TripleCandidate(
                subject=NodeReference(label="Tech", kind="individual"),
                predicate=PredicateReference(label="is_a", kind="property"),
                confidence=0.92,
            )

    def test_candidate_type_field_immutable(self):
        """candidate_type field value is enforced by Literal."""
        data = {
            "candidate_type": "invalid_type",
            "uri": "http://example.org/Class",
            "label": "Test",
            "confidence": 0.95,
        }
        with pytest.raises(ValidationError):
            SchemaClassCandidate(**data)
