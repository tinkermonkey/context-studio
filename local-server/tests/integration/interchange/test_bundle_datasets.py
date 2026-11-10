"""
Integration tests (#1487): bundles and datasets, on real SQLite with the House
bundle. A plain export is as before; an export of one dataset carries only its
data and names it; a schema-only export has no data and, imported, plans none;
an import into a named dataset creates there and leaves the others alone.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import copy

import pytest

from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.interchange.bundle import BundleExporter, BundleError
from domain.ontology.services import OntologyService
from scripts.import_bundle import build_bundle_importer
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.integration.interchange.test_bundle import _workspace, house_with_kits


@pytest.fixture()
def session_factory(tmp_path):
    factory = _workspace(tmp_path / "local.db")
    yield factory
    factory.kw["bind"].dispose()


@pytest.fixture()
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture()
def importer(session_factory):
    return build_bundle_importer(session_factory, FakeEmbeddingService())


@pytest.fixture()
def house(importer, repo):
    """The House bundle imported into its `default` dataset, plus an empty `annex`."""
    result = importer.import_bundle(house_with_kits(), apply=True)
    taxonomy_id = result.proposal.taxonomy_id
    ontology = OntologyService(repo, FakeEmbeddingService(), FakeEventPublisher())
    [default] = repo.list_datasets(taxonomy_id)
    annex = ontology.create_dataset(taxonomy_id, "annex", "Annex")
    return {"taxonomy_id": taxonomy_id, "default": default, "annex": annex}


def test_a_plain_export_is_unchanged_and_names_no_dataset(repo, house):
    bundle = BundleExporter(repo).export(house["taxonomy_id"], source="house")

    assert "dataset" not in bundle
    assert len(bundle["individuals"]) == repo.count_individuals()


def test_a_dataset_export_carries_only_its_data_and_names_it(repo, house):
    exporter = BundleExporter(repo)

    default = exporter.export(house["taxonomy_id"], "house", dataset_id=house["default"].id)
    annex = exporter.export(house["taxonomy_id"], "house", dataset_id=house["annex"].id)

    assert default["dataset"] == {"identifier": "default", "title": "Default"}
    assert len(default["individuals"]) == repo.count_individuals(dataset_id=house["default"].id)
    assert annex["individuals"] == [] and annex["relationships"] == []
    assert annex["dataset"]["identifier"] == "annex"


def test_a_schema_only_export_has_no_data_and_imports_without_touching_data(importer, repo, house):
    before = repo.count_individuals()
    schema = BundleExporter(repo).export(house["taxonomy_id"], "house", schema_only=True)

    result = importer.import_bundle(schema, dry_run=True)

    assert "individuals" not in schema and "relationships" not in schema
    assert result.plan.operations == []
    assert repo.count_individuals() == before


def test_importing_into_another_dataset_creates_there_and_leaves_the_rest(importer, repo, house):
    default_count = repo.count_individuals(dataset_id=house["default"].id)
    bundle = BundleExporter(repo).export(house["taxonomy_id"], "house", house["default"].id)
    bundle["dataset"] = {"identifier": "annex", "title": "Annex"}
    for individual in bundle["individuals"]:
        individual["id"] = f"annex-{individual['id']}"
    for relationship in bundle["relationships"]:
        relationship["source"] = f"annex-{relationship['source']}"
        relationship["target"] = f"annex-{relationship['target']}"
    # Imported data carries the source's references; this copy is a new set.
    for individual in bundle["individuals"]:
        individual.pop("external_references", None)

    result = importer.import_bundle(copy.deepcopy(bundle), apply=True)

    assert result.proposal.dataset_id == house["annex"].id
    assert repo.count_individuals(dataset_id=house["annex"].id) == default_count
    assert repo.count_individuals(dataset_id=house["default"].id) == default_count
    assert all(o.op.value != "delete" for o in result.proposal.operations)


def test_an_unknown_dataset_is_refused(importer, house):
    with pytest.raises(BundleError, match="No dataset 'nowhere'"):
        importer.import_bundle(house_with_kits(), dataset="nowhere", dry_run=True)


def test_a_named_dataset_is_made_for_a_taxonomy_without_any(importer, repo):
    schema_first = house_with_kits()
    schema_first.pop("individuals"), schema_first.pop("relationships")
    importer.import_bundle(schema_first, apply=True)
    taxonomy = repo.get_by_identifier(schema_first["taxonomy"]["identifier"])
    assert repo.list_datasets(taxonomy.id) == []

    result = importer.import_bundle(house_with_kits(), apply=True, dataset="prod")

    [dataset] = repo.list_datasets(taxonomy.id)
    assert dataset.identifier == "prod"
    assert result.proposal.dataset_id == dataset.id


def test_a_schema_only_import_leaves_another_datasets_pending_import(importer, repo, house):
    bundle = BundleExporter(repo).export(house["taxonomy_id"], "house", house["default"].id)
    bundle["individuals"].append(
        {"id": "new-one", "classes": [bundle["classes"][0]["identifier"]], "title": "New one"}
    )
    pending = importer.import_bundle(copy.deepcopy(bundle)).proposal
    schema = BundleExporter(repo).export(house["taxonomy_id"], "house", schema_only=True)
    schema["taxonomy"]["description"] = "Changed"

    importer.import_bundle(schema)

    still = importer._proposals.get(pending.id)
    assert any(o.status.value == "pending" for o in still.operations)
