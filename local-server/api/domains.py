import threading
import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import models
from database.utils import get_db
from embeddings.generate_embeddings import generate_embedding
from utils.logger import get_logger
from utils.watchdog import start_watchdog
from utils.vector import decode_emb, cosine_similarity
from api.api_errors import validation_error_response, conflict_error_response, bad_request_error_response

logger = get_logger("domains_api")
router = APIRouter()


# Pydantic models for Domain
class DomainBase(BaseModel):
    title: str = Field(..., min_length=2)
    definition: str = Field(..., min_length=1)
    layer_id: UUID


class DomainCreate(DomainBase):
    pass


class DomainUpdate(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    layer_id: Optional[UUID] = None


class DomainOut(DomainBase):
    id: UUID
    title_embedding: Optional[List[float]] = None
    definition_embedding: Optional[List[float]] = None
    created_at: str
    version: Optional[int] = None
    last_modified: Optional[str] = None  # ISO8601 string


class FindDomainRequest(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    layer_id: Optional[str] = None
    created_at: Optional[str] = None  # ISO8601 string
    minimum_score: Optional[float] = 0.1
    limit: Optional[int] = 1


class FindDomainResult(DomainOut):
    score: float
    distance: float


@router.post(
    "/find",
    response_model=List[FindDomainResult],
    responses={
        405: {"description": "Method Not Allowed"},
        400: {"description": "Bad Request"},
        409: {"description": "Conflict"},
        500: {"description": "Internal Server Error"},
    },
)
@router.put("/find", response_model=None, responses={405: {"description": "Method Not Allowed"}})
@router.get("/find", response_model=None, responses={405: {"description": "Method Not Allowed"}})
@router.delete("/find", response_model=None, responses={405: {"description": "Method Not Allowed"}})
def find_domain_unsupported_method_delete():
    """Return 405 for unsupported DELETE method on /find endpoint."""
    raise HTTPException(status_code=405, detail="Method Not Allowed")
def find_domain_unsupported_method_get():
    """Return 405 for unsupported GET method on /find endpoint."""
    raise HTTPException(status_code=405, detail="Method Not Allowed")
def find_domain_unsupported_method():
    """Return 405 for unsupported PUT method on /find endpoint."""
    raise HTTPException(status_code=405, detail="Method Not Allowed")
def find_domain(req: FindDomainRequest, db: Session = Depends(get_db)):
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
        "layer_id": req.layer_id,
        "created_at": req.created_at,
        "minimum_score": req.minimum_score,
        "limit": req.limit,
    }
    start_watchdog(stop_event, search_details, route="/api/domains/find")

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
            SELECT d.id, d.title, d.definition, d.layer_id, d.title_embedding, d.definition_embedding, d.created_at, d.version, d.last_modified, v.distance
            FROM (
                SELECT id, distance
                FROM domains_vec
                WHERE {emb_type} match :emb_param
                ORDER BY distance
                LIMIT :limit
            ) v
            JOIN domains d ON d.id = v.id
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
            out = FindDomainResult(
                id=row[0],
                title=row[1],
                definition=row[2],
                layer_id=row[3],
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


def to_domain_out(domain):
    return DomainOut(
        id=domain.id,
        title=domain.title,
        definition=domain.definition,
        layer_id=domain.layer_id,
        title_embedding=decode_emb(domain.title_embedding) if domain.title_embedding else None,
        definition_embedding=decode_emb(domain.definition_embedding) if domain.definition_embedding else None,
        created_at=domain.created_at.isoformat(),
        version=domain.version,
        last_modified=(domain.last_modified.isoformat() if domain.last_modified else None),
    )


@router.post("/", response_model=DomainOut, status_code=201)
def create_domain(domain: DomainCreate, db: Session = Depends(get_db)):
    if not domain.title or not domain.title.strip():
        return validation_error_response("Domain title must not be empty.", loc=["body", "title"])
    if db.query(models.Domain).filter_by(title=domain.title).first():
        return conflict_error_response("Domain title must be unique.")
    if not db.query(models.Layer).filter_by(id=str(domain.layer_id)).first():
        return bad_request_error_response("Layer does not exist.")
    title_emb = generate_embedding(domain.title)
    # Always generate a valid embedding for definition (empty string if None)
    def_emb = generate_embedding(domain.definition if domain.definition is not None else "")
    db_domain = models.Domain(
        id=str(uuid4()),
        title=domain.title,
        definition=domain.definition,
        layer_id=str(domain.layer_id),
        title_embedding=title_emb,
        definition_embedding=def_emb,
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(db_domain)
    db.commit()
    db.refresh(db_domain)

    # Insert the sqlite vector index with the new embeddings
    sql = text(
        """
        INSERT INTO domains_vec (id, title_embedding, definition_embedding)
        VALUES (:id, :title_embedding, :definition_embedding)
    """
    )
    db.execute(
        sql,
        {
            "id": str(db_domain.id),
            "title_embedding": db_domain.title_embedding,
            "definition_embedding": db_domain.definition_embedding,
        },
    )
    db.commit()

    db.close()  # Ensure connection is closed after commit for SQLite visibility
    return to_domain_out(db_domain)


@router.get("/{id}", response_model=DomainOut, responses={404: {"description": "Domain not found"}})
def get_domain(id: str, db: Session = Depends(get_db)):
    domain = db.query(models.Domain).filter_by(id=id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    return to_domain_out(domain)


@router.get("/", response_model=List[DomainOut])
def list_domains(
    layer_id: str = None,
    skip: int = 0,
    limit: int = Query(50, le=100),
    sort: Optional[str] = Query(None, pattern="^(title|created_at)?$"),
    db: Session = Depends(get_db),
):
    q = db.query(models.Domain)
    if layer_id:
        q = q.filter(models.Domain.layer_id == layer_id)
    if sort == "title":
        q = q.order_by(models.Domain.title)
    elif sort == "created_at":
        q = q.order_by(models.Domain.created_at.desc())
    domains = q.offset(skip).limit(limit).all()
    result = []
    for d in domains:
        result.append(to_domain_out(d))
    return result


@router.put("/{id}", response_model=DomainOut, responses={404: {"description": "Domain not found"}})
def update_domain(id: str, domain: DomainUpdate, db: Session = Depends(get_db)):
    db_domain = db.query(models.Domain).filter_by(id=id).first()
    if not db_domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    if domain.title is not None:
        if not domain.title.strip():
            return validation_error_response("Domain title must not be empty.", loc=["body", "title"])
        if domain.title != db_domain.title:
            if db.query(models.Domain).filter(models.Domain.title == domain.title, models.Domain.id != str(id)).first():
                return conflict_error_response("Domain title must be unique.")
            db_domain.title = domain.title
            db_domain.title_embedding = generate_embedding(domain.title)
    if domain.definition is not None:
        db_domain.definition = domain.definition
        db_domain.definition_embedding = generate_embedding(domain.definition if domain.definition is not None else "")
    if domain.layer_id is not None and str(domain.layer_id) != str(db_domain.layer_id):
        if not db.query(models.Layer).filter_by(id=str(domain.layer_id)).first():
            return bad_request_error_response("Layer does not exist.")
        db_domain.layer_id = str(domain.layer_id)
    db.commit()
    db.refresh(db_domain)

    # Update the sqlite vector index with the new embeddings
    sql = text(
        """
        UPDATE domains_vec
        SET title_embedding = :title_embedding,
            definition_embedding = :definition_embedding
        WHERE id = :id
    """
    )
    db.execute(
        sql,
        {
            "id": str(db_domain.id),
            "title_embedding": db_domain.title_embedding,
            "definition_embedding": db_domain.definition_embedding,
        },
    )
    db.commit()

    db.close()  # Ensure connection is closed after commit for SQLite visibility
    return to_domain_out(db_domain)


@router.delete("/{id}", status_code=200, responses={404: {"description": "Domain not found"}})
def delete_domain(id: str, db: Session = Depends(get_db)):
    db_domain = db.query(models.Domain).filter_by(id=id).first()
    if not db_domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    db.delete(db_domain)
    db.commit()

    # Delete associated virtual table entry if exists
    try:
        sql = text("DELETE FROM domains_vec WHERE id = :id")
        db.execute(sql, {"id": id})
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to delete virtual table entry for domain {id}: {e}")
        
    return {"success": True}
