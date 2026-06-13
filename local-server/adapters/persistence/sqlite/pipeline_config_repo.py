"""
Repository for user-created pipeline configuration persistence.

Manages CRUD operations for pipeline configurations in operations.db.
System configurations (code-defined) are not stored here; they live in
the in-memory PipelineConfigurationRegistry.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.operations.models import PipelineConfiguration
from domain.pipelines.exceptions import PipelineStorageError
from utils.logger import get_logger

logger = get_logger(__name__)


def _slugify_name(name: str) -> str:
    """Generate a config_ref slug from a configuration name."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower())
    slug = slug.strip("_")[:28]
    return "cfg_" + slug if slug else "cfg_" + uuid.uuid4().hex[:6]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineConfigurationRepository:
    """Repository for user-created pipeline configurations in operations.db."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def _session(self) -> Session:
        return self._session_factory()

    def create(
        self,
        pipeline_type: str,
        implementation_id: str,
        name: str,
        provider: str,
        model: str,
        user_prompt_template: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 800,
        top_p: float = 0.9,
        enabled: bool = True,
    ) -> PipelineConfiguration:
        """Create and persist a new user pipeline configuration."""
        config_id = str(uuid.uuid4())
        base_ref = _slugify_name(name)
        existing_refs = self.list_known_config_refs(pipeline_type, implementation_id)
        if base_ref in existing_refs:
            config_ref = f"{base_ref}_{uuid.uuid4().hex[:6]}"
        else:
            config_ref = base_ref
        now = _now_iso()

        record = PipelineConfiguration(
            id=config_id,
            config_ref=config_ref,
            pipeline_type=pipeline_type,
            implementation_id=implementation_id,
            name=name,
            description=description,
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            enabled=enabled,
            version=1,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )

        try:
            with self._session() as session:
                session.add(record)
                session.commit()
                session.refresh(record)
                return record
        except SQLAlchemyError as exc:
            raise PipelineStorageError(f"Failed to create pipeline configuration: {exc}") from exc

    def get(self, config_id: str) -> Optional[PipelineConfiguration]:
        """Get a configuration by ID. Returns None if deleted or not found."""
        try:
            with self._session() as session:
                return (
                    session.query(PipelineConfiguration)
                    .filter(
                        PipelineConfiguration.id == config_id,
                        PipelineConfiguration.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                    .first()
                )
        except SQLAlchemyError as exc:
            raise PipelineStorageError(f"Failed to get pipeline configuration: {exc}") from exc

    def list_for_type(
        self, pipeline_type: str, implementation_id: str
    ) -> list[PipelineConfiguration]:
        """List all non-deleted configurations for a pipeline type and implementation."""
        try:
            with self._session() as session:
                return (
                    session.query(PipelineConfiguration)
                    .filter(
                        PipelineConfiguration.pipeline_type == pipeline_type,
                        PipelineConfiguration.implementation_id == implementation_id,
                        PipelineConfiguration.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                    .order_by(PipelineConfiguration.created_at)
                    .all()
                )
        except SQLAlchemyError as exc:
            raise PipelineStorageError(
                f"Failed to list pipeline configurations: {exc}"
            ) from exc

    def list_all(self) -> list[PipelineConfiguration]:
        """List all non-deleted user configurations (for startup registry loading)."""
        try:
            with self._session() as session:
                return (
                    session.query(PipelineConfiguration)
                    .filter(PipelineConfiguration.deleted_at.is_(None))  # type: ignore[union-attr]
                    .all()
                )
        except SQLAlchemyError as exc:
            raise PipelineStorageError(
                f"Failed to list all pipeline configurations: {exc}"
            ) from exc

    def update(
        self,
        config_id: str,
        name: str,
        provider: str,
        model: str,
        user_prompt_template: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 800,
        top_p: float = 0.9,
        enabled: bool = True,
    ) -> Optional[PipelineConfiguration]:
        """Update a configuration, incrementing its version number."""
        try:
            with self._session() as session:
                record = (
                    session.query(PipelineConfiguration)
                    .filter(
                        PipelineConfiguration.id == config_id,
                        PipelineConfiguration.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                    .first()
                )
                if record is None:
                    return None

                record.name = name
                record.description = description
                record.provider = provider
                record.model = model
                record.system_prompt = system_prompt
                record.user_prompt_template = user_prompt_template
                record.temperature = temperature
                record.max_tokens = max_tokens
                record.top_p = top_p
                record.enabled = enabled
                record.version = record.version + 1
                record.updated_at = _now_iso()

                session.commit()
                session.refresh(record)
                return record
        except SQLAlchemyError as exc:
            raise PipelineStorageError(
                f"Failed to update pipeline configuration: {exc}"
            ) from exc

    def list_known_config_refs(self, pipeline_type: str, implementation_id: str) -> set[str]:
        """Return all config_refs for a type+impl (including deleted), for deduplication."""
        try:
            with self._session() as session:
                rows = (
                    session.query(PipelineConfiguration.config_ref)  # type: ignore[call-overload]
                    .filter(
                        PipelineConfiguration.pipeline_type == pipeline_type,
                        PipelineConfiguration.implementation_id == implementation_id,
                    )
                    .all()
                )
                return {row[0] for row in rows}
        except SQLAlchemyError as exc:
            raise PipelineStorageError(
                f"Failed to list config refs: {exc}"
            ) from exc

    def soft_delete(self, config_id: str) -> bool:
        """Soft-delete a configuration. Returns True if deleted, False if not found."""
        try:
            with self._session() as session:
                record = (
                    session.query(PipelineConfiguration)
                    .filter(
                        PipelineConfiguration.id == config_id,
                        PipelineConfiguration.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                    .first()
                )
                if record is None:
                    return False

                record.deleted_at = _now_iso()
                session.commit()
                return True
        except SQLAlchemyError as exc:
            raise PipelineStorageError(
                f"Failed to delete pipeline configuration: {exc}"
            ) from exc
