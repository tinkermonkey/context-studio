"""
Integration tests for datasets over one schema (#1484), against real SQLite
with foreign keys enforced, as in the app.

Two datasets share one taxonomy's schema: each lists and counts only its own
individuals and relationships, edges can't cross them, deleting one removes
its data with a change event each, and a revert restores an individual into
its dataset (or refuses when the dataset is gone).
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.interchange.services import set_batch_run_context
from domain.ontology.entities import Individual
from domain.ontology.events import (
    IndividualCreated,
    IndividualDeleted,
    RelationshipCreated,
    RelationshipDeleted,
)
from domain.ontology.exceptions import (
    DatasetMismatchError,
    DatasetRequiredError,
    DuplicateEntityError,
)
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.versioning.exceptions import RevertRefusedError
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.parent_rows import create_batch_row


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield SharedSessionFactory(sessionmaker(bind=engine))
        engine.dispose()


@pytest.fixture()
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory=session_factory)


@pytest.fixture()
def change_repo(session_factory):
    return SQLiteChangeRepository(session_factory=session_factory)


@pytest.fixture()
def service(repo, change_repo, session_factory):
    publisher = InProcessEventPublisher()
    recorder = ChangeEventRecorder(change_repo)
    publisher.subscribe(IndividualCreated, recorder.on_individual_created)
    publisher.subscribe(IndividualDeleted, recorder.on_individual_deleted)
    publisher.subscribe(RelationshipCreated, recorder.on_relationship_created)
    publisher.subscribe(RelationshipDeleted, recorder.on_relationship_deleted)
    return OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=publisher,
        transaction_scope=SqliteTransactionScope(session_factory),
    )


@pytest.fixture()
def model(service):
    """One schema (component -uses-> service), two datasets, each with two linked individuals."""
    taxonomy = service.create_taxonomy(title="Architecture")
    scheme = service.create_scheme(taxonomy.id, title="Application")
    component = service.create_class(scheme.id, title="Component")
    service_cls = service.create_class(scheme.id, title="Service")
    uses = service.create_property_definition(
        identifier="uses",
        title="Uses",
        domain_class_id=component.id,
        range_class_id=service_cls.id,
    )
    alpha = service.create_dataset(taxonomy.id, "alpha", "Platform Alpha")
    beta = service.create_dataset(taxonomy.id, "beta", "Platform Beta")
    data = {}
    for dataset in (alpha, beta):
        gateway = service.create_individual(
            [component.id], title="API Gateway", dataset_id=dataset.id
        )
        api = service.create_individual([service_cls.id], title="API", dataset_id=dataset.id)
        service.create_relationship(gateway.id, api.id, uses.id)
        data[dataset.identifier] = (gateway, api)
    return {
        "taxonomy": taxonomy,
        "scheme": scheme,
        "component": component,
        "service": service_cls,
        "uses": uses,
        "alpha": alpha,
        "beta": beta,
        "data": data,
    }


class TestScopedQueries:
    def test_each_dataset_lists_and_counts_only_its_own_individuals(self, repo, model):
        alpha, beta = model["alpha"].id, model["beta"].id
        alpha_ids = {i.id for i in model["data"]["alpha"]}

        assert {i.id for i in repo.list_individuals(dataset_id=alpha, limit=None)} == alpha_ids
        assert repo.count_individuals(dataset_id=beta) == 2
        assert repo.count_individuals() == 4
        assert repo.count_individuals(class_id=model["component"].id, dataset_id=alpha) == 1
        assert repo.count_individuals(query="gateway", dataset_id=beta) == 1

    def test_each_dataset_lists_and_counts_only_its_own_relationships(self, repo, model):
        gateway, api = model["data"]["alpha"]

        [edge] = repo.list_relationships(dataset_id=model["alpha"].id, limit=None)
        assert (edge.source_id, edge.target_id) == (gateway.id, api.id)
        assert repo.count_relationships(dataset_id=model["beta"].id) == 1
        assert repo.count_relationships() == 2

    def test_scheme_and_class_counts_take_a_dataset(self, repo, model):
        alpha = model["alpha"].id

        [scheme_counts] = repo.count_by_scheme(model["taxonomy"].id, dataset_id=alpha)
        assert scheme_counts.individual_count == 2
        [all_counts] = repo.count_by_scheme(model["taxonomy"].id)
        assert all_counts.individual_count == 4

        by_class = {c.class_id: c for c in repo.count_by_class(model["scheme"].id, alpha)}
        component = by_class[model["component"].id]
        assert (component.individual_count, component.relationship_count) == (1, 1)

    def test_datasets_are_listed_per_taxonomy_by_title(self, repo, model):
        listed = repo.list_datasets(taxonomy_id=model["taxonomy"].id)

        assert [d.identifier for d in listed] == ["alpha", "beta"]
        assert repo.list_datasets(taxonomy_id="other") == []


class TestWrites:
    def test_the_same_title_is_two_individuals_in_two_datasets_but_refused_in_one(
        self, service, model
    ):
        with pytest.raises(DuplicateEntityError):
            service.create_individual(
                [model["service"].id], title="API", dataset_id=model["alpha"].id
            )

    def test_a_write_must_name_a_dataset_once_the_taxonomy_has_several(self, service, model):
        with pytest.raises(DatasetRequiredError) as raised:
            service.create_individual([model["service"].id], title="Billing")

        assert raised.value.identifiers == ["alpha", "beta"]

    def test_a_taxonomys_first_individual_creates_its_default_dataset(self, service, repo):
        taxonomy = service.create_taxonomy(title="Life Sciences")
        scheme = service.create_scheme(taxonomy.id, title="Cells")
        cell = service.create_class(scheme.id, title="Cell")

        individual = service.create_individual([cell.id], title="Neuron")

        [dataset] = repo.list_datasets(taxonomy_id=taxonomy.id)
        assert (dataset.identifier, individual.dataset_id) == ("default", dataset.id)

    def test_an_individual_cannot_take_a_class_from_another_taxonomy(self, service, model):
        other = service.create_taxonomy(title="Other")
        other_cls = service.create_class(
            service.create_scheme(other.id, title="Other").id, title="Thing"
        )
        gateway, _ = model["data"]["alpha"]

        with pytest.raises(DatasetMismatchError):
            service.add_class_to_individual(gateway.id, other_cls.id)

    def test_the_repository_refuses_a_new_individual_without_a_dataset(self, repo, model):
        with pytest.raises(ValueError, match="no dataset"):
            repo.save_individual(
                Individual(id="ind-x", class_ids=[model["service"].id], title="Orphan")
            )

    def test_an_update_keeps_the_stored_dataset(self, repo, model):
        gateway, _ = model["data"]["alpha"]
        gateway.dataset_id = model["beta"].id
        gateway.title = "Edge Gateway"

        saved = repo.save_individual(gateway)

        assert saved.dataset_id == model["alpha"].id

    def test_a_relationship_cannot_cross_datasets(self, service, model):
        alpha_gateway, _ = model["data"]["alpha"]
        _, beta_api = model["data"]["beta"]

        with pytest.raises(DatasetMismatchError):
            service.create_relationship(alpha_gateway.id, beta_api.id, model["uses"].id)

    def test_renaming_checks_titles_only_inside_the_dataset(self, service, model):
        _, beta_api = model["data"]["beta"]
        service.create_individual(
            [model["service"].id], title="Billing", dataset_id=model["alpha"].id
        )

        renamed = service.update_individual(beta_api.id, title="Billing")

        assert renamed.title == "Billing"

    def test_a_failed_first_create_leaves_no_default_dataset(self, service, repo):
        taxonomy = service.create_taxonomy(title="Life Sciences")
        cell = service.create_class(
            service.create_scheme(taxonomy.id, title="Cells").id, title="Cell"
        )
        other = service.create_taxonomy(title="Other")
        thing = service.create_class(
            service.create_scheme(other.id, title="Things").id, title="Thing"
        )

        with pytest.raises(DatasetMismatchError):
            service.create_individual([cell.id, thing.id], title="Neuron")

        assert repo.list_datasets(taxonomy_id=taxonomy.id) == []

    def test_a_scheme_with_individuals_cannot_move_taxonomy_even_on_revert(
        self, service, repo, model
    ):
        other = service.create_taxonomy(title="Other")
        scheme = repo.get_concept_scheme(model["scheme"].id)
        scheme.taxonomy_id = other.id

        with pytest.raises(DatasetMismatchError):
            repo.save_concept_scheme(scheme)

    def test_a_dataset_identifier_is_unique_within_its_taxonomy(self, service, model):
        with pytest.raises(DuplicateEntityError):
            service.create_dataset(model["taxonomy"].id, "alpha", "Another Alpha")


class TestDeleteDataset:
    def test_it_removes_only_its_data_and_records_each_delete(
        self, service, repo, change_repo, model
    ):
        alpha_ids = [i.id for i in model["data"]["alpha"]]

        deletion = service.delete_dataset(model["alpha"].id)

        assert (deletion.individual_count, deletion.relationship_count) == (2, 1)
        assert repo.get_dataset(model["alpha"].id) is None
        assert all(repo.get_individual(i) is None for i in alpha_ids)
        assert repo.count_individuals() == 2
        assert repo.count_relationships() == 1
        deletes = [
            e
            for entity_id in alpha_ids
            for e in change_repo.get_changes(entity_id=entity_id).events
            if e.operation.value == "delete"
        ]
        assert len(deletes) == 2
        assert {d.previous_state["dataset_id"] for d in deletes} == {model["alpha"].id}


@pytest.fixture()
def run_id(session_factory):
    repo = PipelineRepository(session_factory=session_factory)
    run = repo.create(
        batch_run_id=create_batch_row(session_factory),
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        implementation_id="default",
        configuration_ref="schema-default",
        configuration_slug="schema-default",
        configuration_version=1,
        specific_data={},
    )
    repo.update_status(run.id, PipelineRunStatus.COMPLETED)
    return run.id


class TestRevert:
    def test_reverting_a_delete_restores_the_individual_into_its_dataset(
        self, service, repo, change_repo, model, run_id
    ):
        _, beta_api = model["data"]["beta"]
        set_batch_run_context(run_id)
        try:
            service.delete_individual(beta_api.id)
        finally:
            set_batch_run_context(None)

        RevertService(change_repo=change_repo, ontology_repo=repo).revert(run_id)

        restored = repo.get_individual(beta_api.id)
        assert restored is not None
        assert restored.dataset_id == model["beta"].id

    def test_reverting_into_a_deleted_dataset_is_refused(
        self, service, repo, change_repo, model, run_id
    ):
        _, beta_api = model["data"]["beta"]
        set_batch_run_context(run_id)
        try:
            service.delete_individual(beta_api.id)
        finally:
            set_batch_run_context(None)
        service.delete_dataset(model["beta"].id)

        with pytest.raises(RevertRefusedError, match="dataset .* was deleted"):
            RevertService(change_repo=change_repo, ontology_repo=repo).revert(run_id)
