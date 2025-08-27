import threading
import datetime
import json
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from sqlalchemy.exc import IntegrityError
from database import models
from database.utils import get_db
from database.predicate_utils import validate_predicate_set
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
    primary_predicate_id: Optional[str] = None  # UUID as string to match database storage
    predicate_set: Optional[List[str]] = None  # Array of predicate identifiers


class DomainCreate(DomainBase):
    pass


class DomainUpdate(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    layer_id: Optional[UUID] = None
    primary_predicate_id: Optional[str] = None  # UUID as string to match database storage
    predicate_set: Optional[List[str]] = None


class DomainOut(DomainBase):
    id: UUID
    primary_predicate: Optional[str] = None  # Populated from predicate relationship
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


class PaginatedDomainsResponse(BaseModel):
    data: List[DomainOut]
    total: int
    skip: int
    limit: int


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
    # Parse predicate_set from JSON if present
    predicate_set_list = None
    if domain.predicate_set:
        try:
            predicate_set_list = json.loads(domain.predicate_set)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in domain {domain.id} predicate_set: {domain.predicate_set}")
            predicate_set_list = None
    
    return DomainOut(
        id=domain.id,
        title=domain.title,
        definition=domain.definition,
        layer_id=domain.layer_id,
        primary_predicate_id=domain.primary_predicate_id,
        primary_predicate=domain.primary_predicate,  # This will be populated from the predicate relationship
        predicate_set=predicate_set_list,
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
    # Check for duplicate title only within the same layer
    if db.query(models.Domain).filter_by(title=domain.title, layer_id=str(domain.layer_id)).first():
        return conflict_error_response("Domain title must be unique.")
    if not db.query(models.Layer).filter_by(id=str(domain.layer_id)).first():
        return bad_request_error_response("Layer does not exist.")
    
    # Validate primary_predicate_id if provided
    primary_predicate = None
    if domain.primary_predicate_id:
        primary_predicate = db.query(models.Predicate).filter_by(id=str(domain.primary_predicate_id)).first()
        if not primary_predicate:
            return bad_request_error_response("Primary predicate does not exist.")
    
    # Validate predicate_set if provided
    if domain.predicate_set:
        if not validate_predicate_set(domain.predicate_set, db):
            return bad_request_error_response("One or more predicates in predicate_set do not exist.")
    
    title_emb = generate_embedding(domain.title)
    # Always generate a valid embedding for definition (empty string if None)
    def_emb = generate_embedding(domain.definition if domain.definition is not None else "")
    
    # Serialize predicate_set to JSON if provided
    predicate_set_json = None
    if domain.predicate_set:
        try:
            predicate_set_json = json.dumps(domain.predicate_set)
        except (TypeError, ValueError) as e:
            return validation_error_response(f"Invalid predicate_set format: {str(e)}", loc=["body", "predicate_set"])
    
    db_domain = models.Domain(
        id=str(uuid4()),
        title=domain.title,
        definition=domain.definition,
        layer_id=str(domain.layer_id),
        primary_predicate_id=str(domain.primary_predicate_id) if domain.primary_predicate_id else None,
        primary_predicate=primary_predicate.title if primary_predicate else None,
        predicate_set=predicate_set_json,
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


@router.get("/", response_model=PaginatedDomainsResponse)
def list_domains(
    layer_id: str = None,
    skip: int = 0,
    limit: int = Query(50, le=100),
    sortBy: str = Query("title", pattern="^(title|created_at)$"),
    db: Session = Depends(get_db),
):
    # Build base query for both count and data
    q = db.query(models.Domain)
    if layer_id:
        q = q.filter(models.Domain.layer_id == layer_id)
    
    # Get total count
    total = q.count()
    
    # Apply sorting and pagination to get data
    if sortBy == "title":
        q = q.order_by(models.Domain.title)
    elif sortBy == "created_at":
        q = q.order_by(models.Domain.created_at.desc())
    domains = q.offset(skip).limit(limit).all()
    
    result = []
    for d in domains:
        result.append(to_domain_out(d))
    
    return PaginatedDomainsResponse(
        data=result,
        total=total,
        skip=skip,
        limit=limit
    )


@router.put("/{id}", response_model=DomainOut, responses={404: {"description": "Domain not found"}})
def update_domain(id: str, domain: DomainUpdate, db: Session = Depends(get_db)):
    db_domain = db.query(models.Domain).filter_by(id=id).first()
    if not db_domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    
    embeddings_updated = False
    
    if domain.title is not None:
        if not domain.title.strip():
            return validation_error_response("Domain title must not be empty.", loc=["body", "title"])
        if domain.title != db_domain.title:
            if db.query(models.Domain).filter(models.Domain.title == domain.title, models.Domain.id != str(id)).first():
                return conflict_error_response("Domain title must be unique.")
            db_domain.title = domain.title
            db_domain.title_embedding = generate_embedding(domain.title)
            embeddings_updated = True
    
    if domain.definition is not None:
        db_domain.definition = domain.definition
        db_domain.definition_embedding = generate_embedding(domain.definition if domain.definition is not None else "")
        embeddings_updated = True
    
    if domain.layer_id is not None and str(domain.layer_id) != str(db_domain.layer_id):
        if not db.query(models.Layer).filter_by(id=str(domain.layer_id)).first():
            return bad_request_error_response("Layer does not exist.")
        db_domain.layer_id = str(domain.layer_id)
    
    # Handle primary_predicate_id update
    if domain.primary_predicate_id is not None:
        if str(domain.primary_predicate_id) != str(db_domain.primary_predicate_id or ''):
            primary_predicate = db.query(models.Predicate).filter_by(id=str(domain.primary_predicate_id)).first()
            if not primary_predicate:
                return bad_request_error_response("Primary predicate does not exist.")
            db_domain.primary_predicate_id = str(domain.primary_predicate_id)
            db_domain.primary_predicate = primary_predicate.title
    
    # Handle predicate_set update
    if domain.predicate_set is not None:
        if domain.predicate_set:
            if not validate_predicate_set(domain.predicate_set, db):
                return bad_request_error_response("One or more predicates in predicate_set do not exist.")
            try:
                db_domain.predicate_set = json.dumps(domain.predicate_set)
            except (TypeError, ValueError) as e:
                return validation_error_response(f"Invalid predicate_set format: {str(e)}", loc=["body", "predicate_set"])
        else:
            db_domain.predicate_set = None
    
    db.commit()
    db.refresh(db_domain)

    # Update the sqlite vector index with the new embeddings if they were updated
    if embeddings_updated:
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


# Move functionality
class MoveDomainRequest(BaseModel):
    domain_ids: List[UUID]
    target_layer_id: UUID
    move_terms: bool = True


class MoveDomainResponse(BaseModel):
    moved_domains: List[DomainOut]
    moved_terms: List[DomainOut]  # Using DomainOut as placeholder - will contain TermOut in actual implementation
    warnings: List[str]


def move_domains_with_lineage(
    db: Session,
    domain_ids: List[str],
    target_layer_id: str,
    move_terms: bool = True
) -> MoveDomainResponse:
    """
    Move domains to a new layer with all their terms.
    """
    moved_domains = []
    moved_terms = []
    warnings = []
    
    # 1. Validate target layer exists
    target_layer = db.query(models.Layer).filter_by(id=str(target_layer_id)).first()
    if not target_layer:
        raise HTTPException(status_code=400, detail="Target layer does not exist.")
    
    # 2. Validate all domains exist and get current state
    domains_to_move = []
    old_data = {}
    
    for domain_id in domain_ids:
        domain = db.query(models.Domain).filter_by(id=str(domain_id)).first()
        if not domain:
            warnings.append(f"Domain {domain_id} not found, skipping.")
            continue
        
        # Store old data for event logging
        old_data[domain.id] = {
            "id": domain.id,
            "layer_id": domain.layer_id,
            "title": domain.title
        }
        
        domains_to_move.append(domain)
    
    if not domains_to_move:
        raise HTTPException(status_code=400, detail="No valid domains found to move.")
    
    # 3. Check for title conflicts in target layer
    existing_titles = {d.title for d in db.query(models.Domain).filter_by(layer_id=str(target_layer_id)).all()}
    
    for domain in domains_to_move:
        if domain.title in existing_titles and str(domain.layer_id) != str(target_layer_id):
            warnings.append(f"Domain '{domain.title}' already exists in target layer.")
    
    # 4. Begin transaction and update domains
    from sqlalchemy.exc import IntegrityError
    try:
        # Update domain layer_id
        for domain in domains_to_move:
            if str(domain.layer_id) != str(target_layer_id):
                domain.layer_id = str(target_layer_id)
                domain.last_modified = datetime.datetime.now(datetime.UTC)
                moved_domains.append(to_domain_out(domain))

        # 5. If move_terms=True, update all terms' layer_id
        if move_terms:
            for domain in domains_to_move:
                terms = db.query(models.Term).filter_by(domain_id=domain.id).all()
                for term in terms:
                    if str(term.layer_id) != str(target_layer_id):
                        term.layer_id = str(target_layer_id)
                        term.last_modified = datetime.datetime.now(datetime.UTC)
                        term.version += 1

        # 6. Log changes to GraphEvent
        for domain in domains_to_move:
            event = models.GraphEvent(
                event_type="update",
                entity_type="domain",
                old_data=old_data.get(domain.id),
                new_data={
                    "id": domain.id,
                    "layer_id": domain.layer_id,
                    "title": domain.title
                },
                timestamp=datetime.datetime.now(datetime.UTC),
                processed=False
            )
            db.add(event)

        db.commit()

    except IntegrityError:
        db.rollback()
        warnings.append("Domain title conflict: a domain with the same title already exists in the target layer.")
        return MoveDomainResponse(moved_domains=[], moved_terms=[], warnings=warnings)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to move domains: {str(e)}")

    return MoveDomainResponse(
        moved_domains=moved_domains,
        moved_terms=moved_terms,  # Will be populated with actual term data in real implementation
        warnings=warnings
    )


@router.post("/move", response_model=MoveDomainResponse)
def move_domains(request: MoveDomainRequest, db: Session = Depends(get_db)):
    """Move domains to a new layer with all their terms."""
    response = move_domains_with_lineage(
        db,
        [str(d) for d in request.domain_ids],
        str(request.target_layer_id),
        move_terms=request.move_terms
    )
    return response
