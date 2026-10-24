"""
Integration tests for the DR model import (scripts/dr_model_loader.import_dr_model).

Imports a tiny synthetic DR spec into a fresh in-memory SQLite database first
(via import_dr_ontology), then a tiny synthetic DR model — neither the real
spec checkout nor the repo's documentation-robotics/model/. Covers individual
and relationship rows, change events recorded through the service, idempotent
re-import, and the batch reindex the script runs afterwards.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.models import Base, ChangeEvent, OntologyEntity
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from scripts.dr_model_loader import import_dr_model
from scripts.dr_ontology_loader import import_dr_ontology
from scripts.import_dr_model import build_import_service
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.scripts.test_import_dr_ontology import spec_dir  # noqa: F401  (fixture)

# The synthetic spec (see test_import_dr_ontology.spec_dir) defines
# motivation.{goal,stakeholder}, business.businessservice and the predicates
# stakeholder associated-with goal, goal realizes businessservice.
ELEMENTS = {
    "motivation/stakeholder.yaml": {
        "motivation.stakeholder.km": {
            "path": "motivation.stakeholder.km",
            "spec_node_id": "motivation.stakeholder",
            "layer_id": "motivation",
            "name": "Knowledge Manager",
            "description": "Curates the graph",
        },
    },
    "motivation/goal.yaml": {
        "motivation.goal.reuse": {
            "path": "motivation.goal.reuse",
            "spec_node_id": "motivation.goal",
            "layer_id": "motivation",
            "name": "Knowledge Reuse",
        },
    },
    "business/businessservice.yaml": {
        "business.businessservice.curation": {
            "path": "business.businessservice.curation",
            "spec_node_id": "business.businessservice",
            "layer_id": "business",
            "name": "Curation Service",
        },
        "business.businessevent.release": {
            "path": "business.businessevent.release",
            "spec_node_id": "business.businessevent",
            "layer_id": "business",
            "name": "Release",
        },
    },
}
RELATIONSHIPS = [
    {
        "source": "motivation.stakeholder.km",
        "target": "motivation.goal.reuse",
        "predicate": "associated-with",
    },
    {
        "source": "motivation.goal.reuse",
        "target": "business.businessservice.curation",
        "predicate": "realizes",
    },
    {
        "source": "business.businessservice.curation",
        "target": "motivation.goal.reuse",
        "predicate": "serves",
    },
]


@pytest.fixture
def viewer_dir(tmp_path):
    model_dir = tmp_path / "viewer" / "documentation-robotics" / "model"
    for relative, data in ELEMENTS.items():
        path = model_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data))
    (model_dir / "relationships.yaml").write_text(yaml.safe_dump(RELATIONSHIPS))
    (model_dir / "manifest.yaml").write_text(yaml.safe_dump({"spec_version": "0.8.4"}))
    return tmp_path / "viewer"


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def ontology_service(repo, session_factory, spec_dir):  # noqa: F811
    # The same wiring the import scripts use (import_dr_model.py, seed_dr_poc.py).
    service = build_import_service(session_factory, FakeEmbeddingService())
    import_dr_ontology(service, repo, spec_dir)
    return service


def _count(session_factory, model, **filters):
    with session_factory() as session:
        return session.query(model).filter_by(**filters).count()


class TestImportDrModel:
    def test_imports_resolvable_elements_and_relationships(
        self, ontology_service, repo, viewer_dir, session_factory
    ):
        summary = import_dr_model(ontology_service, repo, viewer_dir)

        assert summary.layers["motivation"].individuals_created == 2
        assert summary.layers["business"].individuals_created == 1
        assert summary.layers["motivation"].relationships_created == 2
        assert sorted((r.kind, r.reason) for r in summary.skipped) == [
            ("element", "unresolved_class:business.businessevent"),
            (
                "relationship",
                "unresolved_predicate:business.businessservice.serves.motivation.goal",
            ),
        ]
        assert _count(session_factory, OntologyEntity, node_type="individual") == 3

        stakeholder = repo.get_by_identifier("motivation_stakeholder")
        individuals = repo.list_individuals(class_id=stakeholder.id, limit=None)
        assert [i.title for i in individuals] == ["Knowledge Manager"]
        assert individuals[0].external_references[0].identifier == "motivation.stakeholder.km"

        relationships = repo.list_relationships(source_id=individuals[0].id, limit=None)
        assert len(relationships) == 1
        prop = repo.get_property_definition(relationships[0].property_definition_id)
        assert prop.identifier == "stakeholder_associated_with_goal"

    def test_records_change_events_through_the_service(
        self, ontology_service, repo, viewer_dir, session_factory
    ):
        import_dr_model(ontology_service, repo, viewer_dir)

        assert _count(session_factory, ChangeEvent, entity_type="individual") == 3
        assert _count(session_factory, ChangeEvent, entity_type="relationship") == 2

    def test_reimport_is_idempotent(self, ontology_service, repo, viewer_dir, session_factory):
        import_dr_model(ontology_service, repo, viewer_dir)
        summary = import_dr_model(ontology_service, repo, viewer_dir)

        assert summary.layers["motivation"].individuals_unchanged == 2
        assert summary.layers["business"].individuals_unchanged == 1
        assert summary.layers["motivation"].relationships_unchanged == 2
        assert sum(c.individuals_created for c in summary.layers.values()) == 0
        assert sum(c.relationships_created for c in summary.layers.values()) == 0
        assert _count(session_factory, OntologyEntity, node_type="individual") == 3
        assert _count(session_factory, ChangeEvent, entity_type="individual") == 3

    def test_individuals_indexed_by_batch_reindex(
        self, ontology_service, repo, viewer_dir, session_factory
    ):
        import_dr_model(ontology_service, repo, viewer_dir)

        indexed = SqliteIndividualVectorIndex(
            session_factory, FakeEmbeddingService()
        ).reindex_all_individuals()

        assert indexed == 3
        assert _count(session_factory, OntologyEntity, node_type="individual", is_indexed=True) == 3
