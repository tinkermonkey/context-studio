"""
Phase 2: End-to-end verification of concept-object typing through recognition and apply.

Verifies that a pass-2-introduced concept-object survives the full pipeline:
- typed via range-class inference (`_type_concept_objects`)
- resolved or minted through the existing recognition cascade (`_recognize_individuals`)
- persisted as a relationship through the unmodified apply service
- including cross-document/cross-run deduplication behavior

Tests cover both extraction modes (`_extract_triples_two_pass` and
`_extract_triples_nlp_grounded`) to ensure identical behavior.
"""

import inspect
import logging
import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.services import ExtractionService
from domain.interchange.services import set_batch_run_context
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.services import OntologyService
from domain.pipelines.entities import IndividualExtractionRun, PipelineRunStatus
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource


@pytest.fixture
def temp_db():
    """Create a temporary in-memory SQLite database for integration tests."""
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    return create_session_factory(temp_db)


@pytest.fixture
def event_publisher():
    """Create an in-process event publisher."""
    return InProcessEventPublisher()


@pytest.fixture
def ontology_repo(session_factory):
    """Create an ontology repository instance."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def embedding_service():
    """Create a fake embedding service."""
    return FakeEmbeddingService()


@pytest.fixture
def individual_index(session_factory, embedding_service):
    """Create an individual vector index."""
    return SqliteIndividualVectorIndex(session_factory, embedding_service)


@pytest.fixture
def ontology_service(ontology_repo, embedding_service, event_publisher):
    """Create the ontology service with all dependencies."""
    return OntologyService(ontology_repo, embedding_service, event_publisher, schema_index=None)


@pytest.fixture
def extraction_service(ontology_repo, embedding_service, individual_index):
    """Create an extraction service with fake providers."""
    return ExtractionService(
        ontology_repo=ontology_repo,
        embedding_service=embedding_service,
        llm=FakeLLMProvider(),
        nlp=FakeNLPProcessor(),
        reference_sources=[FakeReferenceSource()],
        event_publisher=InProcessEventPublisher(),
        extraction_repo=None,
        extraction_run_repo=None,
        individual_index=individual_index,
    )


@pytest.fixture
def ontology_with_properties(ontology_repo):
    """
    Create a test ontology with classes and property definitions.

    Structure:
    - Quality class (range for "improves" predicate)
    - Performance class (range for "optimizes" predicate)
    - Pattern class
    - PropertyDefinition "improves" with range_class_id = Quality
    - PropertyDefinition "optimizes" with range_class_id = Performance
    """
    tax = Taxonomy(
        id=str(uuid4()),
        identifier="test_ontology",
        title="Test Ontology",
        description="Test ontology for concept-object typing",
    )
    ontology_repo.save_taxonomy(tax)

    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="test_scheme",
        taxonomy_id=tax.id,
        title="Test Scheme",
        description="Test concept scheme",
    )
    ontology_repo.save_concept_scheme(scheme)

    # Create classes
    quality_class = Class(
        id=str(uuid4()),
        identifier="quality",
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Quality Attribute",
        description="A quality attribute",
    )
    ontology_repo.save_class(quality_class)

    performance_class = Class(
        id=str(uuid4()),
        identifier="performance",
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Performance",
        description="Performance characteristic",
    )
    ontology_repo.save_class(performance_class)

    pattern_class = Class(
        id=str(uuid4()),
        identifier="pattern",
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Design Pattern",
        description="A design pattern",
    )
    ontology_repo.save_class(pattern_class)

    # Create property definitions with range classes
    improves_prop = PropertyDefinition(
        id=str(uuid4()),
        identifier="improves",
        title="improves",
        canonical_predicate="improves",
        domain_class_id=pattern_class.id,
        range_class_id=quality_class.id,
    )
    ontology_repo.save_property_definition(improves_prop)

    optimizes_prop = PropertyDefinition(
        id=str(uuid4()),
        identifier="optimizes",
        title="optimizes",
        canonical_predicate="optimizes",
        domain_class_id=pattern_class.id,
        range_class_id=performance_class.id,
    )
    ontology_repo.save_property_definition(optimizes_prop)

    # Property without range (for negative testing)
    relates_prop = PropertyDefinition(
        id=str(uuid4()),
        identifier="relates",
        title="relates",
        canonical_predicate="relates",
        domain_class_id=pattern_class.id,
        range_class_id=None,  # No range class
    )
    ontology_repo.save_property_definition(relates_prop)

    return {
        "taxonomy": tax,
        "scheme": scheme,
        "quality_class": quality_class,
        "performance_class": performance_class,
        "pattern_class": pattern_class,
        "improves_prop": improves_prop,
        "optimizes_prop": optimizes_prop,
        "relates_prop": relates_prop,
    }


class TestConceptObjectTypingFullPipeline:
    """Integration tests for concept-object typing through the full pipeline."""

    def test_concept_object_typed_recognized_and_applied(
        self,
        extraction_service,
        ontology_repo,
        ontology_service,
        individual_index,
        ontology_with_properties,
    ):
        """
        Requirement: Concept-object with resolvable predicate range -> synthetic is_a
        -> recognition resolves or creates individual -> relationship persisted.

        Scenario:
        1. Relationship triple with concept-object "readability" (no id, not in pass-1)
        2. PropertyDefinition "improves" has range_class_id = Quality
        3. _type_concept_objects emits synthetic is_a triple
        4. _recognize_individuals creates new Individual with Quality class
        5. apply() persists the relationship
        """
        tax = ontology_with_properties["taxonomy"]
        pattern_class = ontology_with_properties["pattern_class"]
        quality_class = ontology_with_properties["quality_class"]
        improves_prop = ontology_with_properties["improves_prop"]

        # Create a pattern individual in pass-1
        pattern_individual_triples = [
            {
                "subject": {
                    "kind": "individual",
                    "id": None,
                    "label": "Decorator Pattern",
                    "class_ids": [str(pattern_class.id)],
                },
                "predicate": {"property_definition_id": None, "label": "is_a"},
                "object": {
                    "kind": "class",
                    "id": str(pattern_class.id),
                    "label": pattern_class.title,
                },
                "confidence": 0.9,
                "provenance": {"raw": "test"},
            }
        ]

        # Pass-2 relationship with concept-object "readability"
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Decorator Pattern"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "readability"},
                "confidence": 0.85,
                "provenance": {"raw": "test"},
            }
        ]

        # Step 1: Type concept objects - emits synthetic is_a triple
        all_relationship_triples = extraction_service._type_concept_objects(
            relationship_triples, pattern_individual_triples, tax
        )

        assert len(all_relationship_triples) == 2, (
            "Should have synthetic is_a + relationship"
        )
        typing_triple = all_relationship_triples[0]
        relationship_triple = all_relationship_triples[1]

        # Verify synthetic is_a triple was emitted
        assert typing_triple["predicate"]["label"] == "is_a"
        assert typing_triple["subject"]["label"] == "readability"
        assert typing_triple["subject"]["class_ids"] == [str(quality_class.id)]
        assert typing_triple["object"]["id"] == str(quality_class.id)

        # Verify property_definition_id was stamped on relationship
        assert (
            relationship_triple["predicate"]["property_definition_id"]
            == str(improves_prop.id)
        )

        # Step 2: Recognition step
        combined_triples = pattern_individual_triples + all_relationship_triples
        recognized_triples = extraction_service._recognize_individuals(combined_triples, tax)

        # Find the typing and relationship triples after recognition
        typing_triple_after = next(
            (
                t
                for t in recognized_triples
                if t["predicate"]["label"] == "is_a"
                and t["subject"]["label"] == "readability"
            ),
            None,
        )
        assert typing_triple_after is not None
        # Verify typing triple retained synthetic properties through recognition
        assert typing_triple_after["predicate"]["label"] == "is_a"
        assert typing_triple_after["subject"]["label"] == "readability"
        assert typing_triple_after["subject"]["class_ids"] == [str(quality_class.id)]
        assert typing_triple_after["object"]["id"] == str(quality_class.id)

        relationship_triple_after = next(
            (t for t in recognized_triples if t["predicate"]["label"] == "improves"),
            None,
        )
        assert relationship_triple_after is not None
        # Verify relationship triple retained property definition through recognition
        assert relationship_triple_after["predicate"]["label"] == "improves"
        assert (
            relationship_triple_after["predicate"]["property_definition_id"]
            == str(improves_prop.id)
        )
        assert relationship_triple_after["subject"]["label"] == "Decorator Pattern"
        assert relationship_triple_after["object"]["label"] == "readability"

        # Pattern should be resolved (id will be assigned during create)
        pattern_after = next(
            (
                t
                for t in recognized_triples
                if t["subject"]["label"] == "Decorator Pattern"
                and t["predicate"]["label"] == "is_a"
            ),
            None,
        )
        assert pattern_after is not None
        assert pattern_after["subject"]["id"] is None  # Not yet resolved (no existing individual)

        # Step 3: Apply all triples in a single call (synthetic triples come first)
        run_id = str(uuid4())
        set_batch_run_context(run_id)

        try:
            # Single apply call with all recognized triples
            run = IndividualExtractionRun(
                id=run_id,
                batch_run_id=run_id,
                implementation_id="default",
                configuration_slug="extraction-default",
                configuration_version=1,
                status=PipelineRunStatus.COMPLETED,
                output_summary={"triples": recognized_triples},
            )

            apply_service = IndividualExtractionApplyService(ontology_service, ontology_repo)
            apply_result = apply_service.apply(run)

            # Verify both individuals and relationships were created
            assert apply_result.individuals_created >= 2, (
                f"Pattern and readability individuals created (result: {apply_result})"
            )
            assert apply_result.relationships_created >= 1, (
                f"Relationship created (result: {apply_result})"
            )

            # Verify relationship was created with correct property
            created_relationships = ontology_repo.list_relationships(limit=None)
            improves_relationships = [
                r
                for r in created_relationships
                if r.property_definition_id == str(improves_prop.id)
            ]
            assert len(improves_relationships) >= 1, "improves relationship created"

        finally:
            set_batch_run_context(None)

    def test_concept_object_deduplicates_existing_individual(
        self,
        extraction_service,
        ontology_repo,
        ontology_service,
        individual_index,
        ontology_with_properties,
    ):
        """
        Requirement: Concept-object that already exists as an Individual
        -> recognition resolves to existing node -> no duplicate Individual created.

        Scenario:
        1. Existing Individual "readability" with Quality class (from prior extraction)
        2. New pass-2 relationship emits concept-object "readability"
        3. Recognition resolves to existing node
        4. apply() uses existing node id, no new Individual created
        """
        tax = ontology_with_properties["taxonomy"]
        pattern_class = ontology_with_properties["pattern_class"]
        quality_class = ontology_with_properties["quality_class"]
        improves_prop = ontology_with_properties["improves_prop"]

        # Pre-create an existing Individual "readability" with Quality class
        existing_readability = Individual(
            id=str(uuid4()),
            class_ids=[str(quality_class.id)],
            title="readability",
        )
        ontology_repo.save_individual(existing_readability)
        individual_index.index_individual(
            existing_readability.id, existing_readability.title, None
        )

        # Pattern individual in pass-1
        pattern_individual_triples = [
            {
                "subject": {
                    "kind": "individual",
                    "id": None,
                    "label": "Caching",
                    "class_ids": [str(pattern_class.id)],
                },
                "predicate": {"property_definition_id": None, "label": "is_a"},
                "object": {
                    "kind": "class",
                    "id": str(pattern_class.id),
                    "label": pattern_class.title,
                },
                "confidence": 0.9,
                "provenance": {"raw": "test"},
            }
        ]

        # Pass-2 relationship with concept-object "readability" (existing)
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Caching"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "readability"},
                "confidence": 0.85,
                "provenance": {"raw": "test"},
            }
        ]

        # Type concept objects
        all_relationship_triples = extraction_service._type_concept_objects(
            relationship_triples, pattern_individual_triples, tax
        )

        # Recognition should resolve "readability" to existing node
        combined_triples = pattern_individual_triples + all_relationship_triples
        recognized_triples = extraction_service._recognize_individuals(combined_triples, tax)

        # Find the readability typing triple after recognition
        readability_triple = next(
            (
                t
                for t in recognized_triples
                if t["predicate"]["label"] == "is_a"
                and t["subject"]["label"] == "readability"
            ),
            None,
        )

        # Readability should be resolved to existing node
        assert readability_triple is not None
        assert readability_triple["subject"]["id"] == existing_readability.id
        assert readability_triple["subject"]["label"] == "readability"

        # Count existing individuals
        individuals_before = len(ontology_repo.list_individuals(limit=None))

        # Apply all triples in a single call (synthetic triples come first)
        run_id = str(uuid4())
        set_batch_run_context(run_id)

        try:
            run = IndividualExtractionRun(
                id=run_id,
                batch_run_id=run_id,
                implementation_id="default",
                configuration_slug="extraction-default",
                configuration_version=1,
                status=PipelineRunStatus.COMPLETED,
                output_summary={"triples": recognized_triples},
            )

            apply_service = IndividualExtractionApplyService(ontology_service, ontology_repo)
            apply_result = apply_service.apply(run)

            individuals_after = len(ontology_repo.list_individuals(limit=None))

            # Only pattern individual should be created, readability reused
            # We expect: pattern individual created (1) + no new readability (0)
            new_individuals = individuals_after - individuals_before
            assert new_individuals == 1, (
                f"Only pattern individual created, readability reused "
                f"(got {new_individuals} new)"
            )

            # Verify relationship was created with existing readability
            relationships = ontology_repo.list_relationships(limit=None)
            improves_relationships = [
                r
                for r in relationships
                if r.property_definition_id == str(improves_prop.id)
            ]
            assert len(improves_relationships) >= 1, "improves relationship created"

            # Verify relationship points to existing node
            improves_rel = improves_relationships[0]
            assert improves_rel.target_id == existing_readability.id, (
                "Relationship points to existing readability individual"
            )

        finally:
            set_batch_run_context(None)

    def test_concept_object_untyped_skipped(
        self,
        extraction_service,
        ontology_repo,
        ontology_service,
        ontology_with_properties,
        caplog,
    ):
        """
        Requirement: Concept-object with no resolvable predicate range
        -> skip behavior matches today's untyped-object behavior -> observable/distinguishable.

        Scenario:
        1. PropertyDefinition "relates" has no range_class_id
        2. Pass-2 emits concept-object with predicate "relates"
        3. _type_concept_objects does NOT emit is_a triple (no range)
        4. Concept-object stays untyped and invisible to recognition
        5. apply() skips the relationship (no property_definition_id check) or logs it
        """
        tax = ontology_with_properties["taxonomy"]
        pattern_class = ontology_with_properties["pattern_class"]
        relates_prop = ontology_with_properties["relates_prop"]

        pattern_individual_triples = [
            {
                "subject": {
                    "kind": "individual",
                    "id": None,
                    "label": "Pattern",
                    "class_id": str(pattern_class.id),
                },
                "predicate": {"property_definition_id": None, "label": "is_a"},
                "object": {
                    "kind": "class",
                    "id": str(pattern_class.id),
                    "label": pattern_class.title,
                },
                "confidence": 0.9,
                "provenance": {"raw": "test"},
            }
        ]

        # Pass-2 relationship with concept-object, predicate has no range
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Pattern"},
                "predicate": {"property_definition_id": None, "label": "relates"},
                "object": {"kind": "individual", "label": "unknown_entity"},
                "confidence": 0.85,
                "provenance": {"raw": "test"},
            }
        ]

        # Type concept objects - should NOT emit is_a for "relates"
        with caplog.at_level(logging.INFO):
            all_relationship_triples = extraction_service._type_concept_objects(
                relationship_triples, pattern_individual_triples, tax
            )

        # Should only have the relationship, no synthetic is_a
        assert len(all_relationship_triples) == 1
        assert all_relationship_triples[0]["predicate"]["label"] == "relates"

        # Verify log message indicates no range_class_id
        assert "declares no range_class_id" in caplog.text

        # Verify property_definition_id was still stamped
        assert (
            all_relationship_triples[0]["predicate"]["property_definition_id"]
            == str(relates_prop.id)
        )

    def test_concept_object_unresolved_predicate_skipped(
        self,
        extraction_service,
        ontology_repo,
        ontology_service,
        ontology_with_properties,
        caplog,
    ):
        """
        Requirement: Concept-object with no resolvable PropertyDefinition
        -> skip behavior distinguished from typed-but-unranged case.

        Scenario:
        1. Pass-2 emits concept-object with unknown predicate
        2. PropertyDefinition not found in ontology
        3. _type_concept_objects does NOT emit is_a triple
        4. Concept-object stays untyped
        """
        tax = ontology_with_properties["taxonomy"]
        pattern_class = ontology_with_properties["pattern_class"]

        pattern_individual_triples = [
            {
                "subject": {
                    "kind": "individual",
                    "id": None,
                    "label": "Pattern",
                    "class_id": str(pattern_class.id),
                },
                "predicate": {"property_definition_id": None, "label": "is_a"},
                "object": {
                    "kind": "class",
                    "id": str(pattern_class.id),
                    "label": pattern_class.title,
                },
                "confidence": 0.9,
                "provenance": {"raw": "test"},
            }
        ]

        # Pass-2 relationship with unknown predicate
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Pattern"},
                "predicate": {"property_definition_id": None, "label": "unknown_predicate"},
                "object": {"kind": "individual", "label": "unknown_entity"},
                "confidence": 0.85,
                "provenance": {"raw": "test"},
            }
        ]

        # Type concept objects - should NOT emit is_a
        with caplog.at_level(logging.INFO):
            all_relationship_triples = extraction_service._type_concept_objects(
                relationship_triples, pattern_individual_triples, tax
            )

        # Should only have the relationship, no synthetic is_a
        assert len(all_relationship_triples) == 1
        assert all_relationship_triples[0]["predicate"]["label"] == "unknown_predicate"

        # Verify log message indicates PropertyDefinition not found
        assert "PropertyDefinition not found" in caplog.text

        # property_definition_id should NOT be stamped (no property found)
        assert not all_relationship_triples[0]["predicate"].get("property_definition_id")

    def test_both_extraction_modes_identical_behavior(
        self, extraction_service, ontology_repo, ontology_with_properties
    ):
        """
        Requirement: Both _extract_triples_two_pass and _extract_triples_nlp_grounded
        exhibit identical concept-object behavior.

        This test verifies that both call sites use the same insertion point
        (_type_concept_objects) and therefore produce identical results by
        inspecting their source code for the shared call.
        """
        # Structural test: Verify both extraction modes call _type_concept_objects
        two_pass_source = inspect.getsource(
            extraction_service._extract_triples_two_pass
        )
        nlp_grounded_source = inspect.getsource(
            extraction_service._extract_triples_nlp_grounded
        )

        # Both methods must contain the _type_concept_objects call
        assert "_type_concept_objects" in two_pass_source, (
            "_extract_triples_two_pass must call _type_concept_objects"
        )
        assert "_type_concept_objects" in nlp_grounded_source, (
            "_extract_triples_nlp_grounded must call _type_concept_objects"
        )

        # Behavioral test: Verify shared _type_concept_objects produces correct output
        tax = ontology_with_properties["taxonomy"]
        pattern_class = ontology_with_properties["pattern_class"]
        improves_prop = ontology_with_properties["improves_prop"]

        pattern_individual_triples = [
            {
                "subject": {
                    "kind": "individual",
                    "id": None,
                    "label": "DecoratorPattern",
                    "class_ids": [str(pattern_class.id)],
                },
                "predicate": {"property_definition_id": None, "label": "is_a"},
                "object": {
                    "kind": "class",
                    "id": str(pattern_class.id),
                    "label": pattern_class.title,
                },
                "confidence": 0.9,
                "provenance": {"raw": "test"},
            }
        ]

        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "DecoratorPattern"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "readability"},
                "confidence": 0.85,
                "provenance": {"raw": "test"},
            }
        ]

        # Call _type_concept_objects as both modes do
        result = extraction_service._type_concept_objects(
            relationship_triples, pattern_individual_triples, tax
        )

        # Both modes should produce the same output
        # With new triple ordering: synthetic is_a triples come first
        assert len(result) == 2
        assert result[0]["predicate"]["label"] == "is_a"
        assert result[0]["subject"]["label"] == "readability"
        assert result[1]["predicate"]["property_definition_id"] == str(improves_prop.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
