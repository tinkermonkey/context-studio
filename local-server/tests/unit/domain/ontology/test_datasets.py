"""Unit tests for which dataset a write goes into (domain.ontology.datasets, #1484)."""

import pytest

from domain.ontology.datasets import resolve_dataset_id
from domain.ontology.entities import Dataset
from domain.ontology.exceptions import (
    DatasetMismatchError,
    DatasetRequiredError,
    EntityNotFoundError,
)
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


def _dataset(identifier: str, taxonomy_id: str = "tax") -> Dataset:
    return Dataset(
        id=f"ds-{identifier}",
        taxonomy_id=taxonomy_id,
        identifier=identifier,
        title=identifier.title(),
    )


def test_a_taxonomy_without_datasets_gets_a_default_one():
    repo = FakeOntologyRepository()

    dataset_id = resolve_dataset_id(repo, "tax")

    [dataset] = repo.list_datasets(taxonomy_id="tax")
    assert (dataset.id, dataset.identifier) == (dataset_id, "default")


def test_a_taxonomys_only_dataset_is_used():
    repo = FakeOntologyRepository()
    repo.save_dataset(_dataset("context-studio"))

    assert resolve_dataset_id(repo, "tax") == "ds-context-studio"


def test_several_datasets_need_one_named():
    repo = FakeOntologyRepository()
    repo.save_dataset(_dataset("beta"))
    repo.save_dataset(_dataset("alpha"))

    with pytest.raises(DatasetRequiredError) as raised:
        resolve_dataset_id(repo, "tax")
    assert raised.value.identifiers == ["alpha", "beta"]
    assert resolve_dataset_id(repo, "tax", "ds-beta") == "ds-beta"


def test_a_named_dataset_must_exist_and_belong_to_the_taxonomy():
    repo = FakeOntologyRepository()
    repo.save_dataset(_dataset("elsewhere", taxonomy_id="other"))

    with pytest.raises(EntityNotFoundError):
        resolve_dataset_id(repo, "tax", "ds-missing")
    with pytest.raises(DatasetMismatchError):
        resolve_dataset_id(repo, "tax", "ds-elsewhere")


@pytest.mark.parametrize("identifier", ["", "-lead", "Has Space", "x"])
def test_a_dataset_identifier_is_a_slug(identifier):
    with pytest.raises(ValueError):
        _dataset(identifier)


def test_a_dataset_identifier_may_use_hyphens():
    assert _dataset("context-studio").identifier == "context-studio"
