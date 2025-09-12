"""
FastAPI router for schema.org endpoints (scaffold).

Defines minimal endpoints for status and refresh to match the design.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional, Union
from pydantic import BaseModel
from .manager import SchemaOrgManager
from config import get_settings
from .service import SchemaOrgService
from utils.logger import get_logger
from .errors import (
    DownloadError,
    BackupError,
    RestoreError,
    DatabaseError,
    ValidationError,
    SearchError,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/schema-org", tags=["schema-org"])

# Instantiate manager and service for simplicity; app.py can replace or reuse these
manager = SchemaOrgManager()
service = SchemaOrgService(manager=manager)


class SchemaOrgEntityOut(BaseModel):
    id: str
    identifier: str
    title: str
    definition: Optional[str]
    parent_identifier: Optional[str]
    parent_id: Optional[str]
    created_at: Optional[str]
    children_count: Optional[int] = None
    raw: Optional[dict]


class SchemaOrgPropertyOut(BaseModel):
    id: str
    identifier: str
    title: str
    definition: Optional[str]
    contributors: Optional[List[str]]
    domain_includes: Optional[List[str]]
    range_includes: Optional[List[str]]
    inverse_of: Optional[List[str]]
    created_at: Optional[str]
    raw: Optional[dict]


class SchemaOrgStatus(BaseModel):
    is_populated: bool
    entity_count: int
    property_count: int
    last_updated: Optional[float]
    database_size: Optional[int]


class SearchResult(BaseModel):
    items: List[Union[SchemaOrgEntityOut, SchemaOrgPropertyOut]]
    total_count: int
    limit: int
    offset: int
    query: Optional[str]


@router.get("/status", response_model=SchemaOrgStatus)
def get_status() -> Dict:
    """Return schema.org database status."""
    try:
        settings = get_settings()
        # Auto-initialize on-demand if enabled and not already populated
        try:
            if settings.SCHEMA_ORG_AUTO_INITIALIZE and not manager.is_populated():
                logger.info("Auto-initializing schema.org DB from status endpoint")
                # initialize runs background population if needed
                manager.initialize()
        except Exception:
            logger.exception("Auto-initialize check failed")

        status = manager.get_status()
        return status
    except Exception as e:
        logger.exception("Failed to get schema.org status: %s", e)
        raise HTTPException(status_code=500, detail="internal_error")


@router.post("/refresh")
def refresh_schema_org(force: bool = False) -> Dict:
    """Trigger a refresh of the schema.org database."""
    try:
        result = manager.refresh_data(force=force)
        # If refresh succeeded, invalidate service caches
        if result.get("success"):
            try:
                service.invalidate_cache()
            except Exception:
                logger.exception("Failed to invalidate schema_org service cache after refresh")
        return result
    except Exception as e:
        logger.exception("Failed to refresh schema.org data: %s", e)
        # Map known errors to 502/503
        if isinstance(e, (DownloadError, BackupError, RestoreError)):
            raise HTTPException(status_code=502, detail=str(e))
        if isinstance(e, DatabaseError):
            raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail="internal_error")


@router.get("/entities", response_model=SearchResult)
def list_entities(query: Optional[str] = Query(None), parent_id: Optional[str] = Query(None), limit: int = 50, offset: int = 0):
    try:
        res = service.search_entities(query=query, parent_id=parent_id, limit=limit, offset=offset)
        return {"items": res["items"], "total_count": res["total_count"], "limit": res["limit"], "offset": res["offset"], "query": query}
    except ValidationError as e:
        logger.debug("Validation error listing entities: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to list entities: %s", e)
        raise HTTPException(status_code=500, detail="internal_error")


@router.get("/entities/{identifier}", response_model=SchemaOrgEntityOut)
def get_entity(identifier: str):
    try:
        ent = service.get_entity(identifier)
        if not ent:
            raise HTTPException(status_code=404, detail="Entity not found")
        return ent
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get entity: %s", e)
        raise HTTPException(status_code=500, detail="internal_error")


@router.get("/properties", response_model=SearchResult)
def list_properties(query: Optional[str] = Query(None), domain_includes: Optional[str] = Query(None), range_includes: Optional[str] = Query(None), limit: int = 50, offset: int = 0):
    try:
        res = service.search_properties(query=query, domain_includes=domain_includes, range_includes=range_includes, limit=limit, offset=offset)
        return {"items": res["items"], "total_count": res["total_count"], "limit": res["limit"], "offset": res["offset"], "query": query}
    except ValidationError as e:
        logger.debug("Validation error listing properties: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to list properties: %s", e)
        raise HTTPException(status_code=500, detail="internal_error")


@router.get("/properties/{identifier}", response_model=SchemaOrgPropertyOut)
def get_property(identifier: str):
    try:
        prop = service.get_property(identifier)
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        return prop
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get property: %s", e)
        raise HTTPException(status_code=500, detail="internal_error")


@router.get("/search", response_model=SearchResult)
def semantic_search(query: str = Query(...), search_type: str = Query("both"), limit: int = 20, similarity_threshold: float = 0.7):
    try:
        res = service.semantic_search(query=query, search_type=search_type, limit=limit, similarity_threshold=similarity_threshold)
        return {"items": res["items"], "total_count": res["total_count"], "limit": res["limit"], "offset": res.get("offset", 0), "query": query}
    except Exception as e:
        logger.exception("Failed semantic search: %s", e)
        if isinstance(e, ValidationError):
            raise HTTPException(status_code=400, detail=str(e))
        if isinstance(e, SearchError):
            raise HTTPException(status_code=502, detail=str(e))
        raise HTTPException(status_code=500, detail="internal_error")
