"""
Integration tests for the `ontology_factory` fixture (tests/integration/pipelines/conftest.py).

Verifies that PLACEHOLDER and DR_SPEC ontology contexts build independently
and are cached per test session, and that DR_SPEC reuses the Phase 1
DR-spec transform (scripts.dr_ontology_loader.import_dr_ontology) rather than
duplicating any translation logic.
"""

from domain.ontology.value_objects import SearchCriteria
from scripts.dr_ontology_loader import DR_TAXONOMY_IDENTIFIER
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dataset_split import OntologyContext


class TestPlaceholderOntology:
    def test_builds_three_placeholder_classes(self, ontology_factory):
        repo, _index = ontology_factory(OntologyContext.PLACEHOLDER)
        for identifier in ("individual", "property", "entity"):
            assert repo.get_by_identifier(identifier) is not None

    def test_is_cached_across_calls(self, ontology_factory):
        first_repo, first_index = ontology_factory(OntologyContext.PLACEHOLDER)
        second_repo, second_index = ontology_factory(OntologyContext.PLACEHOLDER)
        assert first_repo is second_repo
        assert first_index is second_index

    def test_search_finds_a_placeholder_class(self, ontology_factory):
        _repo, index = ontology_factory(OntologyContext.PLACEHOLDER)
        query = FakeEmbeddingService().embed("individual")
        matches = index.search(query, kinds=["class"], top_k=10)
        assert len(matches) == 3


class TestDrSpecOntology:
    def test_builds_expected_row_counts(self, ontology_factory):
        repo, _index = ontology_factory(OntologyContext.DR_SPEC)
        taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
        assert taxonomy is not None
        classes = repo.search_classes(SearchCriteria(taxonomy_id=taxonomy.id, limit=1000))
        assert len(classes) == 186

    def test_is_cached_and_independent_of_placeholder(self, ontology_factory):
        placeholder_repo, _ = ontology_factory(OntologyContext.PLACEHOLDER)
        dr_repo, _ = ontology_factory(OntologyContext.DR_SPEC)
        dr_repo_again, _ = ontology_factory(OntologyContext.DR_SPEC)

        assert dr_repo is dr_repo_again
        assert placeholder_repo is not dr_repo
        # The DR taxonomy only exists in the DR_SPEC context's database.
        assert placeholder_repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER) is None
        assert dr_repo.get_by_identifier("individual") is None

    def test_search_scoped_to_dr_taxonomy_excludes_placeholder_classes(self, ontology_factory):
        _repo, index = ontology_factory(OntologyContext.DR_SPEC)
        # The DR-spec ontology has no "individual"/"property"/"entity" classes,
        # confirming this is the real imported spec, not the placeholder.
        query = FakeEmbeddingService().embed("individual")
        matches = index.search(query, kinds=["class"], top_k=1000)
        labels = {m.label for m in matches}
        assert "Individual" not in labels
