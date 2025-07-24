import threading
import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from database import models
from database.utils import get_db
from embeddings.generate_embeddings import generate_embedding
from utils.vector import cosine_similarity, decode_emb
from utils.logger import get_logger
from utils.watchdog import start_watchdog
from api.api_errors import validation_error_response, conflict_error_response, bad_request_error_response

logger = get_logger("layers_api")
router = APIRouter()


# Pydantic models for Layer
class LayerBase(BaseModel):
    title: str = Field(..., min_length=2)
    definition: Optional[str] = Field(None, min_length=1)
    primary_predicate: Optional[str] = None


class LayerCreate(LayerBase):
    pass


class LayerUpdate(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    primary_predicate: Optional[str] = None


class LayerOut(LayerBase):
    id: UUID
    title_embedding: Optional[List[float]] = None
    definition_embedding: Optional[List[float]] = None
    created_at: str
    version: Optional[int] = None
    last_modified: Optional[str] = None  # ISO8601 string


# --- Find Layer Endpoint Models ---
class FindLayerRequest(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    created_at: Optional[str] = None  # ISO8601 string
    minimum_score: Optional[float] = 0.1
    limit: Optional[int] = 1


class FindLayerResult(LayerOut):
    score: float
    distance: float


class PaginatedLayersResponse(BaseModel):
    data: List[LayerOut]
    total: int
    skip: int
    limit: int


def to_layer_out(layer):
    return LayerOut(
        id=layer.id,
        title=layer.title,
        definition=layer.definition,
        primary_predicate=layer.primary_predicate,
        title_embedding=decode_emb(layer.title_embedding) if layer.title_embedding else None,
        definition_embedding=decode_emb(layer.definition_embedding) if layer.definition_embedding else None,
        created_at=layer.created_at.isoformat(),
        version=layer.version,
        last_modified=layer.last_modified.isoformat() if layer.last_modified else None,
    )


@router.post(
    "/find",
    response_model=List[FindLayerResult],
    responses={
        405: {"description": "Method Not Allowed"},
        400: {"description": "Bad Request"},
        409: {"description": "Conflict"},
        500: {"description": "Internal Server Error"},
    },
)
def find_layer(req: FindLayerRequest, db: Session = Depends(get_db)):
    # Validate created_at if provided
    if req.created_at is not None:
        try:
            datetime.datetime.fromisoformat(req.created_at)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid created_at format. Must be ISO8601 string.",
            )

    # Watchdog setup
    stop_event = threading.Event()
    search_details = {
        "title": req.title,
        "definition": req.definition,
        "created_at": req.created_at,
        "minimum_score": req.minimum_score,
        "limit": req.limit,
    }
    start_watchdog(stop_event, search_details, route="/api/layers/find")

    title_emb = generate_embedding(req.title) if req.title else None
    title_emb = decode_emb(title_emb)
    title_emb_str = "[" + ", ".join(f"{x:.6f}" for x in title_emb) + "]" if title_emb else None
    def_emb = generate_embedding(req.definition) if req.definition else None
    def_emb = decode_emb(def_emb)
    def_emb_str = "[" + ", ".join(f"{x:.6f}" for x in def_emb) + "]" if def_emb else None

    results = []
    sql = None
    limit = req.limit if req.limit is not None else 1
    emb_type = None
    emb_param = None

    if title_emb is not None:
        emb_type = "title_embedding"
        emb_param = title_emb_str
    elif def_emb is not None:
        emb_type = "definition_embedding"
        emb_param = def_emb_str

    if emb_type:
        sql = text(
            f"""
            SELECT l.id, l.title, l.definition, l.primary_predicate, l.title_embedding, l.definition_embedding, l.created_at, l.version, l.last_modified, v.distance
            FROM (
                SELECT id, distance
                FROM layers_vec
                WHERE {emb_type} match :emb_param
                ORDER BY distance
                LIMIT :limit
            ) v
            JOIN layers l ON l.id = v.id
            """
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="At least one of title or definition must be provided for search.",
        )

    try:
        rows = db.execute(sql, {"emb_param": emb_param, "limit": limit}).fetchall()
        for row in rows:
            out = FindLayerResult(
                id=row[0],
                title=row[1],
                definition=row[2],
                primary_predicate=row[3],
                title_embedding=decode_emb(row[4]),
                definition_embedding=decode_emb(row[5]),
                created_at=(row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6])),
                version=row[7],
                last_modified=(row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8])),
                score=cosine_similarity(title_emb or def_emb, decode_emb(row[4] if title_emb else row[5]) or []),
                distance=row[9],
            )

            if out.score >= req.minimum_score:
                results.append(out)
        stop_event.set()
        return results
    except Exception as e:
        logger.warning(f"sqlite-vec KNN search failed: {e}")
    stop_event.set()
    return []


@router.post(
    "/",
    response_model=LayerOut,
    status_code=201,
    responses={
        201: {"description": "Layer created."},
        400: {"description": "Bad Request"},
        409: {"description": "Conflict"},
        422: {"description": "Validation Error"},
    },
)
def create_layer(layer: LayerCreate, db: Session = Depends(get_db)):
    logger.info(f"Creating layer with payload: {layer}")
    if not layer.title or not layer.title.strip():
        return validation_error_response("Layer title must not be empty.", loc=["body", "title"])
    if db.query(models.Layer).filter_by(title=layer.title).first():
        return conflict_error_response("Layer title must be unique.")
    title_emb = generate_embedding(layer.title)
    def_emb = generate_embedding(layer.definition if layer.definition is not None else "")
    db_layer = models.Layer(
        id=str(uuid4()),
        title=layer.title,
        definition=layer.definition,
        primary_predicate=layer.primary_predicate,
        title_embedding=title_emb,
        definition_embedding=def_emb,
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(db_layer)
    db.commit()
    db.refresh(db_layer)
    sql = text(
        """
        INSERT INTO layers_vec (id, title_embedding, definition_embedding)
        VALUES (:id, :title_embedding, :definition_embedding)
        """
    )
    db.execute(
        sql,
        {
            "id": str(db_layer.id),
            "title_embedding": db_layer.title_embedding,
            "definition_embedding": db_layer.definition_embedding,
        },
    )
    db.commit()
    db.close()
    return to_layer_out(db_layer)


@router.get("/{id}", response_model=LayerOut, responses={404: {"description": "Layer not found"}})
def get_layer(id: str, db: Session = Depends(get_db)):
    layer = db.query(models.Layer).filter_by(id=id).first()
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found.")
    return to_layer_out(layer)


@router.get("/", response_model=PaginatedLayersResponse)
def list_layers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort: Optional[str] = Query(None, pattern="^(title|created_at)$"),
    db: Session = Depends(get_db),
):
    # Validation now handled by Query pattern
    if sort == "":
        return validation_error_response("Sort parameter cannot be empty.", loc=["query", "sort"])
    
    # Build base query for both count and data
    q = db.query(models.Layer)
    
    # Get total count
    total = q.count()
    
    # Apply sorting and pagination to get data
    if sort == "title":
        q = q.order_by(models.Layer.title)
    elif sort == "created_at":
        q = q.order_by(models.Layer.created_at.desc())
    layers = q.offset(skip).limit(limit).all()
    
    result = []
    for l in layers:
        # Defensive: skip layers with invalid title
        if not l.title or len(l.title) < 2:
            logger.warning(f"Skipping layer with invalid title (id={l.id}): '{l.title}'")
            continue
        result.append(to_layer_out(l))
    
    return PaginatedLayersResponse(
        data=result,
        total=total,
        skip=skip,
        limit=limit
    )


@router.put("/{id}", response_model=LayerOut, responses={404: {"description": "Layer not found"}})
def update_layer(id: str, layer: LayerUpdate, db: Session = Depends(get_db)):
    db_layer = db.query(models.Layer).filter_by(id=id).first()
    if not db_layer:
        raise HTTPException(status_code=404, detail="Layer not found.")
    if layer.title is not None:
        if not layer.title.strip():
            return validation_error_response("Layer title must not be empty.", loc=["body", "title"])
        if layer.title != db_layer.title:
            if db.query(models.Layer).filter(models.Layer.title == layer.title, models.Layer.id != str(id)).first():
                return conflict_error_response("Layer title must be unique.")
            db_layer.title = layer.title
            db_layer.title_embedding = generate_embedding(layer.title)
    if layer.definition is not None:
        db_layer.definition = layer.definition
        db_layer.definition_embedding = generate_embedding(layer.definition if layer.definition is not None else "")
    if layer.primary_predicate is not None:
        db_layer.primary_predicate = layer.primary_predicate
    db.commit()
    db.refresh(db_layer)
    sql = text(
        """
        UPDATE layers_vec
        SET title_embedding = :title_embedding,
            definition_embedding = :definition_embedding
        WHERE id = :id
        """
    )
    db.execute(
        sql,
        {
            "id": str(db_layer.id),
            "title_embedding": db_layer.title_embedding,
            "definition_embedding": db_layer.definition_embedding,
        },
    )
    db.commit()
    db.close()
    return to_layer_out(db_layer)


@router.delete("/{id}", status_code=200, responses={404: {"description": "Layer not found"}})
def delete_layer(id: str, db: Session = Depends(get_db)):
    db_layer = db.query(models.Layer).filter_by(id=id).first()
    if not db_layer:
        raise HTTPException(status_code=404, detail="Layer not found.")
    db.delete(db_layer)
    db.commit()

    # Remove from sqlite vector index
    try:
        sql = text("DELETE FROM layers_vec WHERE id = :id")
        db.execute(sql, {"id": str(db_layer.id)})
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to remove layer from vector index: {e}")

    return {"success": True}
