"""
SQLite adapter implementing the ExtractionRepository port.

Provides persistence for extraction results, including extracted entities,
layer execution metadata, and performance metrics.

Key responsibilities:
- Store extraction results with all entities and layer metadata
- Retrieve extraction results by ID
- List extraction results with pagination
"""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import desc

from domain.extraction.entities import ExtractionResult, ExtractedEntity
from domain.extraction.value_objects import ExtractionLayerResult

from adapters.persistence.sqlite.models import ExtractionResult as ExtractionResultORM


class SQLiteExtractionRepository:
    """
    SQLAlchemy-based implementation of the ExtractionRepository port (structural subtyping).

    Manages persistence of extraction results using SQLAlchemy ORM.
    Results are stored with full entity and layer execution metadata.

    Attributes:
        session_factory: SQLAlchemy sessionmaker for creating isolated sessions
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        """
        Initialize the repository with a database session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker for creating isolated sessions
        """
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """
        Create and return a new isolated session.

        Returns:
            SQLAlchemy Session instance
        """
        return self.session_factory()

    def save_extraction_result(self, result: ExtractionResult) -> ExtractionResult:
        """
        Save an extraction result to persistent storage.

        Converts the domain entity to ORM model, persists it, and returns
        the saved result. All entity and layer metadata is stored as JSON.

        Args:
            result: The ExtractionResult to save

        Returns:
            The saved ExtractionResult (may have updated metadata like id or timestamp)
        """
        session = self._get_session()
        try:
            # Convert domain entities to JSON-serializable format
            entities_json = [
                {
                    "id": entity.id,
                    "label": entity.label,
                    "entity_type": entity.entity_type,
                    "source_layer": entity.source_layer,
                    "confidence": entity.confidence,
                    "uri": entity.uri,
                    "description": entity.description,
                    "properties": entity.properties,
                }
                for entity in result.extracted_entities
            ]

            layers_json = [
                {
                    "layer_number": layer.layer_number,
                    "layer_name": layer.layer_name,
                    "entities_found": layer.entities_found,
                    "duration_ms": layer.duration_ms,
                    "success": layer.success,
                    "error_message": layer.error_message,
                }
                for layer in result.layers_executed
            ]

            # Create ORM model
            orm_result = ExtractionResultORM(
                id=result.id,
                text=result.text,
                extracted_entities=entities_json,
                layers_executed=layers_json,
                total_duration_ms=result.total_duration_ms,
                created_at=result.created_at,
            )

            # Persist and flush to ensure the record is saved
            session.add(orm_result)
            session.commit()

            return result

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_extraction_result(self, result_id: str) -> ExtractionResult | None:
        """
        Retrieve an extraction result by ID.

        Converts ORM model back to domain entity, reconstructing all
        entities and layer metadata from JSON.

        Args:
            result_id: The ID of the extraction result

        Returns:
            The ExtractionResult or None if not found
        """
        session = self._get_session()
        try:
            orm_result = session.query(ExtractionResultORM).filter(
                ExtractionResultORM.id == result_id
            ).first()

            if not orm_result:
                return None

            return self._orm_to_domain(orm_result)

        finally:
            session.close()

    def list_extraction_results(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionResult]:
        """
        List extraction results with pagination.

        Results are ordered by created_at descending (most recent first).

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of ExtractionResult objects
        """
        session = self._get_session()
        try:
            orm_results = session.query(ExtractionResultORM).order_by(
                desc(ExtractionResultORM.created_at)
            ).offset(offset).limit(limit).all()

            return [self._orm_to_domain(orm) for orm in orm_results]

        finally:
            session.close()

    def _orm_to_domain(self, orm_result: ExtractionResultORM) -> ExtractionResult:
        """
        Convert ORM model to domain entity.

        Reconstructs ExtractedEntity and ExtractionLayerResult objects
        from JSON storage.

        Args:
            orm_result: ORM model instance

        Returns:
            Domain ExtractionResult entity
        """
        # Reconstruct extracted entities from JSON
        extracted_entities = [
            ExtractedEntity(
                id=entity_data.get("id", ""),  # type: ignore[assignment]
                label=entity_data.get("label", ""),  # type: ignore[assignment]
                entity_type=entity_data.get("entity_type", ""),  # type: ignore[assignment]
                source_layer=entity_data.get("source_layer", 0),  # type: ignore[assignment]
                confidence=entity_data.get("confidence", 0.0),  # type: ignore[assignment]
                uri=entity_data.get("uri"),  # type: ignore[assignment]
                description=entity_data.get("description"),  # type: ignore[assignment]
                properties=entity_data.get("properties", {}),  # type: ignore[assignment]
            )
            for entity_data in (orm_result.extracted_entities or [])  # type: ignore[union-attr]
        ]

        # Reconstruct layer results from JSON
        layers_executed = [
            ExtractionLayerResult(
                layer_number=layer_data.get("layer_number", 0),  # type: ignore[assignment]
                layer_name=layer_data.get("layer_name", ""),  # type: ignore[assignment]
                entities_found=layer_data.get("entities_found", 0),  # type: ignore[assignment]
                duration_ms=layer_data.get("duration_ms", 0),  # type: ignore[assignment]
                success=layer_data.get("success", False),  # type: ignore[assignment]
                error_message=layer_data.get("error_message"),  # type: ignore[assignment]
            )
            for layer_data in (orm_result.layers_executed or [])  # type: ignore[union-attr]
        ]

        # Create domain entity
        return ExtractionResult(
            id=orm_result.id or "",  # type: ignore[arg-type]
            text=orm_result.text or "",  # type: ignore[arg-type]
            extracted_entities=extracted_entities,
            layers_executed=layers_executed,
            total_duration_ms=orm_result.total_duration_ms or 0,  # type: ignore[arg-type]
            created_at=orm_result.created_at or datetime.now(timezone.utc),  # type: ignore[arg-type]
        )
