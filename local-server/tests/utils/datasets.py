"""Test helper: save an individual straight to the repository, in its taxonomy's dataset."""

from typing import Any

from adapters.persistence.sqlite.models import Dataset as DatasetModel
from adapters.persistence.sqlite.models import OntologyEntity
from domain.ontology.datasets import resolve_dataset_id
from domain.ontology.entities import Individual
from domain.ontology.ports import OntologyRepository


def save_in_dataset(repo: OntologyRepository, individual: Individual) -> Individual:
    """
    Save the individual, filling in its taxonomy's dataset when it names none.

    Only for tests that write individuals below OntologyService: the repository
    refuses a new individual without a dataset.
    """
    if individual.dataset_id is None:
        first_class = repo.get_class(individual.class_ids[0])
        if first_class is not None:
            individual.dataset_id = resolve_dataset_id(repo, first_class.taxonomy_id)
    return repo.save_individual(individual)


SEED_DATASET_ID = "00000000-0000-0000-0000-00000000da7a"


def add_seed_dataset(session: Any) -> str:
    """Add a taxonomy and a dataset over it to an ORM session; return the dataset id."""
    taxonomy_id = "00000000-0000-0000-0000-0000000074a1"
    session.add(OntologyEntity(id=taxonomy_id, node_type="taxonomy", title="Seed taxonomy"))
    session.flush()
    session.add(
        DatasetModel(
            id=SEED_DATASET_ID, taxonomy_id=taxonomy_id, identifier="default", title="Default"
        )
    )
    session.flush()
    return SEED_DATASET_ID
