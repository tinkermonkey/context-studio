import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from database import models
from database.utils import get_db

router = APIRouter()

# Pydantic models for TermRelationship
class TermRelationshipBase(BaseModel):
    source_term_id: UUID
    target_term_id: UUID
    predicate: str

class TermRelationshipCreate(TermRelationshipBase):
    pass

class TermRelationshipUpdate(BaseModel):
    predicate: str

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
        created_at=rel.created_at.isoformat(),
        source_term=source_term,
        target_term=target_term
    )

@router.post("/", response_model=TermRelationshipOut, status_code=201)
def create_relationship(rel: TermRelationshipCreate, db: Session = Depends(get_db)):
    source_term_id = str(rel.source_term_id)
    target_term_id = str(rel.target_term_id)
    if not db.query(models.Term).filter_by(id=str(source_term_id)).first() or not db.query(models.Term).filter_by(id=str(target_term_id)).first():
        raise HTTPException(status_code=400, detail="Both term IDs must exist.")
    if db.query(models.TermRelationship).filter_by(source_term_id=str(source_term_id), target_term_id=str(target_term_id), predicate=rel.predicate).first():
        raise HTTPException(status_code=400, detail="Duplicate relationship.")
    db_rel = models.TermRelationship(
        id=str(uuid4()),
        source_term_id=str(source_term_id),
        target_term_id=str(target_term_id),
        predicate=rel.predicate,
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
    db_rel.predicate = rel.predicate
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
