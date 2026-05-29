"""
Use case for loading a pre-curated demo dataset into the ontology repository.

This service is intentionally thin. It validates the dataset name against the
loader's registered list, synthesizes a `source_run_id` for provenance, and
delegates the actual materialization to the injected DemoDatasetLoader port.

Keeping the loader behind a port preserves hexagonal isolation: the domain knows
nothing about JSON files, filesystem paths, or SQL.
"""

from __future__ import annotations

import uuid

from .exceptions import DemoDatasetNotFoundError
from .ports import DemoDatasetLoader
from .value_objects import DemoDatasetDescriptor, LoadResult


class LoadDemoDataset:
    """
    Use case for loading a demo dataset.

    Validates the requested dataset name, generates a synthetic provenance id,
    and delegates to the DemoDatasetLoader port to materialize the entities.
    """

    def __init__(self, loader: DemoDatasetLoader) -> None:
        """
        Initialize the use case with a DemoDatasetLoader port implementation.

        Args:
            loader: Port implementation responsible for reading the canon and
                writing entities through the ontology repository.
        """
        self._loader = loader

    def list_available(self) -> tuple[DemoDatasetDescriptor, ...]:
        """
        List demo datasets available to load.

        Returns:
            Tuple of descriptors, one per available dataset.
        """
        return self._loader.list_available()

    def execute(self, name: str) -> LoadResult:
        """
        Load the named demo dataset.

        Args:
            name: Stable identifier of the dataset (e.g. 'software-architecture').

        Returns:
            LoadResult with counts of each persisted entity type.

        Raises:
            DemoDatasetNotFoundError: if `name` is not a registered dataset.
            DemoDatasetAlreadyLoadedError: if the dataset is already loaded.
        """
        if not name or not name.strip():
            raise DemoDatasetNotFoundError(name or "")

        normalized = name.strip()
        available = {descriptor.name for descriptor in self._loader.list_available()}
        if normalized not in available:
            raise DemoDatasetNotFoundError(normalized)

        run_id = f"demo:{normalized}:{uuid.uuid4()}"
        return self._loader.load(normalized, run_id)
