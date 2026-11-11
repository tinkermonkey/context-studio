"""
FastAPI routes for sources: the files, web pages and text extraction reads (#1551).

- POST   /api/sources                  Add one: a multipart file, or JSON {url} or {title, text}
- GET    /api/sources                  A taxonomy's sources (one dataset's when named)
- GET    /api/sources/{source_id}      One source, without its text
- GET    /api/sources/{source_id}/text One page's text, or all of it
- DELETE /api/sources/{source_id}      Remove one; provenance that names it stays

A web page is fetched after the response: the source comes back `fetching`
and turns `ready` or `failed`.
"""

from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from adapters.web.dependencies import get_source_service
from adapters.web.schemas.ontology import ListResponse
from adapters.web.schemas.sources import (
    SourceCreateRequest,
    SourceResponse,
    SourceTextResponse,
    SourceUploadForm,
)
from domain.extraction.exceptions import SourceNotReadyError
from domain.extraction.sources import Source, SourceService
from domain.ontology.exceptions import (
    DatasetMismatchError,
    DatasetRequiredError,
    EntityNotFoundError,
)
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["sources"])

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"description": "Taxonomy, dataset or source not found"}
}

_ADD_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {"schema": SourceUploadForm.model_json_schema()},
            "application/json": {"schema": SourceCreateRequest.model_json_schema()},
        },
    }
}


def _http_error(exc: Exception) -> HTTPException:
    """404 for something missing, 409 for text not ready, 422 for bad input, else 500."""
    if isinstance(exc, EntityNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, SourceNotReadyError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (DatasetRequiredError, DatasetMismatchError, ValueError)):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    logger.exception("Sources request failed")
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


def _form_text(value: object) -> Optional[str]:
    return value.strip() or None if isinstance(value, str) else None


async def _add_file(request: Request, service: SourceService) -> Source:
    """A multipart upload: read at most one byte past the limit, so too large is known."""
    async with request.form() as form:
        upload = form.get("file")
        taxonomy_id = _form_text(form.get("taxonomy_id"))
        if not isinstance(upload, UploadFile) or taxonomy_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A file upload needs `file` and `taxonomy_id` form fields",
            )
        data = await upload.read(service.max_bytes + 1)
        return await run_sync_in_executor(
            service.add_file,
            taxonomy_id,
            upload.filename or "upload",
            data,
            upload.content_type,
            _form_text(form.get("dataset")),
            _form_text(form.get("title")),
        )


@router.post(
    "/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_NOT_FOUND,
        422: {"description": "Neither a file, a URL nor text; or the dataset must be named"},
    },
    openapi_extra=_ADD_BODY,
)
async def add_source(
    request: Request,
    background: BackgroundTasks,
    service: SourceService = Depends(get_source_service),
) -> SourceResponse:
    """
    Add a source: a multipart file (PDF, Markdown, HTML or plain text), or JSON
    with a `url` to fetch or a `title` and pasted `text`. A file or text is read
    at once: `ready`, or `failed` saying why (too_large, unsupported_type,
    no_text). A URL comes back `fetching` and is fetched in the background.
    """
    try:
        if request.headers.get("content-type", "").startswith("multipart/form-data"):
            return SourceResponse.from_domain(await _add_file(request, service))
        try:
            body = SourceCreateRequest.model_validate_json(await request.body())
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        if body.url is not None:
            source = await run_sync_in_executor(
                service.add_url, body.taxonomy_id, body.url, body.dataset, body.title
            )
            background.add_task(service.fetch, source.id)
        else:
            source = await run_sync_in_executor(
                service.add_text, body.taxonomy_id, body.title or "", body.text or "", body.dataset
            )
        return SourceResponse.from_domain(source)
    except (HTTPException, RequestValidationError):
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/sources", response_model=ListResponse[SourceResponse], responses=_NOT_FOUND)
async def list_sources(
    taxonomy_id: str = Query(..., description="The taxonomy"),
    dataset: Optional[str] = Query(
        None, description="Only this dataset's sources (identifier or id)"
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: SourceService = Depends(get_source_service),
) -> ListResponse[SourceResponse]:
    """A taxonomy's sources, newest first, without removed ones."""
    try:
        sources = await run_sync_in_executor(service.list_sources, taxonomy_id, dataset)
    except Exception as exc:
        raise _http_error(exc) from exc
    return ListResponse(
        items=[SourceResponse.from_domain(s) for s in sources[offset : offset + limit]],
        total=len(sources),
        limit=limit,
        offset=offset,
    )


@router.get("/sources/{source_id}", response_model=SourceResponse, responses=_NOT_FOUND)
async def get_source(
    source_id: str, service: SourceService = Depends(get_source_service)
) -> SourceResponse:
    """One source, removed or not, without its text."""
    try:
        return SourceResponse.from_domain(await run_sync_in_executor(service.get, source_id))
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/sources/{source_id}/text",
    response_model=SourceTextResponse,
    responses={
        **_NOT_FOUND,
        409: {"description": "The source is fetching or failed, so it has no text"},
        422: {"description": "The source has no such page"},
    },
)
async def get_source_text(
    source_id: str,
    page: Optional[int] = Query(None, ge=1, description="A page (from 1); all the text without"),
    service: SourceService = Depends(get_source_service),
) -> SourceTextResponse:
    """A source's text, one page or all of it, with its offsets in the whole text."""
    try:
        source, start, end = await run_sync_in_executor(service.text, source_id, page)
    except Exception as exc:
        raise _http_error(exc) from exc
    return SourceTextResponse(
        source_id=source.id,
        page=page,
        pages=source.pages,
        start=start,
        end=end,
        text=source.text[start:end],
    )


@router.delete("/sources/{source_id}", response_model=SourceResponse, responses=_NOT_FOUND)
async def remove_source(
    source_id: str, service: SourceService = Depends(get_source_service)
) -> SourceResponse:
    """
    Remove a source: it leaves the list and its original file is deleted. Its
    record stays, so entities applied from it keep their provenance.
    """
    try:
        return SourceResponse.from_domain(await run_sync_in_executor(service.remove, source_id))
    except Exception as exc:
        raise _http_error(exc) from exc
