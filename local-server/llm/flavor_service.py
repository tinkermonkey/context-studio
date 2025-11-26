"""
Service for managing pipeline flavors.
"""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import text
import uuid

from .models import (
    PipelineFlavor, 
    CreatePipelineFlavorRequest, 
    UpdatePipelineFlavorRequest,
    PipelineType,
    LLMConfig
)
from .exceptions import FlavorNotFoundError, FlavorValidationError
from .default_flavors import DefaultFlavorProvider
from pipeline.manager import get_pipeline_session
from utils.logger import get_logger


class PipelineFlavorService:
    """Service for managing pipeline flavors"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def create_flavor(self, request: CreatePipelineFlavorRequest) -> PipelineFlavor:
        """Create a new pipeline flavor"""
        with get_pipeline_session() as db:
            # Check for duplicate title within pipeline
            existing = db.execute(text("""
                SELECT id FROM pipeline_flavors
                WHERE pipeline = :pipeline AND title = :title
            """), {
                "pipeline": request.pipeline.value,
                "title": request.title
            }).fetchone()

            if existing:
                raise FlavorValidationError(
                    f"Flavor with title '{request.title}' already exists for pipeline '{request.pipeline.value}'"
                )

            # Insert new flavor
            flavor_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            db.execute(text("""
                INSERT INTO pipeline_flavors (
                    id, pipeline, title, llm_provider, llm_model, llm_config,
                    system_prompt, user_prompt, version, enabled, created_at, updated_at
                ) VALUES (
                    :id, :pipeline, :title, :llm_provider, :llm_model, :llm_config,
                    :system_prompt, :user_prompt, :version, :enabled, :created_at, :updated_at
                )
            """), {
                "id": flavor_id,
                "pipeline": request.pipeline.value,
                "title": request.title,
                "llm_provider": request.llm_provider,
                "llm_model": request.llm_model,
                "llm_config": request.llm_config.model_dump_json(),
                "system_prompt": request.system_prompt,
                "user_prompt": request.user_prompt,
                "version": 1,
                "enabled": request.enabled,
                "created_at": now,
                "updated_at": now
            })

            db.commit()

            # Return the created flavor
            return self.get_flavor_by_id(flavor_id)
    
    def update_flavor(self, flavor_id: str, request: UpdatePipelineFlavorRequest) -> PipelineFlavor:
        """Update an existing pipeline flavor"""
        with get_pipeline_session() as db:
            # Get existing flavor
            existing = db.execute(text("""
                SELECT * FROM pipeline_flavors WHERE id = :id
            """), {"id": flavor_id}).fetchone()

            if not existing:
                raise FlavorNotFoundError(f"Flavor with ID '{flavor_id}' not found")

            # Check if trying to rename Default flavor
            if existing[2] == "Default" and request.title and request.title != "Default":
                raise FlavorValidationError("Cannot rename the Default flavor")

            # Build update query dynamically
            update_fields = []
            params = {"id": flavor_id}

            if request.title is not None:
                update_fields.append("title = :title")
                params["title"] = request.title

            if request.llm_provider is not None:
                update_fields.append("llm_provider = :llm_provider")
                params["llm_provider"] = request.llm_provider

            if request.llm_model is not None:
                update_fields.append("llm_model = :llm_model")
                params["llm_model"] = request.llm_model

            if request.llm_config is not None:
                update_fields.append("llm_config = :llm_config")
                params["llm_config"] = request.llm_config.model_dump_json()

            if request.system_prompt is not None:
                update_fields.append("system_prompt = :system_prompt")
                params["system_prompt"] = request.system_prompt

            if request.user_prompt is not None:
                update_fields.append("user_prompt = :user_prompt")
                params["user_prompt"] = request.user_prompt

            if request.enabled is not None:
                update_fields.append("enabled = :enabled")
                params["enabled"] = request.enabled

            if update_fields:
                # Always update the timestamp and increment version when making changes
                update_fields.append("updated_at = :updated_at")
                update_fields.append("version = version + 1")
                params["updated_at"] = datetime.now(timezone.utc)

                db.execute(text(f"""
                    UPDATE pipeline_flavors
                    SET {', '.join(update_fields)}
                    WHERE id = :id
                """), params)

                db.commit()

            return self.get_flavor_by_id(flavor_id)
    
    def delete_flavor(self, flavor_id: str) -> bool:
        """Delete a pipeline flavor"""
        with get_pipeline_session() as db:
            # Check if it's the Default flavor
            existing = db.execute(text("""
                SELECT title FROM pipeline_flavors WHERE id = :id
            """), {"id": flavor_id}).fetchone()

            if not existing:
                raise FlavorNotFoundError(f"Flavor with ID '{flavor_id}' not found")

            if existing[0] == "Default":
                raise FlavorValidationError("Cannot delete the Default flavor")

            result = db.execute(text("""
                DELETE FROM pipeline_flavors WHERE id = :id
            """), {"id": flavor_id})

            db.commit()
            return result.rowcount > 0

    def get_flavor_by_id(self, flavor_id: str) -> PipelineFlavor:
        """Get a flavor by ID"""
        # Handle default flavor special case
        if DefaultFlavorProvider.is_default_flavor(flavor_id):
            # Need to determine which pipeline - this is a limitation of the default approach
            # For now, we'll raise an error and require more specific lookup
            raise FlavorNotFoundError("Default flavor ID requires pipeline specification. Use get_default_flavor() instead.")

        with get_pipeline_session() as db:
            row = db.execute(text("""
                SELECT * FROM pipeline_flavors WHERE id = :id
            """), {"id": flavor_id}).fetchone()

            if not row:
                raise FlavorNotFoundError(f"Flavor with ID '{flavor_id}' not found")

            return self._row_to_flavor(row)

    def get_flavor_by_title(self, pipeline: PipelineType, title: str) -> PipelineFlavor:
        """Get a flavor by pipeline and title"""
        # Handle default flavor special case
        if title.lower() == "default":
            return DefaultFlavorProvider.get_default_flavor(pipeline)

        with get_pipeline_session() as db:
            row = db.execute(text("""
                SELECT * FROM pipeline_flavors
                WHERE pipeline = :pipeline AND title = :title
            """), {
                "pipeline": pipeline.value,
                "title": title
            }).fetchone()

            if not row:
                raise FlavorNotFoundError(
                    f"Flavor with title '{title}' not found for pipeline '{pipeline.value}'"
                )

            return self._row_to_flavor(row)

    def list_flavors(self, pipeline: Optional[PipelineType] = None) -> List[PipelineFlavor]:
        """List all flavors, optionally filtered by pipeline"""
        flavors = []

        # Always include default flavors
        if pipeline:
            # Add default flavor for this pipeline
            default_flavor = DefaultFlavorProvider.get_default_flavor(pipeline)
            flavors.append(default_flavor)

            # Add user-created flavors for this pipeline
            user_flavors = self._get_user_flavors(pipeline)
            flavors.extend(user_flavors)
        else:
            # Add all default flavors
            for pipeline_type in PipelineType:
                default_flavor = DefaultFlavorProvider.get_default_flavor(pipeline_type)
                flavors.append(default_flavor)

            # Add all user-created flavors
            all_user_flavors = self._get_all_user_flavors()
            flavors.extend(all_user_flavors)

        return flavors

    def get_enabled_flavors(self, pipeline: PipelineType) -> List[PipelineFlavor]:
        """Get all enabled flavors for a pipeline"""
        flavors = []

        # Always include default flavor (always enabled)
        default_flavor = DefaultFlavorProvider.get_default_flavor(pipeline)
        flavors.append(default_flavor)

        # Add enabled user-created flavors
        user_flavors = self._get_user_flavors(pipeline, enabled_only=True)
        flavors.extend(user_flavors)

        return flavors

    def get_default_flavor(self, pipeline: PipelineType) -> PipelineFlavor:
        """Get the default flavor for a pipeline"""
        return DefaultFlavorProvider.get_default_flavor(pipeline)
    
    def _row_to_flavor(self, row) -> PipelineFlavor:
        """Convert database row to PipelineFlavor model"""
        return PipelineFlavor(
            id=row[0],                                          # id
            pipeline=PipelineType(row[1]),                      # pipeline
            title=row[2],                                       # title
            llm_provider=row[3],                                # llm_provider
            llm_model=row[4],                                   # llm_model
            llm_config=LLMConfig.model_validate_json(row[5]),   # llm_config
            system_prompt=row[6],                               # system_prompt
            user_prompt=row[7],                                 # user_prompt
            version=row[8],                                     # version
            enabled=bool(row[9]),                               # enabled
            created_at=row[10],                                 # created_at
            updated_at=row[11]                                  # updated_at
        )
    
    def _get_user_flavors(self, pipeline: PipelineType, enabled_only: bool = False) -> List[PipelineFlavor]:
        """Get user-created flavors for a specific pipeline"""
        with get_pipeline_session() as db:
            if enabled_only:
                rows = db.execute(text("""
                    SELECT * FROM pipeline_flavors
                    WHERE pipeline = :pipeline AND enabled = TRUE
                    ORDER BY title
                """), {"pipeline": pipeline.value}).fetchall()
            else:
                rows = db.execute(text("""
                    SELECT * FROM pipeline_flavors
                    WHERE pipeline = :pipeline
                    ORDER BY title
                """), {"pipeline": pipeline.value}).fetchall()

            return [self._row_to_flavor(row) for row in rows]

    def _get_all_user_flavors(self) -> List[PipelineFlavor]:
        """Get all user-created flavors across all pipelines"""
        with get_pipeline_session() as db:
            rows = db.execute(text("""
                SELECT * FROM pipeline_flavors
                ORDER BY pipeline, title
            """)).fetchall()

            return [self._row_to_flavor(row) for row in rows]
