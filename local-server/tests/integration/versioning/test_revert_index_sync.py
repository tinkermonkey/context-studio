"""
Integration tests: reverting a run restores entities exactly and keeps the
recognition and schema indexes in sync (#1293, #1295).

Real SQLite with the real SqliteIndividualVectorIndex and SqliteSchemaVectorIndex,
an in-process event publisher wired to the ChangeEventRecorder, the real
individual-extraction apply service and recognizer, and the RevertService wired
as in app.py. Embeddings come from the deterministic FakeEmbeddingService, so an
identical text scores ~1.0 and anything else scores lower.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from adapters.recognition.individual_recognizer import CascadeIndividualRecognizer
from domain.interchange.services import set_batch_run_context
from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.events import (
    AttributeDefinitionDeleted,
    ClassDeleted,
    ClassUpdated,
    IndividualCreated,
    IndividualDeleted,
    IndividualUpdated,
    PropertyDefinitionDeleted,
    RelationshipCreated,
    RelationshipDeleted,
)
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import (
    DataPropertyValue,
    DataType,
    ExternalReference,
    LexicalSense,
    Status,
)
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.parent_rows import create_batch_row

TAXONOMY_ID = "tx-idx"
SCHEME_ID = "cs-idx"
CLASS_ID = "cls-org"
OTHER_CLASS_ID = "cls-other"
PROP_ID = "prop-link"
SAME_TEXT = 0.999


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def embedding():
    return FakeEmbeddingService()


@pytest.fixture()
def ontology_repo(session_factory):
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    repo.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="idx_tax", title="Idx Taxonomy"))
    repo.save_concept_scheme(
        ConceptScheme(id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, identifier="idx_scheme", title="Idx")
    )
    repo.save_class(
        Class(
            id=CLASS_ID,
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="organization",
            title="Organization",
            description="A group of people with a shared purpose.",
        )
    )
    return repo


@pytest.fixture()
def change_repo(session_factory):
    return SQLiteChangeRepository(session_factory=session_factory)


@pytest.fixture()
def pipeline_repo(session_factory):
    return PipelineRepository(session_factory=session_factory)


@pytest.fixture()
def individual_index(session_factory, embedding):
    return SqliteIndividualVectorIndex(session_factory, embedding)


@pytest.fixture()
def schema_index(session_factory, embedding):
    return SqliteSchemaVectorIndex(session_factory, embedding)


@pytest.fixture()
def ontology_service(ontology_repo, change_repo, embedding, schema_index, individual_index):
    publisher = InProcessEventPublisher()
    recorder = ChangeEventRecorder(change_repo)
    publisher.subscribe(IndividualCreated, recorder.on_individual_created)
    publisher.subscribe(IndividualUpdated, recorder.on_individual_updated)
    publisher.subscribe(IndividualDeleted, recorder.on_individual_deleted)
    publisher.subscribe(ClassUpdated, recorder.on_class_updated)
    publisher.subscribe(ClassDeleted, recorder.on_class_deleted)
    publisher.subscribe(AttributeDefinitionDeleted, recorder.on_attribute_definition_deleted)
    publisher.subscribe(PropertyDefinitionDeleted, recorder.on_property_definition_deleted)
    publisher.subscribe(RelationshipCreated, recorder.on_relationship_created)
    publisher.subscribe(RelationshipDeleted, recorder.on_relationship_deleted)
    return OntologyService(
        repository=ontology_repo,
        embedding_service=embedding,
        event_publisher=publisher,
        schema_index=schema_index,
        individual_index=individual_index,
    )


@pytest.fixture()
def recognizer(individual_index, embedding):
    return CascadeIndividualRecognizer(
        individual_index=individual_index, embedding_service=embedding
    )


@pytest.fixture()
def revert_service(change_repo, ontology_repo, schema_index, individual_index):
    return RevertService(
        change_repo=change_repo,
        ontology_repo=ontology_repo,
        schema_index=schema_index,
        individual_index=individual_index,
    )


def _new_run(pipeline_repo, output_summary=None):
    run = pipeline_repo.create(
        batch_run_id=create_batch_row(pipeline_repo._session_factory),
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        implementation_id="default",
        configuration_ref="extraction-default",
        configuration_slug="extraction-default",
        configuration_version=1,
        specific_data={"source_text_hash": "abc123"},
    )
    pipeline_repo.update_status(run.id, PipelineRunStatus.COMPLETED)
    if output_summary is not None:
        pipeline_repo.update_summaries(run.id, output_summary=output_summary)
    return pipeline_repo.get(run.id)


def _org_triple(label):
    return {
        "subject": {"kind": "individual", "id": "", "label": label, "class_ids": [CLASS_ID]},
        "predicate": {"property_definition_id": None, "label": "is_a"},
        "object": {"kind": "class", "id": CLASS_ID, "label": "organization"},
        "confidence": 0.9,
    }


def _in_run(run_id, write):
    """Perform a write with its change events tagged with the run, as the apply route does."""
    set_batch_run_context(run_id)
    try:
        return write()
    finally:
        set_batch_run_context(None)


def _individual_hits(individual_index, embedding, text):
    return [
        m.individual_id
        for m in individual_index.search(embedding.embed(text), [CLASS_ID], threshold=SAME_TEXT)
    ]


def _schema_hits(schema_index, embedding, text, kind):
    return [
        m.entity_id
        for m in schema_index.search(embedding.embed(text), kinds=[kind], threshold=SAME_TEXT)
    ]


def test_reverted_individuals_are_not_recognized_by_a_fresh_run(
    pipeline_repo, ontology_repo, ontology_service, recognizer, revert_service
):
    """Apply a run that creates individuals, revert it, and recognize the same mentions again."""
    run = _new_run(pipeline_repo, {"triples": [_org_triple("Globex"), _org_triple("Initech")]})
    apply_svc = IndividualExtractionApplyService(ontology_service, ontology_repo, recognizer)
    result = _in_run(run.id, lambda: apply_svc.apply(run=run))
    assert len(result.created_individual_ids) == 2
    assert recognizer.recognize("Globex", "", [CLASS_ID]) is not None

    revert_service.revert_with_summary(run.id)

    assert recognizer.recognize("Globex", "", [CLASS_ID]) is None
    assert recognizer.recognize("Initech", "", [CLASS_ID]) is None


def test_reverted_individual_update_restores_its_embedding(
    pipeline_repo, ontology_service, individual_index, schema_index, embedding, revert_service
):
    """Reverting a rename makes the old title searchable again and the new one stop matching."""
    original = ontology_service.create_individual(
        title="Acme Corp", class_ids=[CLASS_ID], description="Maker of anvils."
    )
    run = _new_run(pipeline_repo)
    _in_run(
        run.id,
        lambda: ontology_service.update_individual(
            original.id, title="Acme Rocket Works", description="Maker of rockets."
        ),
    )
    assert _individual_hits(individual_index, embedding, "Acme Rocket Works") == [original.id]

    revert_service.revert_with_summary(run.id)

    assert _individual_hits(individual_index, embedding, "Acme Corp") == [original.id]
    assert _individual_hits(individual_index, embedding, "Acme Rocket Works") == []
    assert _schema_hits(schema_index, embedding, "Maker of anvils.", "individual") == [original.id]


def test_reverted_class_definition_update_restores_its_embedding(
    pipeline_repo, ontology_service, schema_index, embedding, revert_service
):
    """Reverting a definition refinement makes the original definition drive retrieval again."""
    original_definition = "A group of people with a shared purpose."
    run = _new_run(pipeline_repo)
    _in_run(
        run.id,
        lambda: ontology_service.update_class(CLASS_ID, description="A registered company."),
    )
    assert _schema_hits(schema_index, embedding, "A registered company.", "class") == [CLASS_ID]

    revert_service.revert_with_summary(run.id)

    assert _schema_hits(schema_index, embedding, original_definition, "class") == [CLASS_ID]
    assert _schema_hits(schema_index, embedding, "A registered company.", "class") == []


def test_reverted_individual_delete_is_recognizable_again(
    pipeline_repo, ontology_service, recognizer, individual_index, embedding, revert_service
):
    """An individual restored by a revert is back in the recognition index."""
    original = ontology_service.create_individual(title="Umbrella Corp", class_ids=[CLASS_ID])
    run = _new_run(pipeline_repo)
    _in_run(run.id, lambda: ontology_service.delete_individual(original.id))
    assert recognizer.recognize("Umbrella Corp", "", [CLASS_ID]) is None

    revert_service.revert_with_summary(run.id)

    assert _individual_hits(individual_index, embedding, "Umbrella Corp") == [original.id]
    match = recognizer.recognize("Umbrella Corp", "", [CLASS_ID])
    assert match is not None and match.individual_id == original.id


def _relationship_fields(relationships):
    return sorted((r.id, r.source_id, r.target_id, r.property_definition_id) for r in relationships)


def _without_bookkeeping(entity):
    """Entity fields minus the ones a save always resets (timestamps, version)."""
    return replace(entity, created_at=None, last_modified=None, version=1)


def test_delete_then_revert_restores_individual_exactly_with_its_relationships(
    pipeline_repo,
    ontology_repo,
    ontology_service,
    individual_index,
    schema_index,
    embedding,
    revert_service,
):
    """create -> delete -> revert round-trips the individual and its cascaded relationships."""
    ontology_repo.save_class(
        Class(
            id=OTHER_CLASS_ID,
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="company",
            title="Company",
        )
    )
    ontology_repo.save_property_definition(
        PropertyDefinition(id=PROP_ID, identifier="partners_with", title="partners with")
    )
    ontology_repo.save_individual(
        Individual(
            id="ind-acme",
            class_ids=[CLASS_ID, OTHER_CLASS_ID],
            title="Acme Corp",
            description="Maker of anvils.",
            data_properties=[
                DataPropertyValue("founded", 1949, "xsd:integer"),
                DataPropertyValue("public", True),
            ],
            external_references=[
                ExternalReference(
                    source="wikidata",
                    identifier="Q123",
                    uri="https://www.wikidata.org/wiki/Q123",
                    metadata=MappingProxyType({"label": "Acme"}),
                )
            ],
            status=Status.PUBLISHED,
        )
    )
    individual_index.index_individual("ind-acme", "Acme Corp", "Maker of anvils.")
    partner = ontology_service.create_individual(title="Globex", class_ids=[CLASS_ID])
    ontology_service.create_relationship("ind-acme", partner.id, PROP_ID)
    ontology_service.create_relationship(partner.id, "ind-acme", PROP_ID)
    before = ontology_repo.get_individual("ind-acme")
    relationships_before = ontology_repo.list_relationships(
        source_id="ind-acme", limit=None
    ) + ontology_repo.list_relationships(target_id="ind-acme", limit=None)
    assert len(relationships_before) == 2

    run = _new_run(pipeline_repo)
    _in_run(run.id, lambda: ontology_service.delete_individual("ind-acme"))
    assert ontology_repo.get_individual("ind-acme") is None
    assert ontology_repo.list_relationships(source_id=partner.id, limit=None) == []

    result = revert_service.revert_with_summary(run.id)

    assert result.entities_restored == 3
    after = ontology_repo.get_individual("ind-acme")
    assert after is not None
    assert _without_bookkeeping(after) == _without_bookkeeping(before)
    relationships_after = ontology_repo.list_relationships(
        source_id="ind-acme", limit=None
    ) + ontology_repo.list_relationships(target_id="ind-acme", limit=None)
    assert _relationship_fields(relationships_after) == _relationship_fields(relationships_before)
    assert _individual_hits(individual_index, embedding, "Acme Corp") == ["ind-acme"]
    assert _schema_hits(schema_index, embedding, "Maker of anvils.", "individual") == ["ind-acme"]


def test_delete_then_revert_restores_class_exactly_with_its_relationships(
    pipeline_repo, ontology_repo, ontology_service, schema_index, embedding, revert_service
):
    """
    create -> delete -> revert round-trips a class plus the relationships and
    attribute definitions deleted with it. Undo runs newest first, so the class
    is restored before the attribute definitions and relationships that need it.
    """
    ontology_repo.save_property_definition(
        PropertyDefinition(id=PROP_ID, identifier="supplies", title="supplies")
    )
    ontology_repo.save_class(
        Class(
            id=OTHER_CLASS_ID,
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="supplier",
            title="Supplier",
            description="Provides goods to an organization.",
            color="#aabbcc",
            parent_class_id=CLASS_ID,
            external_references=[ExternalReference(source="wikidata", identifier="Q7")],
            lexical_senses=[LexicalSense("supplier", "en", "synset")],
            data_properties=[DataPropertyValue("tier", 1)],
            status=Status.PUBLISHED,
        )
    )
    ontology_service.create_relationship(OTHER_CLASS_ID, CLASS_ID, PROP_ID)
    ontology_repo.save_attribute_definition(
        AttributeDefinition(
            id="attr-tier",
            class_id=OTHER_CLASS_ID,
            identifier="tier",
            title="Tier",
            datatype=DataType.INTEGER,
            description="Supplier tier.",
            is_required=True,
            default_value="1",
            sort_order=2,
            external_references=[ExternalReference(source="dr", identifier="tier")],
            status=Status.PUBLISHED,
        )
    )
    ontology_repo.save_attribute_definition(
        AttributeDefinition(
            id="attr-region",
            class_id=OTHER_CLASS_ID,
            identifier="region",
            title="Region",
            datatype=DataType.STRING,
            allowed_values=["emea", "apac"],
        )
    )
    before = ontology_repo.get_class(OTHER_CLASS_ID)
    relationships_before = ontology_repo.list_relationships(source_id=OTHER_CLASS_ID, limit=None)
    attributes_before = ontology_repo.list_attribute_definitions(
        class_id=OTHER_CLASS_ID, limit=None
    )
    assert len(attributes_before) == 2

    run = _new_run(pipeline_repo)
    _in_run(run.id, lambda: ontology_service.delete_class(OTHER_CLASS_ID))
    assert ontology_repo.get_class(OTHER_CLASS_ID) is None
    assert ontology_repo.get_attribute_definition("attr-tier") is None

    result = revert_service.revert_with_summary(run.id)

    assert result.entities_restored == 4
    attributes_after = ontology_repo.list_attribute_definitions(class_id=OTHER_CLASS_ID, limit=None)
    assert sorted(map(_without_bookkeeping, attributes_after), key=lambda a: a.id) == sorted(
        map(_without_bookkeeping, attributes_before), key=lambda a: a.id
    )

    after = ontology_repo.get_class(OTHER_CLASS_ID)
    assert after is not None
    assert _without_bookkeeping(after) == _without_bookkeeping(before)
    relationships_after = ontology_repo.list_relationships(source_id=OTHER_CLASS_ID, limit=None)
    assert _relationship_fields(relationships_after) == _relationship_fields(relationships_before)
    assert _schema_hits(schema_index, embedding, "Provides goods to an organization.", "class") == [
        OTHER_CLASS_ID
    ]


def test_delete_then_revert_restores_property_definition_exactly(
    pipeline_repo, ontology_repo, ontology_service, schema_index, embedding, revert_service
):
    """create -> delete -> revert round-trips a property definition."""
    ontology_repo.save_property_definition(
        PropertyDefinition(
            id=PROP_ID,
            identifier="employs",
            title="employs",
            description="Has as an employee.",
            canonical_predicate="employs",
            domain_class_id=CLASS_ID,
            range_class_id=CLASS_ID,
            external_references=[ExternalReference(source="schema.org", identifier="employee")],
            is_relevant=True,
            status=Status.PUBLISHED,
        )
    )
    before = ontology_repo.get_property_definition(PROP_ID)

    run = _new_run(pipeline_repo)
    _in_run(run.id, lambda: ontology_service.delete_property_definition(PROP_ID))
    assert ontology_repo.get_property_definition(PROP_ID) is None

    revert_service.revert_with_summary(run.id)

    after = ontology_repo.get_property_definition(PROP_ID)
    assert after is not None
    assert _without_bookkeeping(after) == _without_bookkeeping(before)
    assert _schema_hits(schema_index, embedding, "Has as an employee.", "property_definition") == [
        PROP_ID
    ]
