"""
Unit tests for the DR model -> individuals transform (scripts/dr_model_loader.py).

Builds a tiny dr_spec ontology in the in-memory fake repository and a tiny
synthetic DR model directory (not the real documentation-robotics/model/),
then exercises element/relationship resolution, skip reporting, and
idempotent re-runs.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import yaml

from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference
from scripts.dr_model_loader import import_dr_model
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

DR = "documentation_robotics"


def _element(layer, type_name, slug, name, description=None):
    return {
        "path": f"{layer}.{type_name}.{slug}",
        "spec_node_id": f"{layer}.{type_name}",
        "type": type_name,
        "layer_id": layer,
        "name": name,
        "description": description,
    }


def _relationship(source, predicate, target):
    return {"source": source, "target": target, "predicate": predicate}


def _write_model(viewer_dir, elements, relationships):
    model_dir = viewer_dir / "documentation-robotics" / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "manifest.yaml").write_text(yaml.safe_dump({"spec_version": "0.8.4"}))
    by_file = {}
    for element in elements:
        by_file.setdefault((element["layer_id"], element["type"]), {})[element["path"]] = element
    for (layer, type_name), data in by_file.items():
        layer_dir = model_dir / f"01_{layer}"
        layer_dir.mkdir(exist_ok=True)
        (layer_dir / f"{type_name}.yaml").write_text(yaml.safe_dump(data))
    (model_dir / "relationships.yaml").write_text(yaml.safe_dump(relationships))


STAKEHOLDER = _element("motivation", "stakeholder", "km", "Knowledge Manager", "Curates")
GOAL = _element("motivation", "goal", "reuse", "Knowledge Reuse", "Reuse knowledge")
SERVICE = _element("business", "businessservice", "curation", "Curation Service")


@pytest.fixture
def repo():
    return FakeOntologyRepository()


@pytest.fixture
def service(repo):
    return OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=FakeEventPublisher(),
    )


@pytest.fixture
def ontology(service, repo):
    """dr_spec taxonomy: 3 classes, 2 property definitions, each carrying its DR ref."""
    taxonomy = service.create_taxonomy(title="Documentation Robotics", identifier="dr_spec")
    class_ids = {}
    for layer, type_name in (
        ("motivation", "stakeholder"),
        ("motivation", "goal"),
        ("business", "businessservice"),
    ):
        scheme = repo.get_by_identifier(layer) or service.create_scheme(
            taxonomy_id=taxonomy.id, title=layer, identifier=layer
        )
        cls = service.create_class(
            concept_scheme_id=scheme.id,
            title=type_name,
            identifier=f"{layer}_{type_name}",
        )
        cls.external_references.append(
            ExternalReference(source=DR, identifier=f"{layer}.{type_name}")
        )
        repo.save_class(cls)
        class_ids[f"{layer}.{type_name}"] = cls.id
    for source, predicate, target in (
        ("motivation.stakeholder", "associated-with", "motivation.goal"),
        ("motivation.goal", "realizes", "business.businessservice"),
    ):
        service.create_property_definition(
            identifier=f"{source}_{predicate}_{target}".replace(".", "_").replace("-", "_"),
            title=f"{source} {predicate} {target}",
            canonical_predicate=predicate,
            domain_class_id=class_ids[source],
            range_class_id=class_ids[target],
            external_references=[
                ExternalReference(source=DR, identifier=f"{source}.{predicate}.{target}")
            ],
        )
    return class_ids


def _individual_by_path(repo, path):
    matches = [
        individual
        for individual in repo.list_individuals(limit=None)
        if any(ref.identifier == path for ref in individual.external_references)
    ]
    assert len(matches) <= 1
    return matches[0] if matches else None


class TestImportCreatesIndividualsAndRelationships:
    def test_creates_typed_individuals_with_path_reference(self, service, repo, ontology, tmp_path):
        _write_model(tmp_path, [STAKEHOLDER, GOAL, SERVICE], [])

        summary = import_dr_model(service, repo, tmp_path)

        assert summary.model_spec_version == "0.8.4"
        assert summary.layers["motivation"].individuals_created == 2
        assert summary.layers["business"].individuals_created == 1
        individual = _individual_by_path(repo, STAKEHOLDER["path"])
        assert individual.title == "Knowledge Manager"
        assert individual.description == "Curates"
        assert individual.class_ids == [ontology["motivation.stakeholder"]]
        assert individual.external_references == [
            ExternalReference(source=DR, identifier=STAKEHOLDER["path"])
        ]

    def test_creates_relationships_typed_to_matching_property_definition(
        self, service, repo, ontology, tmp_path
    ):
        _write_model(
            tmp_path,
            [STAKEHOLDER, GOAL, SERVICE],
            [
                _relationship(STAKEHOLDER["path"], "associated-with", GOAL["path"]),
                _relationship(GOAL["path"], "realizes", SERVICE["path"]),
            ],
        )

        summary = import_dr_model(service, repo, tmp_path)

        assert summary.layers["motivation"].relationships_created == 2
        assert summary.skipped == []
        goal = _individual_by_path(repo, GOAL["path"])
        realizes = repo.list_relationships(source_id=goal.id, limit=None)
        assert len(realizes) == 1
        prop = repo.get_property_definition(realizes[0].property_definition_id)
        assert prop.canonical_predicate == "realizes"
        assert realizes[0].target_id == _individual_by_path(repo, SERVICE["path"]).id


class TestImportSkipsUnresolvable:
    def test_unknown_element_type_is_skipped_not_fabricated(
        self, service, repo, ontology, tmp_path
    ):
        unknown = _element("motivation", "driver", "growth", "Growth")
        _write_model(tmp_path, [STAKEHOLDER, unknown], [])

        summary = import_dr_model(service, repo, tmp_path)

        assert summary.layers["motivation"].individuals_created == 1
        assert summary.layers["motivation"].individuals_skipped == 1
        assert [(r.key, r.reason) for r in summary.skipped] == [
            (unknown["path"], "unresolved_class:motivation.driver")
        ]
        assert _individual_by_path(repo, unknown["path"]) is None

    def test_unresolved_predicate_endpoint_and_self_loop_are_skipped(
        self, service, repo, ontology, tmp_path
    ):
        _write_model(
            tmp_path,
            [STAKEHOLDER, GOAL],
            [
                _relationship(STAKEHOLDER["path"], "influences", GOAL["path"]),
                _relationship(STAKEHOLDER["path"], "associated-with", "motivation.goal.missing"),
                _relationship(STAKEHOLDER["path"], "associated-with", STAKEHOLDER["path"]),
            ],
        )

        summary = import_dr_model(service, repo, tmp_path)

        reasons = sorted(r.reason for r in summary.skipped)
        assert reasons == [
            "self_loop",
            "unresolved_predicate:motivation.stakeholder.influences.motivation.goal",
            "unresolved_target:motivation.goal.missing",
        ]
        assert summary.layers["motivation"].relationships_skipped == 3
        assert repo.list_relationships(limit=None) == []

    def test_duplicate_title_within_class_is_skipped(self, service, repo, ontology, tmp_path):
        twin = _element("motivation", "stakeholder", "km-2", "Knowledge Manager")
        _write_model(tmp_path, [STAKEHOLDER, twin], [])

        summary = import_dr_model(service, repo, tmp_path)

        assert summary.layers["motivation"].individuals_created == 1
        assert [r.reason for r in summary.skipped] == ["duplicate_title_in_class:Knowledge Manager"]

    def test_missing_dr_spec_taxonomy_raises(self, service, repo, tmp_path):
        _write_model(tmp_path, [STAKEHOLDER], [])

        with pytest.raises(ValueError, match="dr_spec"):
            import_dr_model(service, repo, tmp_path)


class TestImportIdempotency:
    def test_rerun_reports_everything_unchanged(self, service, repo, ontology, tmp_path):
        relationships = [_relationship(STAKEHOLDER["path"], "associated-with", GOAL["path"])]
        _write_model(tmp_path, [STAKEHOLDER, GOAL], relationships)
        import_dr_model(service, repo, tmp_path)

        summary = import_dr_model(service, repo, tmp_path)

        counts = summary.layers["motivation"]
        assert (counts.individuals_created, counts.individuals_updated) == (0, 0)
        assert counts.individuals_unchanged == 2
        assert (counts.relationships_created, counts.relationships_unchanged) == (0, 1)
        assert len(repo.list_individuals(limit=None)) == 2
        assert len(repo.list_relationships(limit=None)) == 1

    def test_rename_updates_in_place_keyed_on_path(self, service, repo, ontology, tmp_path):
        _write_model(tmp_path, [STAKEHOLDER], [])
        import_dr_model(service, repo, tmp_path)
        original_id = _individual_by_path(repo, STAKEHOLDER["path"]).id

        _write_model(tmp_path, [{**STAKEHOLDER, "name": "Ontology Curator"}], [])
        summary = import_dr_model(service, repo, tmp_path)

        assert summary.layers["motivation"].individuals_updated == 1
        individual = _individual_by_path(repo, STAKEHOLDER["path"])
        assert individual.id == original_id
        assert individual.title == "Ontology Curator"
        assert len(repo.list_individuals(limit=None)) == 1

    def test_adopts_same_title_individual_without_path_reference(
        self, service, repo, ontology, tmp_path
    ):
        # E.g. a run interrupted between create and reference attach.
        orphan = service.create_individual(
            ontology["motivation.stakeholder"], title="Knowledge Manager"
        )
        _write_model(tmp_path, [STAKEHOLDER], [])

        summary = import_dr_model(service, repo, tmp_path)

        assert summary.layers["motivation"].individuals_updated == 1
        assert summary.skipped == []
        adopted = _individual_by_path(repo, STAKEHOLDER["path"])
        assert adopted.id == orphan.id
        assert adopted.description == "Curates"
        assert len(repo.list_individuals(limit=None)) == 1
