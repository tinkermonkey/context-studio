"""
Integration tests for SQLiteOntologyRepository pagination, sorting, and search.

Tests verify that the new query-building code exercises real SQLite behavior:
- Pagination (limit, offset)
- Sorting (by title, created_at, last_modified)
- Text search filtering (SQLite LIKE - case-insensitive for ASCII characters)
- Count methods with various filters
- Combined filters and sorting

All tests use real in-memory SQLite to expose differences from the fake repository.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    PropertyDefinition,
    Taxonomy,
)


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(db_engine):
    return sessionmaker(bind=db_engine)


@pytest.fixture
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def sample_taxonomy(repo):
    taxonomy = Taxonomy(
        id="tax-1",
        title="Biology",
        description="Biological classification",
    )
    return repo.save_taxonomy(taxonomy)


@pytest.fixture
def sample_concept_scheme(repo, sample_taxonomy):
    scheme = ConceptScheme(
        id="scheme-1",
        taxonomy_id=sample_taxonomy.id,
        title="Organisms",
        description="Classification of living organisms",
    )
    return repo.save_concept_scheme(scheme)


@pytest.fixture
def large_taxonomy_dataset(repo):
    """Create 20 taxonomies with varied names for pagination/sorting tests."""
    names = [
        "Zoology",
        "Botany",
        "Mycology",
        "Entomology",
        "Microbiology",
        "Ecology",
        "Genetics",
        "Anatomy",
        "Physiology",
        "Taxonomy",
        "Ethology",
        "Ornithology",
        "Herpetology",
        "Ichthyology",
        "Paleontology",
        "Arachnology",
        "Malacology",
        "Nematology",
        "Phycology",
        "Lichenology",
    ]
    taxonomies = []
    for i, name in enumerate(names):
        tax = Taxonomy(
            id=f"tax-{i}",
            title=name,
            description=f"Study of {name.lower()}",
        )
        saved = repo.save_taxonomy(tax)
        taxonomies.append(saved)
    return taxonomies


@pytest.fixture
def large_concept_scheme_dataset(repo, sample_taxonomy):
    """Create 15 concept schemes for pagination/sorting tests."""
    names = [
        "Animals",
        "Plants",
        "Fungi",
        "Bacteria",
        "Viruses",
        "Protists",
        "Archaea",
        "Algae",
        "Mosses",
        "Ferns",
        "Gymnosperms",
        "Angiosperms",
        "Invertebrates",
        "Vertebrates",
        "Microorganisms",
    ]
    schemes = []
    for i, name in enumerate(names):
        scheme = ConceptScheme(
            id=f"scheme-{i}",
            taxonomy_id=sample_taxonomy.id,
            title=name,
            description=f"Classification of {name.lower()}",
        )
        saved = repo.save_concept_scheme(scheme)
        schemes.append(saved)
    return schemes


@pytest.fixture
def large_class_dataset(repo, sample_concept_scheme, sample_taxonomy):
    """Create 20 classes for pagination and filtering tests."""
    names = [
        "Mammalia",
        "Aves",
        "Reptilia",
        "Amphibia",
        "Actinopterygii",
        "Sarcopterygii",
        "Petromyzontida",
        "Insecta",
        "Arachnida",
        "Crustacea",
        "Mollusca",
        "Annelida",
        "Nematoda",
        "Platyhelminthes",
        "Porifera",
        "Cnidaria",
        "Echinodermata",
        "Chordata",
        "Arthropoda",
        "Coelenterata",
    ]
    classes = []
    for i, name in enumerate(names):
        cls = Class(
            id=f"class-{i}",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title=name,
            description=f"Class of {name.lower()}",
        )
        saved = repo.save_class(cls)
        classes.append(saved)
    return classes


class TestTaxonomyPagination:
    """Tests for taxonomy list pagination."""

    def test_list_taxonomies_pagination_limit(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=5)
        assert len(result) == 5

    def test_list_taxonomies_pagination_offset(self, repo, large_taxonomy_dataset):
        first_batch = repo.list_taxonomies(limit=5, offset=0)
        second_batch = repo.list_taxonomies(limit=5, offset=5)
        assert len(first_batch) == 5
        assert len(second_batch) == 5
        assert first_batch[0].id != second_batch[0].id

    def test_list_taxonomies_pagination_beyond_total(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=10, offset=50)
        assert len(result) == 0

    def test_list_taxonomies_pagination_none_limit(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=None)
        assert len(result) == 20

    def test_list_taxonomies_pagination_zero_offset(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=5, offset=0)
        assert len(result) == 5


class TestTaxonomySorting:
    """Tests for taxonomy sorting."""

    def test_list_taxonomies_sort_by_title_asc(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=None, sort_by="title", sort_order="asc")
        titles = [t.title for t in result]
        assert titles == sorted(titles)

    def test_list_taxonomies_sort_by_title_desc(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=None, sort_by="title", sort_order="desc")
        titles = [t.title for t in result]
        assert titles == sorted(titles, reverse=True)

    def test_list_taxonomies_sort_by_created_at_asc(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=None, sort_by="created_at", sort_order="asc")
        assert len(result) == 20
        for i in range(len(result) - 1):
            assert result[i].created_at <= result[i + 1].created_at

    def test_list_taxonomies_sort_by_created_at_desc(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=None, sort_by="created_at", sort_order="desc")
        assert len(result) == 20
        for i in range(len(result) - 1):
            assert result[i].created_at >= result[i + 1].created_at

    def test_list_taxonomies_sort_default(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=None, sort_by=None)
        assert len(result) == 20


class TestTaxonomySearch:
    """Tests for taxonomy text search (SQLite LIKE - case-insensitive for ASCII)."""

    def test_list_taxonomies_search_exact_match(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(query="Zoology")
        assert len(result) == 1
        assert result[0].title == "Zoology"

    def test_list_taxonomies_search_partial_match(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(query="ology")
        assert len(result) >= 10
        assert all("ology" in t.title for t in result)

    def test_list_taxonomies_search_case_insensitive(self, repo, large_taxonomy_dataset):
        result_lower = repo.list_taxonomies(query="zoology")
        result_upper = repo.list_taxonomies(query="Zoology")
        result_mixed = repo.list_taxonomies(query="ZoOlOgY")
        assert len(result_lower) == 1
        assert len(result_upper) == 1
        assert len(result_mixed) == 1

    def test_list_taxonomies_search_no_results(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(query="NonexistentTerm")
        assert len(result) == 0

    def test_list_taxonomies_search_empty_query(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(query="")
        assert len(result) == 20

    def test_list_taxonomies_search_with_pagination(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(query="ology", limit=5, offset=0)
        assert len(result) == 5
        assert all("ology" in t.title for t in result)

    def test_list_taxonomies_search_with_sorting(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(query="ology", sort_by="title", sort_order="asc", limit=None)
        titles = [t.title for t in result]
        assert titles == sorted(titles)


class TestTaxonomyCount:
    """Tests for taxonomy count methods."""

    def test_count_taxonomies_total(self, repo, large_taxonomy_dataset):
        count = repo.count_taxonomies()
        assert count == 20

    def test_count_taxonomies_with_query(self, repo, large_taxonomy_dataset):
        count = repo.count_taxonomies(query="ology")
        result = repo.list_taxonomies(query="ology", limit=None)
        assert count == len(result)

    def test_count_taxonomies_no_matches(self, repo, large_taxonomy_dataset):
        count = repo.count_taxonomies(query="NonexistentTerm")
        assert count == 0


class TestConceptSchemePagination:
    """Tests for concept scheme pagination."""

    def test_list_concept_schemes_pagination_limit(self, repo, large_concept_scheme_dataset):
        result = repo.list_concept_schemes(limit=5)
        assert len(result) == 5

    def test_list_concept_schemes_pagination_offset(self, repo, large_concept_scheme_dataset):
        first_batch = repo.list_concept_schemes(limit=5, offset=0)
        second_batch = repo.list_concept_schemes(limit=5, offset=5)
        assert len(first_batch) == 5
        assert len(second_batch) == 5
        assert first_batch[0].id != second_batch[0].id

    def test_list_concept_schemes_pagination_none_limit(self, repo, large_concept_scheme_dataset):
        result = repo.list_concept_schemes(limit=None)
        assert len(result) == 15


class TestConceptSchemeSorting:
    """Tests for concept scheme sorting."""

    def test_list_concept_schemes_sort_by_title_asc(self, repo, large_concept_scheme_dataset):
        result = repo.list_concept_schemes(limit=None, sort_by="title", sort_order="asc")
        titles = [s.title for s in result]
        assert titles == sorted(titles)

    def test_list_concept_schemes_sort_by_title_desc(self, repo, large_concept_scheme_dataset):
        result = repo.list_concept_schemes(limit=None, sort_by="title", sort_order="desc")
        titles = [s.title for s in result]
        assert titles == sorted(titles, reverse=True)


class TestConceptSchemeSearch:
    """Tests for concept scheme text search."""

    def test_list_concept_schemes_search_exact_match(self, repo, large_concept_scheme_dataset):
        result = repo.list_concept_schemes(query="Animals")
        assert len(result) == 1
        assert result[0].title == "Animals"

    def test_list_concept_schemes_search_partial_match(self, repo, large_concept_scheme_dataset):
        result = repo.list_concept_schemes(query="sperm")
        assert len(result) == 2
        titles = [s.title for s in result]
        assert "Gymnosperms" in titles
        assert "Angiosperms" in titles

    def test_list_concept_schemes_search_case_insensitive(self, repo, large_concept_scheme_dataset):
        result_lower = repo.list_concept_schemes(query="animals")
        result_upper = repo.list_concept_schemes(query="Animals")
        result_mixed = repo.list_concept_schemes(query="AnImAlS")
        assert len(result_lower) == 1
        assert len(result_upper) == 1
        assert len(result_mixed) == 1


class TestConceptSchemeCount:
    """Tests for concept scheme count methods."""

    def test_count_concept_schemes_total(self, repo, large_concept_scheme_dataset):
        count = repo.count_concept_schemes()
        assert count == 15

    def test_count_concept_schemes_with_taxonomy_filter(
        self, repo, sample_taxonomy, large_concept_scheme_dataset
    ):
        count = repo.count_concept_schemes(taxonomy_id=sample_taxonomy.id)
        assert count == 15

    def test_count_concept_schemes_with_query(self, repo, large_concept_scheme_dataset):
        count = repo.count_concept_schemes(query="sperm")
        result = repo.list_concept_schemes(query="sperm", limit=None)
        assert count == len(result)

    def test_count_concept_schemes_with_both_filters(
        self, repo, sample_taxonomy, large_concept_scheme_dataset
    ):
        count = repo.count_concept_schemes(taxonomy_id=sample_taxonomy.id, query="sperm")
        result = repo.list_concept_schemes(
            taxonomy_id=sample_taxonomy.id, query="sperm", limit=None
        )
        assert count == len(result)


class TestClassPagination:
    """Tests for class pagination and filtering."""

    def test_list_classes_pagination_limit(self, repo, large_class_dataset):
        result = repo.list_classes(limit=5)
        assert len(result) == 5

    def test_list_classes_pagination_offset(self, repo, large_class_dataset):
        first_batch = repo.list_classes(limit=5, offset=0)
        second_batch = repo.list_classes(limit=5, offset=5)
        assert len(first_batch) == 5
        assert len(second_batch) == 5
        assert first_batch[0].id != second_batch[0].id

    def test_list_classes_pagination_none_limit(self, repo, large_class_dataset):
        result = repo.list_classes(limit=None)
        assert len(result) == 20

    def test_list_classes_with_concept_scheme_filter(
        self, repo, sample_concept_scheme, large_class_dataset
    ):
        result = repo.list_classes(concept_scheme_id=sample_concept_scheme.id)
        assert len(result) == 20
        assert all(cls.concept_scheme_id == sample_concept_scheme.id for cls in result)

    def test_list_classes_with_parent_class_filter(self, repo, large_class_dataset):
        parent_cls = large_class_dataset[0]
        child = Class(
            id="child-1",
            concept_scheme_id=parent_cls.concept_scheme_id,
            taxonomy_id=parent_cls.taxonomy_id,
            title="Child Class",
            parent_class_id=parent_cls.id,
        )
        repo.save_class(child)

        result = repo.list_classes(parent_class_id=parent_cls.id)
        assert len(result) == 1
        assert result[0].id == "child-1"


class TestClassCount:
    """Tests for class count methods."""

    def test_count_classes_total(self, repo, large_class_dataset):
        count = repo.count_classes()
        assert count == 20

    def test_count_classes_with_concept_scheme_filter(
        self, repo, sample_concept_scheme, large_class_dataset
    ):
        count = repo.count_classes(concept_scheme_id=sample_concept_scheme.id)
        assert count == 20

    def test_count_classes_matches_list_length(self, repo, large_class_dataset):
        count = repo.count_classes()
        result = repo.list_classes(limit=None)
        assert count == len(result)


class TestPropertyDefinitionCount:
    """Tests for property definition count methods."""

    def test_count_property_definitions_total(self, repo):
        prop = PropertyDefinition(
            id="prop-1",
            identifier="is_subclass_of",
            title="Is Subclass Of",
            is_relevant=True,
        )
        repo.save_property_definition(prop)

        count = repo.count_property_definitions()
        assert count >= 1

    def test_count_property_definitions_with_relevance_filter(self, repo):
        prop1 = PropertyDefinition(
            id="prop-1",
            identifier="is_subclass_of",
            title="Is Subclass Of",
            is_relevant=True,
        )
        prop2 = PropertyDefinition(
            id="prop-2",
            identifier="old_property",
            title="Old Property",
            is_relevant=False,
        )
        repo.save_property_definition(prop1)
        repo.save_property_definition(prop2)

        count_relevant = repo.count_property_definitions(is_relevant=True)
        count_irrelevant = repo.count_property_definitions(is_relevant=False)

        assert count_relevant >= 1
        assert count_irrelevant >= 1


class TestPropertyDefinitionList:
    """Tests for property definition list methods."""

    def test_list_property_definitions_pagination(self, repo):
        for i in range(15):
            prop = PropertyDefinition(
                id=f"prop-{i}",
                identifier=f"property_{i}",
                title=f"Property {i}",
                is_relevant=i % 2 == 0,
            )
            repo.save_property_definition(prop)

        result = repo.list_property_definitions(limit=5)
        assert len(result) == 5

    def test_list_property_definitions_with_relevance_filter(self, repo):
        for i in range(10):
            prop = PropertyDefinition(
                id=f"prop-{i}",
                identifier=f"property_{i}",
                title=f"Property {i}",
                is_relevant=i % 2 == 0,
            )
            repo.save_property_definition(prop)

        result = repo.list_property_definitions(is_relevant=True, limit=None)
        assert all(p.is_relevant for p in result)

    def test_list_property_definitions_sorting(self, repo):
        for i in range(5):
            prop = PropertyDefinition(
                id=f"prop-{i}",
                identifier=f"property_{i}",
                title=f"Property Title {5 - i}",
                is_relevant=True,
            )
            repo.save_property_definition(prop)

        result = repo.list_property_definitions(sort_by="title", sort_order="asc", limit=None)
        titles = [p.title for p in result]
        assert titles == sorted(titles)


class TestEdgeCases:
    """Tests for edge cases and real SQLite behavior."""

    def test_empty_database_list(self, repo):
        result = repo.list_taxonomies()
        assert len(result) == 0

    def test_empty_database_count(self, repo):
        count = repo.count_taxonomies()
        assert count == 0

    def test_pagination_consistency(self, repo, large_taxonomy_dataset):
        first_call = repo.list_taxonomies(limit=5, offset=0)
        second_call = repo.list_taxonomies(limit=5, offset=0)
        assert [t.id for t in first_call] == [t.id for t in second_call]

    def test_count_vs_list_total_match(self, repo, large_taxonomy_dataset):
        count = repo.count_taxonomies()
        all_results = repo.list_taxonomies(limit=None)
        assert count == len(all_results)

    def test_offset_greater_than_total(self, repo, large_taxonomy_dataset):
        result = repo.list_taxonomies(limit=10, offset=1000)
        assert len(result) == 0

    def test_search_empty_string_returns_all(self, repo, large_taxonomy_dataset):
        count = repo.count_taxonomies()
        count_with_empty_query = repo.count_taxonomies(query="")
        assert count == count_with_empty_query

    def test_sort_order_case_insensitive(self, repo, large_taxonomy_dataset):
        result_lower = repo.list_taxonomies(sort_order="desc", limit=5)
        result_upper = repo.list_taxonomies(sort_order="DESC", limit=5)
        assert [t.id for t in result_lower] == [t.id for t in result_upper]
