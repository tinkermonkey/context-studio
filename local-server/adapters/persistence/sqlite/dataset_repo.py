"""
SQLite implementation of the DatasetRepository port.

Provides persistence for dataset metadata and computes metrics by querying
the ontology entities.
"""

import logging
from typing import Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import (
    Dataset as DatasetModel,
)
from adapters.persistence.sqlite.models import (
    OntologyEntity,
)
from adapters.persistence.sqlite.models import (
    Relationship as RelationshipModel,
)
from domain.admin.entities import Dataset, DatasetMetrics
from domain.admin.exceptions import DatasetNotFoundError

logger = logging.getLogger(__name__)


class SQLiteDatasetRepository:
    """
    SQLite implementation of DatasetRepository.

    Computes metrics by querying the OntologyEntity table.
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        """
        Initialize repository with session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker for creating sessions
        """
        self.session_factory = session_factory

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """
        Retrieve a dataset by ID.

        Args:
            dataset_id: The dataset ID

        Returns:
            Dataset if found, None otherwise

        Raises:
            RuntimeError: If a database operation fails
        """
        try:
            with self.session_factory() as session:
                row = session.execute(
                    select(DatasetModel).where(DatasetModel.id == dataset_id)
                ).scalar_one_or_none()
                return self._to_domain(row) if row else None
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving dataset {dataset_id}: {e}")
            raise RuntimeError(f"Failed to retrieve dataset: {str(e)}") from e

    def list_datasets(self) -> Sequence[Dataset]:
        """
        List all datasets.

        Returns:
            Sequence of all datasets

        Raises:
            RuntimeError: If a database operation fails
        """
        try:
            with self.session_factory() as session:
                rows = session.execute(select(DatasetModel)).scalars().all()
                return [self._to_domain(row) for row in rows]
        except SQLAlchemyError as e:
            logger.error(f"Database error listing datasets: {e}")
            raise RuntimeError(f"Failed to list datasets: {str(e)}") from e

    def save_dataset(self, dataset: Dataset) -> Dataset:
        """
        Save a dataset (create or update).

        Args:
            dataset: The dataset to save

        Returns:
            The saved dataset

        Raises:
            RuntimeError: If a database operation fails
        """
        try:
            with self.session_factory() as session:
                row = DatasetModel(
                    id=dataset.id,
                    title=dataset.title,
                    filename=dataset.filename,
                    description=dataset.description,
                    created_at=dataset.created_at,
                    last_accessed=dataset.last_accessed,
                    schema_version=dataset.schema_version,
                    layers_count=dataset.metrics.layers_count,
                    domains_count=dataset.metrics.domains_count,
                    terms_count=dataset.metrics.terms_count,
                    relationships_count=dataset.metrics.relationships_count,
                    individuals_count=dataset.metrics.individuals_count,
                    is_active=dataset.is_active,
                    version=dataset.version,
                )
                session.merge(row)
                session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Database error saving dataset {dataset.id}: {e}")
            raise RuntimeError(f"Failed to save dataset: {str(e)}") from e
        return dataset

    def delete_dataset(self, dataset_id: str) -> bool:
        """
        Delete a dataset by ID.

        Args:
            dataset_id: The dataset ID to delete

        Returns:
            True if deleted, False if not found

        Raises:
            RuntimeError: If a database operation fails
        """
        try:
            with self.session_factory() as session:
                dataset = session.execute(
                    select(DatasetModel).where(DatasetModel.id == dataset_id)
                ).scalar_one_or_none()
                if dataset:
                    session.delete(dataset)
                    session.commit()
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting dataset {dataset_id}: {e}")
            raise RuntimeError(f"Failed to delete dataset: {str(e)}") from e

    def get_active_dataset(self) -> Optional[Dataset]:
        """
        Get the currently active dataset.

        Returns:
            Active dataset if one is set, None otherwise

        Raises:
            RuntimeError: If a database operation fails
        """
        try:
            with self.session_factory() as session:
                row = session.execute(
                    select(DatasetModel).where(DatasetModel.is_active)
                ).scalar_one_or_none()
                return self._to_domain(row) if row else None
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving active dataset: {e}")
            raise RuntimeError(f"Failed to retrieve active dataset: {str(e)}") from e

    def set_active_dataset(self, dataset_id: str) -> Dataset:
        """
        Set a dataset as active and deactivate others.

        Args:
            dataset_id: The dataset ID to activate

        Returns:
            The activated dataset

        Raises:
            DatasetNotFoundError: If the dataset does not exist
            RuntimeError: If a database operation fails
        """
        try:
            with self.session_factory() as session:
                # Deactivate all other datasets
                session.execute(
                    update(DatasetModel).where(DatasetModel.is_active).values(is_active=False)
                )
                # Activate the target dataset
                dataset_row = session.execute(
                    select(DatasetModel).where(DatasetModel.id == dataset_id)
                ).scalar_one_or_none()
                if dataset_row is None:
                    raise DatasetNotFoundError(f"Dataset with ID {dataset_id} not found")
                dataset_row.is_active = True
                session.commit()
                return self._to_domain(dataset_row)
        except DatasetNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error setting active dataset {dataset_id}: {e}")
            raise RuntimeError(f"Failed to set active dataset: {str(e)}") from e

    def compute_metrics(self, dataset_id: str) -> DatasetMetrics:
        """
        Compute metrics by querying the ontology entities.

        Args:
            dataset_id: The dataset ID (currently unused as metrics are global)

        Returns:
            DatasetMetrics with current entity counts

        Raises:
            RuntimeError: If a database operation fails
        """
        try:
            with self.session_factory() as session:
                # Count by node_type discriminator
                taxonomies = (
                    session.scalar(
                        select(func.count(OntologyEntity.id)).where(
                            OntologyEntity.node_type == "taxonomy"
                        )
                    )
                    or 0
                )
                schemes = (
                    session.scalar(
                        select(func.count(OntologyEntity.id)).where(
                            OntologyEntity.node_type == "concept_scheme"
                        )
                    )
                    or 0
                )
                classes = (
                    session.scalar(
                        select(func.count(OntologyEntity.id)).where(
                            OntologyEntity.node_type == "class"
                        )
                    )
                    or 0
                )
                individuals = (
                    session.scalar(
                        select(func.count(OntologyEntity.id)).where(
                            OntologyEntity.node_type == "individual"
                        )
                    )
                    or 0
                )
                relationships = session.scalar(select(func.count(RelationshipModel.id))) or 0

            return DatasetMetrics(
                layers_count=taxonomies,
                domains_count=schemes,
                terms_count=classes,
                relationships_count=relationships,
                individuals_count=individuals,
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error computing metrics for dataset {dataset_id}: {e}")
            raise RuntimeError(f"Failed to compute metrics: {str(e)}") from e

    def _to_domain(self, row: DatasetModel) -> Dataset:
        """Convert ORM model to domain entity."""
        return Dataset(
            id=row.id,
            title=row.title,
            filename=row.filename,
            description=row.description,
            created_at=row.created_at,
            last_accessed=row.last_accessed or row.created_at,
            schema_version=row.schema_version,
            metrics=DatasetMetrics(
                layers_count=row.layers_count,
                domains_count=row.domains_count,
                terms_count=row.terms_count,
                relationships_count=row.relationships_count,
                individuals_count=row.individuals_count,
            ),
            is_active=row.is_active,
            version=row.version,
        )
