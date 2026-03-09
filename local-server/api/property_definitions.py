"""
Property Definitions API Endpoints

This module implements the new property_definitions API endpoints using new terminology
alongside the existing predicates API.

Endpoints:
- POST /api/property_definitions/ - Create a new property definition
- GET /api/property_definitions/ - List property definitions
- GET /api/property_definitions/{id} - Get a specific property definition
- GET /api/property_definitions/by-identifier/{identifier} - Get by identifier
- PUT /api/property_definitions/{id} - Update a property definition
- DELETE /api/property_definitions/{id} - Delete a property definition
"""

import datetime
import json
from fastapi import APIRouter, HTTPException, Query, Depends, Path, Body
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import models
from database.utils import get_db
from database.predicate_utils import (
    generate_identifier_from_title, validate_predicate_identifier
)
from api.models.property_definitions import (
    PropertyDefinitionCreate, PropertyDefinitionUpdate,
    PropertyDefinitionOut, PaginatedPropertyDefinitionsResponse
)
from utils.logger import get_logger

logger = get_logger("property_definitions_api")
router = APIRouter(prefix="/api/property_definitions", tags=["property_definitions"])


def to_property_definition_out(predicate: models.Predicate) -> PropertyDefinitionOut:
    """Convert database predicate model to property definition API response."""
    mapping_dict = None
    if predicate.mapping:
        try:
            mapping_dict = json.loads(predicate.mapping)  # type: ignore[arg-type]
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in predicate {predicate.id} mapping: {predicate.mapping}")  # noqa: E501
            mapping_dict = None

    return PropertyDefinitionOut(
        id=predicate.id,  # type: ignore[arg-type]
        identifier=predicate.identifier,  # type: ignore[arg-type]
        title=predicate.title,  # type: ignore[arg-type]
        definition=predicate.definition,  # type: ignore[arg-type]
        mapping=mapping_dict,
        date_created=predicate.date_created.isoformat(),
        date_modified=predicate.date_modified.isoformat()
    )


@router.post("/", response_model=PropertyDefinitionOut, status_code=201)
def create_property_definition(
    property_def: PropertyDefinitionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new property definition.

    This endpoint creates a predicate using new terminology (property_definitions).
    """
    if not property_def.title or not property_def.title.strip():
        raise HTTPException(status_code=400, detail="Property definition title must not be empty.")  # noqa: E501

    # Generate identifier if not provided
    identifier = property_def.identifier
    if not identifier:
        identifier = generate_identifier_from_title(property_def.title)

    # Validate identifier uniqueness
    if not validate_predicate_identifier(identifier, None, db):
        raise HTTPException(status_code=409, detail=f"Property definition with identifier '{identifier}' already exists.")  # noqa: E501

    # Validate title uniqueness
    if db.query(models.Predicate).filter_by(title=property_def.title).first():
        raise HTTPException(status_code=409, detail=f"Property definition with title '{property_def.title}' already exists.")  # noqa: E501

    # Serialize mapping to JSON if provided
    mapping_json = None
    if property_def.mapping:
        try:
            mapping_json = json.dumps(property_def.mapping)
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid mapping format: {str(e)}")  # noqa: E501

    try:
        db_predicate = models.Predicate(
            id=str(uuid4()),
            identifier=identifier,
            title=property_def.title,
            definition=property_def.definition,
            mapping=mapping_json,
            date_created=datetime.datetime.now(datetime.UTC),
            date_modified=datetime.datetime.now(datetime.UTC)
        )
        db.add(db_predicate)
        db.commit()
        db.refresh(db_predicate)

        return to_property_definition_out(db_predicate)

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Property definition with this identifier or title already exists.")  # noqa: E501


@router.get("/", response_model=PaginatedPropertyDefinitionsResponse)
def list_property_definitions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sortBy: str = Query("title", pattern="^(title|identifier|date_created)$"),
    db: Session = Depends(get_db)
):
    """
    List property definitions with pagination and sorting.

    This endpoint lists predicates using new terminology (property_definitions).
    """
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
    result = [to_property_definition_out(p) for p in predicates]

    return PaginatedPropertyDefinitionsResponse(
        data=result,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{property_def_id}", response_model=PropertyDefinitionOut)
def get_property_definition(
    property_def_id: UUID = Path(..., description="The ID of the property definition to retrieve"),  # noqa: E501
    db: Session = Depends(get_db)
):
    """
    Get a specific property definition by ID.

    Returns the complete property definition information.
    """
    predicate = db.query(models.Predicate).filter_by(id=str(property_def_id)).first()  # noqa: E501
    if not predicate:
        raise HTTPException(status_code=404, detail="Property definition not found")

    return to_property_definition_out(predicate)


@router.get("/by-identifier/{identifier}", response_model=PropertyDefinitionOut)
def get_property_definition_by_identifier(
    identifier: str = Path(..., description="The identifier of the property definition"),
    db: Session = Depends(get_db)
):
    """
    Get a property definition by its identifier.

    Returns the complete property definition information.
    """
    predicate = db.query(models.Predicate).filter_by(identifier=identifier).first()  # noqa: E501
    if not predicate:
        raise HTTPException(status_code=404, detail="Property definition not found")

    return to_property_definition_out(predicate)


@router.put("/{property_def_id}", response_model=PropertyDefinitionOut)
def update_property_definition(
    property_def_id: UUID = Path(..., description="The ID of the property definition to update"),  # noqa: E501
    property_def_update: PropertyDefinitionUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update a property definition.

    Allows updating title, definition, identifier, and mapping.
    """
    predicate = db.query(models.Predicate).filter_by(id=str(property_def_id)).first()  # noqa: E501
    if not predicate:
        raise HTTPException(status_code=404, detail="Property definition not found")

    try:
        # Update fields if provided
        if property_def_update.title is not None:
            # Validate title uniqueness if changed
            if property_def_update.title != predicate.title:
                if db.query(models.Predicate).filter_by(title=property_def_update.title).first():  # noqa: E501
                    raise HTTPException(status_code=409, detail=f"Property definition with title '{property_def_update.title}' already exists.")  # noqa: E501
            predicate.title = property_def_update.title  # type: ignore[assignment]

        if property_def_update.definition is not None:
            predicate.definition = property_def_update.definition  # type: ignore[assignment]

        if property_def_update.identifier is not None:
            # Validate identifier uniqueness if changed
            if property_def_update.identifier != predicate.identifier:
                if not validate_predicate_identifier(property_def_update.identifier, str(property_def_id), db):  # noqa: E501
                    raise HTTPException(status_code=409, detail=f"Property definition with identifier '{property_def_update.identifier}' already exists.")  # noqa: E501
            predicate.identifier = property_def_update.identifier  # type: ignore[assignment]

        if property_def_update.mapping is not None:
            try:
                predicate.mapping = json.dumps(property_def_update.mapping)  # type: ignore[assignment]
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid mapping format: {str(e)}")  # noqa: E501

        predicate.date_modified = datetime.datetime.now(datetime.UTC)  # type: ignore[assignment]
        db.commit()
        db.refresh(predicate)

        return to_property_definition_out(predicate)

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Property definition with this identifier or title already exists.")  # noqa: E501


@router.delete("/{property_def_id}", status_code=204)
def delete_property_definition(
    property_def_id: UUID = Path(..., description="The ID of the property definition to delete"),  # noqa: E501
    db: Session = Depends(get_db)
):
    """
    Delete a property definition.

    Removes the property definition from the system.
    """
    predicate = db.query(models.Predicate).filter_by(id=str(property_def_id)).first()  # noqa: E501
    if not predicate:
        raise HTTPException(status_code=404, detail="Property definition not found")

    try:
        db.delete(predicate)
        db.commit()
        return  # Return empty response with 204 status

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cannot delete property definition: it may be in use")  # noqa: E501
