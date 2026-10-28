"""
Integration tests for the DR model import (scripts/dr_model_loader.import_dr_model).

Imports a tiny synthetic DR spec into a fresh in-memory SQLite database first
(via import_dr_ontology), then a tiny synthetic DR model — neither the real
spec checkout nor the repo's documentation-robotics/model/. Covers individual
and relationship rows, change events recorded through the service, idempotent
re-import, the batch reindex the script runs afterwards, and pruning relationships
the model no longer has.
"""

import os
import subprocess
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
from scripts.import_dr_model import build_import_service, report_and_prune
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


# The two RELATIONSHIPS entries that resolve against the synthetic spec.
ASSOCIATED = RELATIONSHIPS[0]  # stakeholder.km associated-with goal.reuse
REALIZES = RELATIONSHIPS[1]  # goal.reuse realizes businessservice.curation


def _commit_model(viewer_dir, relationships):
    """Write relationships.yaml and commit the model, as a DR checkout would."""
    model_dir = viewer_dir / "documentation-robotics" / "model"
    (model_dir / "relationships.yaml").write_text(yaml.safe_dump(relationships))
    git = ["git", "-C", str(viewer_dir)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run(
        [
            *git,
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "model",
        ],
        check=True,
    )


def _relationship_titles(repo):
    """(source title, predicate, target title) for every relationship in the DB."""
    titles = {i.id: i.title for i in repo.list_individuals(limit=None)}
    return sorted(
        (
            titles[r.source_id],
            repo.get_property_definition(r.property_definition_id).canonical_predicate,
            titles[r.target_id],
        )
        for r in repo.list_relationships(limit=None)
    )


class TestPruneRelationshipsNoLongerInModel:
    def _import_then_drop_realizes(self, ontology_service, repo, viewer_dir):
        _commit_model(viewer_dir, [ASSOCIATED, REALIZES])
        import_dr_model(ontology_service, repo, viewer_dir)
        _commit_model(viewer_dir, [ASSOCIATED])
        import_dr_model(ontology_service, repo, viewer_dir)

    def test_prune_deletes_a_relationship_whose_triple_left_the_model(
        self, ontology_service, repo, viewer_dir, session_factory, capsys
    ):
        self._import_then_drop_realizes(ontology_service, repo, viewer_dir)

        assert report_and_prune(ontology_service, repo, viewer_dir, prune=True)

        assert _relationship_titles(repo) == [
            ("Knowledge Manager", "associated-with", "Knowledge Reuse")
        ]
        assert (
            _count(session_factory, ChangeEvent, entity_type="relationship", operation="delete")
            == 1
        )
        out = capsys.readouterr().out
        assert "Pruned 1 relationship(s)" in out
        assert "motivation.goal.reuse --realizes--> business.businessservice.curation" in out

    def test_without_prune_the_relationship_is_only_reported(
        self, ontology_service, repo, viewer_dir, session_factory, capsys
    ):
        self._import_then_drop_realizes(ontology_service, repo, viewer_dir)

        assert report_and_prune(ontology_service, repo, viewer_dir, prune=False)

        assert len(_relationship_titles(repo)) == 2
        assert (
            _count(session_factory, ChangeEvent, entity_type="relationship", operation="delete")
            == 0
        )
        out = capsys.readouterr().out
        assert "Would prune 1 relationship(s)" in out
        assert "motivation.goal.reuse --realizes--> business.businessservice.curation" in out

    def test_relationships_not_from_the_model_are_never_touched(
        self, ontology_service, repo, viewer_dir, capsys
    ):
        # The model only ever had `associated-with`; a user draws `realizes`
        # between the same DR individuals, with a DR relationship type.
        _commit_model(viewer_dir, [ASSOCIATED])
        import_dr_model(ontology_service, repo, viewer_dir)
        goal = repo.get_by_identifier("motivation_goal")
        service_class = repo.get_by_identifier("business_businessservice")
        goal_individual = repo.list_individuals(class_id=goal.id, limit=None)[0]
        curation = repo.list_individuals(class_id=service_class.id, limit=None)[0]
        realizes = repo.get_property_definition_by_identifier("goal_realizes_businessservice")
        ontology_service.create_relationship(goal_individual.id, curation.id, realizes.id)

        # The model then drops `associated-with`, so prune has work to do.
        _commit_model(viewer_dir, [])
        import_dr_model(ontology_service, repo, viewer_dir)
        assert report_and_prune(ontology_service, repo, viewer_dir, prune=True)

        assert _relationship_titles(repo) == [("Knowledge Reuse", "realizes", "Curation Service")]
        assert "Pruned 1 relationship(s)" in capsys.readouterr().out

    def test_without_model_history_nothing_is_checked_or_deleted(
        self, ontology_service, repo, viewer_dir, capsys
    ):
        import_dr_model(ontology_service, repo, viewer_dir)  # viewer_dir is not a git checkout

        assert not report_and_prune(ontology_service, repo, viewer_dir, prune=True)

        assert len(_relationship_titles(repo)) == 2
        assert "Prune check failed" in capsys.readouterr().err
