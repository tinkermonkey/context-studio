import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from database import models
from database.utils import get_db
from database.predicate_utils import validate_term_relationship_predicate
from api.api_errors import validation_error_response, conflict_error_response, bad_request_error_response

router = APIRouter()

# Pydantic models for TermRelationship
class TermRelationshipBase(BaseModel):
    source_term_id: UUID
    target_term_id: UUID
    predicate: str
    predicate_id: Optional[str] = None  # UUID as string to match database storage

class TermRelationshipCreate(TermRelationshipBase):
    pass

class TermRelationshipUpdate(BaseModel):
    predicate: Optional[str] = None
    predicate_id: Optional[str] = None  # UUID as string to match database storage

class TermRelationshipOut(TermRelationshipBase):
    id: UUID
    created_at: str
    source_term: Optional[dict] = None
    target_term: Optional[dict] = None

def to_relationship_out(rel, source_term=None, target_term=None):
    return TermRelationshipOut(
        id=rel.id,
        source_term_id=rel.source_term_id,
        target_term_id=rel.target_term_id,
        predicate=rel.predicate,
        predicate_id=rel.predicate_id,
        created_at=rel.created_at.isoformat(),
        source_term=source_term,
        target_term=target_term
    )

@router.post("/", response_model=TermRelationshipOut, status_code=201)
def create_relationship(rel: TermRelationshipCreate, db: Session = Depends(get_db)):
    source_term_id = str(rel.source_term_id)
    target_term_id = str(rel.target_term_id)
    
    # Validate that both terms exist and get their domain IDs
    source_term = db.query(models.Term).filter_by(id=source_term_id).first()
    target_term = db.query(models.Term).filter_by(id=target_term_id).first()
    
    if not source_term or not target_term:
        raise HTTPException(status_code=400, detail="Both term IDs must exist.")
    
    # Validate predicate_id if provided
    if rel.predicate_id:
        predicate = db.query(models.Predicate).filter_by(id=str(rel.predicate_id)).first()
        if not predicate:
            raise HTTPException(status_code=404, detail="Predicate not found")
        
        # Validate predicate usage based on domain rules
        if not validate_term_relationship_predicate(
            source_term.domain_id, 
            target_term.domain_id, 
            str(rel.predicate_id), 
            db
        ):
            raise HTTPException(
                status_code=400,
                detail="Predicate not allowed for same-domain term relationship. "
                       "Check domain's predicate set configuration."
            )
    
    # Check for duplicate relationship
    existing = db.query(models.TermRelationship).filter_by(
        source_term_id=source_term_id, 
        target_term_id=target_term_id, 
        predicate=rel.predicate
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate relationship.")
    
    db_rel = models.TermRelationship(
        id=str(uuid4()),
        source_term_id=source_term_id,
        target_term_id=target_term_id,
        predicate=rel.predicate,
        predicate_id=str(rel.predicate_id) if rel.predicate_id else None,
        created_at=datetime.datetime.now(datetime.UTC)
    )
    db.add(db_rel)
    db.commit()
    db.refresh(db_rel)
    return to_relationship_out(db_rel)

@router.get("/{id}", response_model=TermRelationshipOut)
def get_relationship(id: str, db: Session = Depends(get_db)):
    rel = db.query(models.TermRelationship).filter_by(id=id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found.")
    source_term = db.query(models.Term).filter_by(id=rel.source_term_id).first()
    target_term = db.query(models.Term).filter_by(id=rel.target_term_id).first()
    return to_relationship_out(rel, source_term={"id": source_term.id, "title": source_term.title} if source_term else None, target_term={"id": target_term.id, "title": target_term.title} if target_term else None)

@router.get("/", response_model=List[TermRelationshipOut])
def list_relationships(
    source_term_id: str = None,
    target_term_id: str = None,
    predicate: str = None,
    predicate_id: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    q = db.query(models.TermRelationship)
    if source_term_id:
        q = q.filter(models.TermRelationship.source_term_id == str(source_term_id))
    if target_term_id:
        q = q.filter(models.TermRelationship.target_term_id == str(target_term_id))
    if predicate:
        q = q.filter(models.TermRelationship.predicate == predicate)
    if predicate_id:
        q = q.filter(models.TermRelationship.predicate_id == str(predicate_id))
    rels = q.offset(skip).limit(limit).all()
    result = []
    for r in rels:
        source_term = db.query(models.Term).filter_by(id=r.source_term_id).first()
        target_term = db.query(models.Term).filter_by(id=r.target_term_id).first()
        result.append(to_relationship_out(r, source_term={"id": source_term.id, "title": source_term.title} if source_term else None, target_term={"id": target_term.id, "title": target_term.title} if target_term else None))
    return result

@router.put("/{id}", response_model=TermRelationshipOut)
def update_relationship(id: str, rel: TermRelationshipUpdate, db: Session = Depends(get_db)):
    db_rel = db.query(models.TermRelationship).filter_by(id=id).first()
    if not db_rel:
        raise HTTPException(status_code=404, detail="Relationship not found.")
    
    # Update predicate if provided
    if rel.predicate is not None:
        db_rel.predicate = rel.predicate
    
    # Update predicate_id if provided
    if rel.predicate_id is not None:
        if rel.predicate_id:  # Check if it's not empty UUID or None
            predicate = db.query(models.Predicate).filter_by(id=str(rel.predicate_id)).first()
            if not predicate:
                raise HTTPException(status_code=404, detail="Predicate not found")
            
            # Get terms for validation
            source_term = db.query(models.Term).filter_by(id=db_rel.source_term_id).first()
            target_term = db.query(models.Term).filter_by(id=db_rel.target_term_id).first()
            
            # Validate predicate usage based on domain rules
            if source_term and target_term:
                if not validate_term_relationship_predicate(
                    source_term.domain_id, 
                    target_term.domain_id, 
                    str(rel.predicate_id), 
                    db
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="Predicate not allowed for same-domain term relationship. "
                               "Check domain's predicate set configuration."
                    )
            
            db_rel.predicate_id = str(rel.predicate_id)
        else:
            db_rel.predicate_id = None
    
    db.commit()
    db.refresh(db_rel)
    source_term = db.query(models.Term).filter_by(id=db_rel.source_term_id).first()
    target_term = db.query(models.Term).filter_by(id=db_rel.target_term_id).first()
    return to_relationship_out(db_rel, source_term={"id": source_term.id, "title": source_term.title} if source_term else None, target_term={"id": target_term.id, "title": target_term.title} if target_term else None)

@router.delete("/{id}", status_code=200)
def delete_relationship(id: str, db: Session = Depends(get_db)):
    db_rel = db.query(models.TermRelationship).filter_by(id=id).first()
    if not db_rel:
        raise HTTPException(status_code=404, detail="Relationship not found.")
    db.delete(db_rel)
    db.commit()
    return {"success": True}
