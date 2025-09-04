"""API endpoints for predicate management."""

import datetime
import json
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import models
from database.utils import get_db
from database.predicate_utils import generate_identifier_from_title, validate_predicate_set, import_conceptnet_predicates, get_conceptnet_relation_for_predicate, validate_predicate_identifier
from config import get_settings
from api.api_errors import validation_error_response, conflict_error_response, bad_request_error_response
from utils.logger import get_logger

logger = get_logger("predicates_api")
router = APIRouter()


def validate_uuid_format(uuid_string: str) -> bool:
    """Validate that a string is a valid UUID format."""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False


# Pydantic models for Predicate
class PredicateBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    definition: Optional[str] = None
    mapping: Optional[dict] = None  # Will be serialized to JSON


class PredicateCreate(PredicateBase):
    identifier: Optional[str] = None  # Auto-generated if not provided


class PredicateUpdate(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    mapping: Optional[dict] = None
    identifier: Optional[str] = None  # Allow identifier updates with validation


class PredicateOut(PredicateBase):
    id: str  # UUID as string to match database storage
    identifier: str
    date_created: str  # ISO8601
    date_modified: str  # ISO8601

    model_config = ConfigDict(from_attributes=True)


class PaginatedPredicatesResponse(BaseModel):
    data: List[PredicateOut]
    total: int
    skip: int
    limit: int


def to_predicate_out(predicate: models.Predicate) -> PredicateOut:
    """Convert database model to API response model."""
    mapping_dict = None
    if predicate.mapping:
        try:
            mapping_dict = json.loads(predicate.mapping)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in predicate {predicate.id} mapping: {predicate.mapping}")
            mapping_dict = None
    
    return PredicateOut(
        id=predicate.id,
        identifier=predicate.identifier,
        title=predicate.title,
        definition=predicate.definition,
        mapping=mapping_dict,
        date_created=predicate.date_created.isoformat(),
        date_modified=predicate.date_modified.isoformat()
    )


@router.post("/", response_model=PredicateOut, status_code=201)
def create_predicate(predicate: PredicateCreate, db: Session = Depends(get_db)):
    """Create a new predicate."""
    if not predicate.title or not predicate.title.strip():
        return validation_error_response("Predicate title must not be empty.", loc=["body", "title"])
    
    # Generate identifier if not provided
    identifier = predicate.identifier
    if not identifier:
        identifier = generate_identifier_from_title(predicate.title)
    
    # Validate identifier uniqueness
    if not validate_predicate_identifier(identifier, None, db):
        return conflict_error_response(f"Predicate with identifier '{identifier}' already exists.")
    
    # Validate title uniqueness
    if db.query(models.Predicate).filter_by(title=predicate.title).first():
        return conflict_error_response(f"Predicate with title '{predicate.title}' already exists.")
    
    # Serialize mapping to JSON if provided
    mapping_json = None
    if predicate.mapping:
        try:
            mapping_json = json.dumps(predicate.mapping)
        except (TypeError, ValueError) as e:
            return validation_error_response(f"Invalid mapping format: {str(e)}", loc=["body", "mapping"])
    
    try:
        db_predicate = models.Predicate(
            id=str(uuid4()),
            identifier=identifier,
            title=predicate.title,
            definition=predicate.definition,
            mapping=mapping_json,
            date_created=datetime.datetime.now(datetime.UTC),
            date_modified=datetime.datetime.now(datetime.UTC)
        )
        db.add(db_predicate)
        db.commit()
        db.refresh(db_predicate)
        
        return to_predicate_out(db_predicate)
        
    except IntegrityError:
        db.rollback()
        return conflict_error_response("Predicate with this identifier or title already exists.")


@router.get("/{id}", response_model=PredicateOut, responses={404: {"description": "Predicate not found"}})
def get_predicate(id: str, db: Session = Depends(get_db)):
    """Get a predicate by ID."""
    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
    
    predicate = db.query(models.Predicate).filter_by(id=id).first()
    if not predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")
    
    return to_predicate_out(predicate)


@router.get("/", response_model=PaginatedPredicatesResponse)
def list_predicates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sortBy: str = Query("title", pattern="^(title|identifier|date_created)$"),
    db: Session = Depends(get_db)
):
    """List predicates with pagination and sorting."""
    # Build base query
    query = db.query(models.Predicate)
    
    # Get total count
    total = query.count()
    
    # Apply sorting
    if sortBy == "title":
        query = query.order_by(models.Predicate.title)
    elif sortBy == "identifier":
        query = query.order_by(models.Predicate.identifier)
    elif sortBy == "date_created":
        query = query.order_by(models.Predicate.date_created.desc())
    
    # Apply pagination
    predicates = query.offset(skip).limit(limit).all()
    
    # Convert to response models
    result = [to_predicate_out(p) for p in predicates]
    
    return PaginatedPredicatesResponse(
        data=result,
        total=total,
        skip=skip,
        limit=limit
    )


@router.put("/{id}", response_model=PredicateOut, responses={404: {"description": "Predicate not found"}})
def update_predicate(id: str, predicate: PredicateUpdate, db: Session = Depends(get_db)):
    """Update an existing predicate."""
    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
    
    db_predicate = db.query(models.Predicate).filter_by(id=id).first()
    if not db_predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")
    
    # Update identifier if provided
    if predicate.identifier is not None:
        if predicate.identifier != db_predicate.identifier:
            # Validate identifier uniqueness
            if not validate_predicate_identifier(predicate.identifier, id, db):
                return conflict_error_response(f"Predicate with identifier '{predicate.identifier}' already exists.")
            db_predicate.identifier = predicate.identifier
    
    # Update title if provided
    if predicate.title is not None:
        if not predicate.title.strip():
            return validation_error_response("Predicate title must not be empty.", loc=["body", "title"])
        
        # Check title uniqueness (excluding current predicate)
        if predicate.title != db_predicate.title:
            existing = db.query(models.Predicate).filter(
                models.Predicate.title == predicate.title,
                models.Predicate.id != id
            ).first()
            if existing:
                return conflict_error_response(f"Predicate with title '{predicate.title}' already exists.")
        
        db_predicate.title = predicate.title
    
    # Update definition if provided
    if predicate.definition is not None:
        db_predicate.definition = predicate.definition
    
    # Update mapping if provided
    if predicate.mapping is not None:
        try:
            mapping_json = json.dumps(predicate.mapping)
            db_predicate.mapping = mapping_json
        except (TypeError, ValueError) as e:
            return validation_error_response(f"Invalid mapping format: {str(e)}", loc=["body", "mapping"])
    
    # Update modification timestamp
    db_predicate.date_modified = datetime.datetime.now(datetime.UTC)
    
    try:
        db.commit()
        db.refresh(db_predicate)
        return to_predicate_out(db_predicate)
        
    except IntegrityError:
        db.rollback()
        return conflict_error_response("Update would create duplicate identifier or title.")


@router.delete("/{id}", status_code=200, responses={404: {"description": "Predicate not found"}})
def delete_predicate(id: str, db: Session = Depends(get_db)):
    """Delete a predicate."""
    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
    
    db_predicate = db.query(models.Predicate).filter_by(id=id).first()
    if not db_predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")
    
    # Check if predicate is being used in domains or term relationships
    domain_usage = db.query(models.Domain).filter_by(primary_predicate_id=id).count()
    relationship_usage = db.query(models.TermRelationship).filter_by(predicate_id=id).count()
    
    if domain_usage > 0 or relationship_usage > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete predicate: it is used in {domain_usage} domains and {relationship_usage} term relationships."
        )
    
    db.delete(db_predicate)
    db.commit()
    
    return {"success": True}


@router.get("/by-identifier/{identifier}", response_model=PredicateOut, responses={404: {"description": "Predicate not found"}})
def get_predicate_by_identifier(identifier: str, db: Session = Depends(get_db)):
    """Get a predicate by its identifier."""
    predicate = db.query(models.Predicate).filter_by(identifier=identifier).first()
    if not predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")
    
    return to_predicate_out(predicate)


# ConceptNet Integration Endpoints
@router.get("/conceptnet-relations", response_model=List[str])
def get_conceptnet_relations():
    """Get the list of ConceptNet relations configured in the system."""
    settings = get_settings()
    return settings.concepcy_config["relations_of_interest"]


@router.post("/import-from-conceptnet", response_model=List[PredicateOut])
def import_predicates_from_conceptnet(
    relations: Optional[List[str]] = None,  # If None, import all configured relations
    db: Session = Depends(get_db)
):
    """Import predicates from ConceptNet relations."""
    settings = get_settings()
    available_relations = settings.concepcy_config["relations_of_interest"]
    
    # If specific relations are requested, validate and filter
    if relations:
        # Validate that all requested relations are available
        invalid_relations = [r for r in relations if r not in available_relations]
        if invalid_relations:
            return bad_request_error_response(f"Invalid ConceptNet relations: {invalid_relations}")
        
        # Temporarily update the config to only import requested relations
        # We'll create a modified session for this specific import
        original_relations = settings.concepcy_config["relations_of_interest"]
        settings.concepcy_config["relations_of_interest"] = relations
        
        try:
            imported_predicates = import_conceptnet_predicates(db)
        finally:
            # Restore original configuration
            settings.concepcy_config["relations_of_interest"] = original_relations
    else:
        # Import all configured relations
        imported_predicates = import_conceptnet_predicates(db)
    
    # Convert to response models
    result = [to_predicate_out(predicate) for predicate in imported_predicates]
    
    return result


@router.get("/{id}/conceptnet-relation", response_model=Optional[str])
def get_predicate_conceptnet_relation(id: str, db: Session = Depends(get_db)):
    """Get the ConceptNet relation for a specific predicate."""
    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
    
    predicate = db.query(models.Predicate).filter_by(id=id).first()
    if not predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")
    
    relation = get_conceptnet_relation_for_predicate(predicate)
    return relation


@router.get("/conceptnet-mapping", response_model=Dict[str, str])
def get_conceptnet_mapping(db: Session = Depends(get_db)):
    """Get a mapping of all predicate identifiers to their ConceptNet relations."""
    predicates = db.query(models.Predicate).all()
    mapping = {}
    
    for predicate in predicates:
        conceptnet_relation = get_conceptnet_relation_for_predicate(predicate)
        if conceptnet_relation:
            mapping[predicate.identifier] = conceptnet_relation
    
    return mapping
