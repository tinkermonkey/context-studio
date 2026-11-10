"""
Which dataset a write goes into.

A taxonomy with one dataset needs no choice: writes go into it. A taxonomy with
none gets a dataset `default` on its first individual. With several, a write
must name one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from domain.ontology.entities import Dataset
from domain.ontology.exceptions import (
    DatasetMismatchError,
    DatasetRequiredError,
    EntityNotFoundError,
)
from domain.ontology.ports import OntologyRepository

DEFAULT_DATASET_IDENTIFIER = "default"


def resolve_dataset_id(
    repo: OntologyRepository, taxonomy_id: str, dataset_id: str | None = None
) -> str:
    """
    Return the dataset a write into a taxonomy goes into.

    Args:
        repo: The ontology repository
        taxonomy_id: The taxonomy whose schema the written data uses
        dataset_id: The dataset the caller named, if any

    Returns:
        The named dataset's id, else the taxonomy's only dataset's id (created
        as `default` when the taxonomy has none yet)

    Raises:
        EntityNotFoundError: If the named dataset does not exist
        DatasetMismatchError: If the named dataset belongs to another taxonomy
        DatasetRequiredError: If none is named and the taxonomy has several
    """
    if dataset_id is not None:
        dataset = repo.get_dataset(dataset_id)
        if dataset is None:
            raise EntityNotFoundError("Dataset", dataset_id)
        if dataset.taxonomy_id != taxonomy_id:
            raise DatasetMismatchError(
                f"Dataset '{dataset.identifier}' belongs to another taxonomy than {taxonomy_id}"
            )
        return dataset.id
    datasets = repo.list_datasets(taxonomy_id=taxonomy_id)
    if len(datasets) == 1:
        return datasets[0].id
    if datasets:
        raise DatasetRequiredError(taxonomy_id, sorted(d.identifier for d in datasets))
    now = datetime.now(timezone.utc)
    return repo.save_dataset(
        Dataset(
            id=str(uuid4()),
            taxonomy_id=taxonomy_id,
            identifier=DEFAULT_DATASET_IDENTIFIER,
            title="Default",
            created_at=now,
            last_modified=now,
        )
    ).id
