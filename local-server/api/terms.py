import threading
import datetime
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from database import models
from database.utils import get_db
from embeddings.generate_embeddings import generate_embedding
from utils.logger import get_logger
from utils.watchdog import start_watchdog
from utils.vector import decode_emb, cosine_similarity
from api.api_errors import validation_error_response, conflict_error_response, bad_request_error_response


logger = get_logger("terms_api")
router = APIRouter()


# Pydantic models for Term
class TermBase(BaseModel):
    title: str = Field(..., min_length=2)
    definition: str = Field(..., min_length=1)
    domain_id: UUID
    layer_id: UUID
    parent_term_id: Optional[UUID] = None


class TermCreate(TermBase):
    pass


class TermUpdate(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    parent_term_id: Optional[UUID] = None


class TermOut(BaseModel):
    id: UUID
    title: str
    definition: str  # No min_length constraint for output
    domain_id: UUID
    layer_id: UUID
    parent_term_id: Optional[UUID] = None
    title_embedding: Optional[List[float]] = None
    definition_embedding: Optional[List[float]] = None
    created_at: str
    version: int
    last_modified: str


# --- FindTermRequest, FindTermResult, and /find endpoint ---
class FindTermRequest(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    layer_id: Optional[str] = None
    domain_id: Optional[str] = None
    created_at: Optional[str] = None  # ISO8601 string
    minimum_score: Optional[float] = 0.1
    limit: Optional[int] = 1


class FindTermResult(TermOut):
    score: float
    distance: float


class PaginatedTermsResponse(BaseModel):
    data: List[TermOut]
    total: int
    skip: int
    limit: int


def to_term_out(term):
    return TermOut(
        id=term.id,
        title=term.title,
        definition=term.definition,
        domain_id=term.domain_id,
        layer_id=term.layer_id,
        parent_term_id=term.parent_term_id,
        title_embedding=None,
        definition_embedding=None,
        created_at=term.created_at.isoformat(),
        version=term.version,
        last_modified=term.last_modified.isoformat() if term.last_modified else None,
    )


@router.post(
    "/find",
    response_model=List[FindTermResult],
    responses={
        405: {"description": "Method Not Allowed"},
        400: {"description": "Bad Request"},
        409: {"description": "Conflict"},
        500: {"description": "Internal Server Error"},
    },
)
def find_term(req: FindTermRequest, db: Session = Depends(get_db)):
    # Validate created_at if provided
    if req.created_at is not None:
        try:
            datetime.datetime.fromisoformat(req.created_at)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid created_at format. Must be ISO8601 string.")

    # Watchdog setup
    stop_event = threading.Event()
    search_details = {
        "title": req.title,
        "definition": req.definition,
        "layer_id": req.layer_id,
        "domain_id": req.domain_id,
        "created_at": req.created_at,
        "minimum_score": req.minimum_score,
        "limit": req.limit,
    }
    start_watchdog(stop_event, search_details, route="/api/terms/find")

    title_emb = generate_embedding(req.title) if req.title else None
    title_emb = decode_emb(title_emb)
    title_emb_str = "[" + ", ".join(f"{x:.6f}" for x in title_emb) + "]" if title_emb else None
    def_emb = generate_embedding(req.definition) if req.definition else None
    def_emb = decode_emb(def_emb)
    def_emb_str = "[" + ", ".join(f"{x:.6f}" for x in def_emb) + "]" if def_emb else None

    results = []
    sql = None
    limit = req.limit if req.limit is not None else 10
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
            SELECT t.id, t.title, t.definition, t.domain_id, t.layer_id, t.parent_term_id, t.title_embedding, t.definition_embedding, t.created_at, t.version, t.last_modified, v.distance
            FROM (
                SELECT id, distance
                FROM terms_vec
                WHERE {emb_type} match :emb_param
                ORDER BY distance
                LIMIT :limit
            ) v
            JOIN terms t ON t.id = v.id
            """
        )
    else:
        stop_event.set()
        raise HTTPException(status_code=400, detail="At least one of title or definition must be provided for search.")

    try:
        rows = db.execute(sql, {"emb_param": emb_param, "limit": limit}).fetchall()
        for row in rows:
            logger.debug(f"Found term: {row})")
            out = FindTermResult(
                id=row[0],
                title=row[1],
                definition=row[2],
                domain_id=row[3],
                layer_id=row[4],
                parent_term_id=row[5],
                title_embedding=None,
                definition_embedding=None,
                created_at=(row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8])),
                version=row[9],
                last_modified=(row[10].isoformat() if hasattr(row[10], "isoformat") else str(row[10])),
                score=cosine_similarity(title_emb or def_emb, decode_emb(row[6] if title_emb else row[7]) or []),
                distance=row[11],
            )
            if out.score >= (req.minimum_score or 0.0):
                results.append(out)
        stop_event.set()
        return results
    except Exception as e:
        import traceback
        logger.warning(f"sqlite-vec KNN search failed: {e}")
        logger.warning(traceback.format_exc())
    stop_event.set()
    return []


def check_circular_reference(db, term_id, parent_term_id):
    # Prevent circular references in hierarchy
    # Always compare as strings
    if term_id is not None:
        term_id = str(term_id)
    current = str(parent_term_id) if parent_term_id else None
    while current:
        if current == term_id:
            return True
        parent = db.query(models.Term).filter_by(id=current).first()
        if not parent:
            break
        current = str(parent.parent_term_id) if parent.parent_term_id else None
    return False


@router.post("/", response_model=TermOut, status_code=201)
def create_term(term: TermCreate, db: Session = Depends(get_db)):
    domain_id = str(term.domain_id)
    layer_id = str(term.layer_id)
    parent_term_id = str(term.parent_term_id) if term.parent_term_id else None
    if not term.title or not term.title.strip():
        return validation_error_response("Term title must not be empty.")
    if not db.query(models.Domain).filter_by(id=str(domain_id)).first():
        return bad_request_error_response("Domain does not exist.")
    if not db.query(models.Layer).filter_by(id=str(layer_id)).first():
        return bad_request_error_response("Layer does not exist.")
    if db.query(models.Term).filter_by(domain_id=str(domain_id), title=term.title).first():
        return conflict_error_response("Term title must be unique within domain.")
    if parent_term_id:
        parent = db.query(models.Term).filter_by(id=str(parent_term_id)).first()
        if not parent or str(parent.domain_id) != str(domain_id):
            return bad_request_error_response("Parent term must exist and belong to same domain.")
        if check_circular_reference(db, None, str(parent_term_id)):
            return bad_request_error_response("Circular reference detected.")
    title_emb = generate_embedding(term.title)
    # Always generate a valid embedding for definition (empty string if None)
    def_emb = generate_embedding(term.definition if term.definition is not None else "")
    now = datetime.datetime.now(datetime.UTC)
    db_term = models.Term(
        id=str(uuid4()),
        title=term.title,
        definition=term.definition,
        domain_id=domain_id,
        layer_id=layer_id,
        parent_term_id=parent_term_id,
        title_embedding=title_emb,
        definition_embedding=def_emb,
        created_at=now,
        last_modified=now,
        version=1,
    )
    db.add(db_term)
    db.commit()
    db.refresh(db_term)

    # Insert the sqlite vector index with the new embeddings
    sql = text(
        """
        INSERT INTO terms_vec (id, title_embedding, definition_embedding)
        VALUES (:id, :title_embedding, :definition_embedding)
    """
    )
    db.execute(
        sql,
        {
            "id": str(db_term.id),
            "title_embedding": db_term.title_embedding,
            "definition_embedding": db_term.definition_embedding,
        },
    )
    db.commit()

    db.close()  # Ensure connection is closed after commit for SQLite visibility
    return to_term_out(db_term)


@router.get("/{id}", response_model=TermOut, responses={404: {"description": "Term not found"}})
def get_term(id: str, db: Session = Depends(get_db)):
    term = db.query(models.Term).filter_by(id=id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found.")
    return to_term_out(term)


@router.get("/", response_model=PaginatedTermsResponse)
def list_terms(
    domain_id: str = None,
    layer_id: str = None,
    parent_term_id: str = None,
    skip: int = 0,
    limit: int = Query(50, le=100),
    sort: Optional[str] = Query(None, pattern="^(title|created_at)?$"),
    db: Session = Depends(get_db),
):
    # Build base query for both count and data
    q = db.query(models.Term)
    if domain_id:
        q = q.filter(models.Term.domain_id == str(domain_id))
    if layer_id:
        q = q.filter(models.Term.layer_id == str(layer_id))
    if parent_term_id:
        q = q.filter(models.Term.parent_term_id == str(parent_term_id))
    
    # Get total count
    total = q.count()
    
    # Apply sorting and pagination to get data
    if sort == "title":
        q = q.order_by(models.Term.title)
    elif sort == "created_at":
        q = q.order_by(models.Term.created_at.desc())
    terms = q.offset(skip).limit(limit).all()
    
    result = []
    for t in terms:
        result.append(to_term_out(t))
    
    return PaginatedTermsResponse(
        data=result,
        total=total,
        skip=skip,
        limit=limit
    )


@router.put("/{id}", response_model=TermOut)
def update_term(id: str, term: TermUpdate, db: Session = Depends(get_db)):
    db_term = db.query(models.Term).filter_by(id=id).first()
    if not db_term:
        raise HTTPException(status_code=404, detail="Term not found.")
    if term.title is not None:
        if not term.title.strip():
            return validation_error_response("Term title must not be empty.")
        if term.title != db_term.title:
            if (
                db.query(models.Term)
                .filter(
                    models.Term.domain_id == str(db_term.domain_id),
                    models.Term.title == term.title,
                    models.Term.id != str(id),
                )
                .first()
            ):
                return conflict_error_response("Term title must be unique within domain.")
            db_term.title = term.title
            db_term.title_embedding = generate_embedding(term.title)
    if term.definition is not None:
        db_term.definition = term.definition
        db_term.definition_embedding = generate_embedding(term.definition if term.definition is not None else "")
    if term.parent_term_id is not None:
        parent_term_id = str(term.parent_term_id) if term.parent_term_id else None
        if parent_term_id:
            parent = db.query(models.Term).filter_by(id=str(parent_term_id)).first()
            if not parent or str(parent.domain_id) != str(db_term.domain_id):
                return bad_request_error_response("Parent term must exist and belong to same domain.")
            if check_circular_reference(db, str(id), str(parent_term_id)):
                return bad_request_error_response("Circular reference detected.")
        db_term.parent_term_id = parent_term_id
    db_term.version += 1
    db_term.last_modified = datetime.datetime.now(datetime.UTC)
    db.commit()
    db.refresh(db_term)

    # Update the sqlite vector index with the new embeddings
    sql = text(
        """
        UPDATE terms_vec
        SET title_embedding = :title_embedding,
            definition_embedding = :definition_embedding
        WHERE id = :id
    """
    )
    db.execute(
        sql,
        {
            "id": str(db_term.id),
            "title_embedding": db_term.title_embedding,
            "definition_embedding": db_term.definition_embedding,
        },
    )
    db.commit()

    db.close()  # Ensure connection is closed after commit for SQLite visibility
    return to_term_out(db_term)


@router.delete("/{id}", status_code=200)
def delete_term(id: str, db: Session = Depends(get_db)):
    db_term = db.query(models.Term).filter_by(id=id).first()
    if not db_term:
        raise HTTPException(status_code=404, detail="Term not found.")
    
    # Orphan children: set their parent_term_id to None
    children = db.query(models.Term).filter_by(parent_term_id=id).all()
    for child in children:
        child.parent_term_id = None

    # Remove associated relationships
    db.query(models.TermRelationship).filter(
        (models.TermRelationship.source_term_id == id) | (models.TermRelationship.target_term_id == id)
    ).delete(synchronize_session=False)
    db.delete(db_term)
    db.commit()

    # Remove from sqlite vector index
    try:
        sql = text("DELETE FROM terms_vec WHERE id = :id")
        db.execute(sql, {"id": str(db_term.id)})
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to remove term from sqlite vector index: {e}")

    return {"success": True}
