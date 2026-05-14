"""
Fake implementation of DatasetRepository for testing.
"""

from typing import Optional, Sequence
from domain.admin.entities import Dataset, DatasetMetrics
from domain.admin.ports import DatasetRepository


class FakeDatasetRepository(DatasetRepository):
    """Fake in-memory implementation of DatasetRepository for testing."""

    def __init__(self):
        """Initialize with empty dataset store."""
        self._datasets: dict[str, Dataset] = {}
        self._active_dataset_id: Optional[str] = None

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get a dataset by ID."""
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> Sequence[Dataset]:
        """List all datasets."""
        return list(self._datasets.values())

    def save_dataset(self, dataset: Dataset) -> Dataset:
        """Save or update a dataset."""
        self._datasets[dataset.id] = dataset
        return dataset

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset by ID."""
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            if self._active_dataset_id == dataset_id:
                self._active_dataset_id = None
            return True
        return False

    def get_active_dataset(self) -> Optional[Dataset]:
        """Get the currently active dataset."""
        if self._active_dataset_id:
            return self._datasets.get(self._active_dataset_id)
        return None

    def set_active_dataset(self, dataset_id: str) -> Dataset:
        """Set a dataset as active and deactivate others."""
        # Deactivate all others
        for dataset in self._datasets.values():
            dataset.is_active = False

        # Activate the target
        dataset = self._datasets[dataset_id]
        dataset.is_active = True
        self._active_dataset_id = dataset_id
        return dataset

    def compute_metrics(self, dataset_id: str) -> DatasetMetrics:
        """Compute metrics for a dataset."""
        # Return stub metrics for testing
        return DatasetMetrics(
            layers_count=0,
            domains_count=0,
            terms_count=0,
            relationships_count=0,
            individuals_count=0,
        )
