"""
Import Context Studio's own Documentation Robotics model against the spec it targets.

`scripts/import_dr_model.py` loads `documentation-robotics/model/` (this repo's
DR model: one YAML file per element type per layer, plus relationships.yaml) as
individuals and relationships under the `dr_spec` taxonomy that
`scripts/import_dr_ontology.py` builds from the DR spec. The importer's other
tests use a small synthetic spec and model; this one runs the real model
through the production wiring (`build_import_service`, file-backed SQLite with
foreign keys enforced) against the spec snapshot the model was written for
(`MODEL_DR_SPEC_VERSION`, newer than the cassette pin), so a model or spec
change that breaks the import fails here, on CI.

It lives under tests/integration/pipelines/ because that is the directory CI
runs, alongside the spec-snapshot helper.
"""

from collections import Counter

import pytest
import yaml

from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from scripts.dr_model_loader import ModelImportSummary, import_dr_model
from scripts.dr_ontology_loader import DR_SOURCE, import_dr_ontology
from scripts.import_dr_model import DEFAULT_VIEWER_DIR, build_import_service
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import (
    MODEL_DR_SPEC_VERSION,
    dr_spec_dir,
)

MODEL_DIR = DEFAULT_VIEWER_DIR / "documentation-robotics" / "model"

# The model as committed in documentation-robotics/model/. Update these when the
# model is regenerated; the per-layer checks below derive from the manifest.
EXPECTED_INDIVIDUALS = 450
EXPECTED_RELATIONSHIPS = 584


def _manifest_layer_counts() -> dict[str, int]:
    """Element count per layer, as declared by the model's manifest.yaml."""
    manifest = yaml.safe_load((MODEL_DIR / "manifest.yaml").read_text())
    return {
        layer: sum((spec.get("elements") or {}).values())
        for layer, spec in manifest["layers"].items()
    }


def _totals(summary: ModelImportSummary) -> Counter:
    totals: Counter = Counter()
    for counts in summary.layers.values():
        totals.update(vars(counts))
    return totals


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    """Import the model's DR spec, then the DR model twice, into one file DB."""
    db_path = tmp_path_factory.mktemp("dr_model") / "local.db"
    engine = create_local_db_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    service = build_import_service(session_factory, FakeEmbeddingService())
    repo = SQLiteOntologyRepository(session_factory)
    import_dr_ontology(service, repo, dr_spec_dir(MODEL_DR_SPEC_VERSION))

    first = import_dr_model(service, repo, DEFAULT_VIEWER_DIR)
    events_after_first = SQLiteChangeRepository(session_factory).get_changes(limit=None).total
    individuals_after_first = repo.count_individuals()
    relationships_after_first = repo.count_relationships()

    second = import_dr_model(service, repo, DEFAULT_VIEWER_DIR)
    events_after_second = SQLiteChangeRepository(session_factory).get_changes(limit=None).total

    yield {
        "repo": repo,
        "first": first,
        "second": second,
        "events_after_first": events_after_first,
        "events_after_second": events_after_second,
        "individuals_after_first": individuals_after_first,
        "relationships_after_first": relationships_after_first,
    }
    engine.dispose()


class TestDrModelImportAgainstModelSpec:
    def test_model_was_written_for_the_snapshot_spec(self, imported):
        assert imported["first"].model_spec_version == MODEL_DR_SPEC_VERSION

    def test_imports_every_element_and_relationship_with_nothing_skipped(self, imported):
        first = imported["first"]
        assert first.skipped == [], [(r.layer, r.kind, r.key, r.reason) for r in first.skipped[:10]]
        totals = _totals(first)
        assert totals["individuals_created"] == EXPECTED_INDIVIDUALS
        assert totals["relationships_created"] == EXPECTED_RELATIONSHIPS
        assert totals["individuals_skipped"] == totals["relationships_skipped"] == 0

    def test_per_layer_counts_match_the_model_manifest(self, imported):
        created = {
            layer: counts.individuals_created for layer, counts in imported["first"].layers.items()
        }
        expected = {layer: n for layer, n in _manifest_layer_counts().items() if n}
        assert created == expected
        assert sum(expected.values()) == EXPECTED_INDIVIDUALS

    def test_database_holds_the_imported_rows(self, imported):
        repo = imported["repo"]
        assert imported["individuals_after_first"] == EXPECTED_INDIVIDUALS
        assert imported["relationships_after_first"] == EXPECTED_RELATIONSHIPS
        individuals = repo.list_individuals(limit=None)
        # Every individual is typed to a dr_spec class and carries its DR path,
        # the key that makes a re-run update in place instead of duplicating.
        assert all(i.class_ids for i in individuals)
        paths = [
            ref.identifier
            for i in individuals
            for ref in i.external_references
            if ref.source == DR_SOURCE
        ]
        assert len(paths) == len(set(paths)) == EXPECTED_INDIVIDUALS

    def test_records_a_change_event_per_created_row(self, imported):
        assert imported["events_after_first"] == EXPECTED_INDIVIDUALS + EXPECTED_RELATIONSHIPS

    def test_rerun_is_idempotent(self, imported):
        second = imported["second"]
        totals = _totals(second)
        assert second.skipped == []
        assert totals["individuals_unchanged"] == EXPECTED_INDIVIDUALS
        assert totals["relationships_unchanged"] == EXPECTED_RELATIONSHIPS
        assert totals["individuals_created"] == totals["individuals_updated"] == 0
        assert totals["relationships_created"] == 0

        repo = imported["repo"]
        assert repo.count_individuals() == EXPECTED_INDIVIDUALS
        assert repo.count_relationships() == EXPECTED_RELATIONSHIPS
        assert imported["events_after_second"] == imported["events_after_first"]


def test_model_directory_is_present():
    """Guard: the model ships in this repo, so the import test can never silently skip."""
    assert (MODEL_DIR / "manifest.yaml").is_file()
    assert (MODEL_DIR / "relationships.yaml").is_file()
