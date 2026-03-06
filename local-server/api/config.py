# mypy: ignore-errors
"""
Configuration Management API

Provides REST endpoints for reading and updating configuration settings
using dot notation for nested values.
"""

from typing import Any, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import get_config_manager, notify_global_configuration_reload
from reference_api.service import ReferenceService
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/config", tags=["configuration"])


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration values"""

    path: str = Field(..., description="Configuration path in dot notation")
    value: Any = Field(..., description="New configuration value")


class ConfigResponse(BaseModel):
    """Response model for configuration operations"""

    success: bool
    data: Any = None
    errors: List[str] = []


def create_error_response(status_code: int, message: str) -> JSONResponse:
    """Create a consistent error response in ConfigResponse format"""
    return JSONResponse(
        status_code=status_code,
        content=ConfigResponse(success=False, errors=[message]).model_dump(),
    )


@router.get("/", response_model=ConfigResponse)
async def get_full_configuration():
    """Get complete configuration"""
    try:
        config_manager = get_config_manager()
        return ConfigResponse(success=True, data=config_manager.settings.model_dump())  # noqa: E501
    except Exception as e:
        logger.error(f"Error getting full configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate", response_model=ConfigResponse)
async def validate_configuration():
    """Validate current configuration"""
    try:
        config_manager = get_config_manager()
        errors = config_manager.validate()

        return ConfigResponse(
            success=len(errors) == 0,
            data={
                "errors": errors,
                "valid": len(errors) == 0,
                "error_count": len(errors),
            },
        )
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/", response_model=ConfigResponse)
async def get_configuration_schema():
    """Get configuration schema with field descriptions"""
    try:
        from config import Settings

        schema = Settings.model_json_schema()

        return ConfigResponse(success=True, data=schema)
    except Exception as e:
        logger.error(f"Error getting configuration schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Reference Sources Configuration Endpoints


@router.get("/reference-sources/status", response_model=ConfigResponse)
async def get_reference_sources_status():
    """Get status of all reference sources"""
    try:
        config_manager = get_config_manager()
        reference_service = ReferenceService(config_manager)
        status = await reference_service.get_source_status()

        # Add proxy server status
        proxy_running = await check_proxy_running()
        status["proxy_server"] = {
            "enabled": config_manager.settings.proxy_server.enabled,
            "host": config_manager.settings.proxy_server.host,
            "port": config_manager.settings.proxy_server.port,
            "running": proxy_running,
        }

        return ConfigResponse(success=True, data=status)
    except Exception as e:
        logger.error(f"Error getting reference sources status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reference-sources", response_model=ConfigResponse)
async def get_reference_sources_config():
    """Get reference sources configuration"""
    try:
        config_manager = get_config_manager()
        return ConfigResponse(
            success=True, data=config_manager.settings.reference_sources.model_dump()  # noqa: E501
        )
    except Exception as e:
        logger.error(f"Error getting reference sources config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reference-sources/{source_name}", response_model=ConfigResponse)
async def get_reference_source_config(source_name: str):
    """Get configuration for a specific reference source"""
    try:
        config_manager = get_config_manager()

        # Validate source name and get configuration
        valid_sources = [
            "conceptnet",
            "dbpedia_lookup",
            "dbpedia_sparql",
            "dbpedia_spotlight",
            "wikidata",
            "duckduckgo",
            "schema_org",
        ]
        if source_name not in valid_sources:
            raise HTTPException(
                status_code=404, detail=f"Unknown reference source: {source_name}"  # noqa: E501
            )

        source_config = getattr(config_manager.settings.reference_sources, source_name)  # noqa: E501
        return ConfigResponse(success=True, data=source_config.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reference source config for {source_name}: {e}")  # noqa: E501
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/reference-sources/{source_name}", response_model=ConfigResponse)  # noqa: E501
async def update_reference_source_config(
    source_name: str, request: ConfigUpdateRequest
):
    """Update configuration for a specific reference source"""
    try:
        config_manager = get_config_manager()

        # Validate source name
        valid_sources = [
            "conceptnet",
            "dbpedia_lookup",
            "dbpedia_sparql",
            "dbpedia_spotlight",
            "wikidata",
            "duckduckgo",
            "schema_org",
        ]
        if source_name not in valid_sources:
            raise HTTPException(
                status_code=404, detail=f"Unknown reference source: {source_name}"  # noqa: E501
            )

        # Update the configuration
        path = f"reference_sources.{source_name}.{request.path}"
        success = config_manager.set(path, request.value)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save configuration")  # noqa: E501

        # Notify relevant services of the change
        await notify_reference_source_change(source_name, request.path, request.value)  # noqa: E501

        return ConfigResponse(success=True, data=request.value)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating reference source config for {source_name}: {e}")  # noqa: E501
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{path:path}", response_model=ConfigResponse)
async def get_configuration_value(path: str):
    """Get specific configuration value by path"""
    try:
        config_manager = get_config_manager()
        value = config_manager.get(path)

        # Convert pydantic models to dict for JSON serialization
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        elif hasattr(value, "dict"):  # Fallback for older Pydantic models
            value = value.dict()

        return ConfigResponse(success=True, data=value)
    except KeyError:
        raise HTTPException(status_code=404, detail="Configuration path not found")  # noqa: E501
    except Exception as e:
        logger.error(f"Error getting configuration value for {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/", response_model=ConfigResponse)
async def update_configuration(request: ConfigUpdateRequest):
    """Update specific configuration value"""
    try:
        # Validate request
        if not request.path or request.path.strip() == "":
            return create_error_response(400, "Configuration path cannot be empty")  # noqa: E501

        config_manager = get_config_manager()

        # Validate the path exists and get current value for type checking
        try:
            current_value = config_manager.get(request.path)
        except KeyError:
            return create_error_response(
                400, f"Configuration path not found: {request.path}"
            )

        # Type validation - ensure new value is compatible with existing type
        if current_value is not None:
            current_type = type(current_value)
            # Skip validation for Pydantic models and complex types
            if current_type in (int, float, str, bool, list, dict):
                if not isinstance(request.value, current_type):
                    # Special case: allow int for float fields
                    if current_type is float and isinstance(request.value, int):  # noqa: E501
                        pass  # Allow int -> float conversion
                    else:
                        expected_type = current_type.__name__
                        actual_type = type(request.value).__name__
                        return create_error_response(
                            400,
                            f"Invalid value type for {request.path}. Expected {expected_type}, got {actual_type}",  # noqa: E501
                        )

        # Try to update the value
        try:
            success = config_manager.set(request.path, request.value)
        except (ValueError, TypeError) as e:
            return create_error_response(
                400, f"Invalid value for {request.path}: {str(e)}"
            )

        if success:
            return ConfigResponse(
                success=True, data={"path": request.path, "value": request.value}  # noqa: E501
            )
        else:
            return create_error_response(500, "Failed to save configuration")

    except Exception as e:
        logger.error(f"Error updating config {request.path}: {e}")
        return create_error_response(500, str(e))


@router.post("/reload")
async def reload_configuration():
    """Reload configuration from file"""
    try:
        config_manager = get_config_manager()
        config_manager.load()

        # Notify all services of the configuration reload
        await notify_global_configuration_reload()

        return ConfigResponse(
            success=True, data={"message": "Configuration reloaded successfully"}  # noqa: E501
        )
    except Exception as e:
        logger.error(f"Error reloading configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_configuration():
    """Reset configuration to defaults"""
    try:
        config_manager = get_config_manager()

        # Create new default settings
        from config import Settings

        config_manager.settings = Settings()

        # Save the defaults
        success = config_manager.save()

        if success:
            # Notify all services of the configuration reset
            await notify_global_configuration_reload()

            return ConfigResponse(
                success=True, data={"message": "Configuration reset to defaults"}  # noqa: E501
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to save default configuration"
            )

    except Exception as e:
        logger.error(f"Error resetting configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Service-specific notification handlers for reference sources
async def handle_reference_source_config_change(source_name: str, field: str, value):  # noqa: E501
    """Handle reference source configuration changes"""
    logger.info(
        f"Reference source configuration changed: {source_name}.{field} = {value}"  # noqa: E501
    )

    # Invalidate NLP pipeline if NLP-related sources change
    if source_name in ["conceptnet", "dbpedia_spotlight"] and field in [
        "enabled",
        "use_proxy",
        "upstream_url",
    ]:
        try:
            from nlp.pipeline import invalidate_pipeline

            invalidate_pipeline()
        except ImportError:
            logger.warning("NLP pipeline invalidation not available")

    # Restart proxy if proxy-related settings change
    if field in ["use_proxy", "upstream_url"] and value:
        try:
            from nlp.proxy_manager import get_proxy_manager

            proxy_manager = get_proxy_manager()
            if hasattr(proxy_manager, "is_running") and proxy_manager.is_running:  # noqa: E501
                await proxy_manager.restart()
        except ImportError:
            logger.warning("Proxy manager not available")


async def notify_reference_source_change(source_name: str, field: str, value):
    """Notify services of reference source configuration changes"""
    await handle_reference_source_config_change(source_name, field, value)


async def check_proxy_running() -> bool:
    """Check if proxy server is running (implementation dependent)"""
    try:
        from nlp.proxy_manager import get_proxy_manager

        proxy_manager = get_proxy_manager()
        return hasattr(proxy_manager, "is_running") and proxy_manager.is_running  # noqa: E501
    except ImportError:
        return False
