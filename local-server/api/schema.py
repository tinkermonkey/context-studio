"""API endpoints for schema management."""

from typing import cast
from fastapi import APIRouter, HTTPException, Depends

from database.migrations.migration_manager import MigrationManager
from dataset.manager import DatasetManager
from dataset.models import MigrationStatus
from database.utils import get_dataset_manager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_dataset_manager_dependency() -> DatasetManager:
    """Dependency to get dataset manager."""
    return cast(DatasetManager, get_dataset_manager())


def get_migration_manager(
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
) -> MigrationManager:
    """Get migration manager for current active dataset."""
    active_dataset = dataset_manager.get_active_dataset()
    if not active_dataset:
        raise HTTPException(status_code=400, detail="No active dataset")

    dataset_path = dataset_manager.get_dataset_file_path(active_dataset.filename)  # noqa: E501
    return MigrationManager(dataset_path)


@router.get("/schema/status", response_model=MigrationStatus)
async def get_schema_status(
    migration_manager: MigrationManager = Depends(get_migration_manager)
):
    """Get current schema version and migration status."""
    try:
        return migration_manager.get_migration_status()
    except Exception as e:
        logger.error(f"Failed to get schema status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schema/migrate")
async def migrate_schema(
    skip_on_error: bool = False,
    migration_manager: MigrationManager = Depends(get_migration_manager)
):
    """Apply pending migrations to current dataset."""
    try:
        success = migration_manager.migrate_to_latest(skip_on_error=skip_on_error)  # noqa: E501
        if not success:
            raise HTTPException(status_code=500, detail="Migration failed")

        status = migration_manager.get_migration_status()
        return {
            "message": "Migrations applied successfully",
            "current_version": status.current_version,
            "applied_migrations": len(status.pending_migrations) if status.needs_migration else 0  # noqa: E501
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply migrations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/history")
async def get_migration_history(
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Get migration history for current dataset."""
    try:
        active_dataset = dataset_manager.get_active_dataset()
        if not active_dataset:
            raise HTTPException(status_code=400, detail="No active dataset")

        dataset_path = dataset_manager.get_dataset_file_path(active_dataset.filename)  # noqa: E501

        # Get migration history from database
        from sqlalchemy import create_engine, text
        database_url = f"sqlite:///{dataset_path}"
        engine = create_engine(database_url, connect_args={"check_same_thread": False})  # noqa: E501

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT version, description, migration_file, applied_at, execution_time_ms  # noqa: E501
                FROM schema_history
                ORDER BY version DESC
            """)).fetchall()

            return {
                "migrations": [
                    {
                        "version": row[0],
                        "description": row[1],
                        "migration_file": row[2],
                        "applied_at": row[3],
                        "execution_time_ms": row[4]
                    }
                    for row in result
                ]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get migration history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schema/rollback/{target_version}")
async def rollback_schema(
    target_version: int,
    migration_manager: MigrationManager = Depends(get_migration_manager)
):
    """Rollback schema to a specific version."""
    try:
        success = migration_manager.rollback_to_version(target_version)
        if not success:
            raise HTTPException(status_code=500, detail="Rollback failed")

        status = migration_manager.get_migration_status()
        return {
            "message": f"Schema rolled back to version {target_version}",
            "current_version": status.current_version
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rollback schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schema/generate-migration")
async def generate_migration(
    description: str,
    migration_manager: MigrationManager = Depends(get_migration_manager)
):
    """Generate a new migration file template."""
    try:
        filepath = migration_manager.generate_migration(description)
        return {
            "message": "Migration file generated successfully",
            "filepath": filepath,
            "description": description
        }
    except Exception as e:
        logger.error(f"Failed to generate migration: {e}")
        raise HTTPException(status_code=500, detail=str(e))
