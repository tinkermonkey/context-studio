"""
Change Events API Endpoints

This module implements the change_events API endpoints for tracking database changes.

Endpoints:
- GET /api/change_events/ - List change events with filtering and pagination
- GET /api/change_events/{event_id} - Get a specific change event
- PUT /api/change_events/{event_id} - Update a change event (e.g., mark as processed)
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from sqlalchemy.orm import Session

from database.utils import get_db
from database.models import ChangeEvent
from api.models.change_events import ChangeEventOut, ChangeEventUpdate, RecordTypeEnum
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/change_events", tags=["change_events"])


def to_change_event_out(event: ChangeEvent) -> ChangeEventOut:
    """Convert database ChangeEvent to API ChangeEventOut model."""
    return ChangeEventOut(
        id=event.id,
        event_type=event.event_type,
        record_type=event.record_type.value if hasattr(event.record_type, 'value') else str(event.record_type),
        record_id=event.record_id,
        old_data=event.old_data,
        new_data=event.new_data,
        event_timestamp=event.timestamp.isoformat(),
        processed=event.processed
    )


@router.get("/", response_model=List[ChangeEventOut])
def list_change_events(
    skip: int = Query(0, ge=0, description="Number of events to skip"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of events to return"),
    record_type: Optional[RecordTypeEnum] = Query(None, description="Filter by record type"),
    record_id: Optional[str] = Query(None, description="Filter by record ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type (create, update, delete)"),
    processed: Optional[bool] = Query(None, description="Filter by processed status"),
    db: Session = Depends(get_db)
):
    """
    List change events with filtering and pagination.

    Events are returned in descending order by timestamp (newest first).
    """
    try:
        query = db.query(ChangeEvent)

        # Apply filters
        if record_type is not None:
            from database.enums import RecordType
            query = query.filter(ChangeEvent.record_type == RecordType(record_type.value))

        if record_id is not None:
            query = query.filter(ChangeEvent.record_id == record_id)

        if event_type is not None:
            query = query.filter(ChangeEvent.event_type == event_type)

        if processed is not None:
            query = query.filter(ChangeEvent.processed == processed)

        # Order by timestamp descending (newest first)
        query = query.order_by(ChangeEvent.timestamp.desc())

        # Apply pagination
        events = query.offset(skip).limit(limit).all()

        return [to_change_event_out(event) for event in events]

    except Exception as e:
        logger.error(f"Error listing change events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing change events: {str(e)}")


@router.get("/{event_id}", response_model=ChangeEventOut)
def get_change_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific change event by ID.
    """
    try:
        event = db.query(ChangeEvent).filter(ChangeEvent.id == event_id).first()

        if not event:
            raise HTTPException(status_code=404, detail=f"Change event {event_id} not found")

        return to_change_event_out(event)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting change event {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting change event: {str(e)}")


@router.put("/{event_id}", response_model=ChangeEventOut)
def update_change_event(
    event_id: int,
    update_data: ChangeEventUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a change event (e.g., mark as processed).
    """
    try:
        event = db.query(ChangeEvent).filter(ChangeEvent.id == event_id).first()

        if not event:
            raise HTTPException(status_code=404, detail=f"Change event {event_id} not found")

        # Update the processed field
        event.processed = update_data.processed
        db.commit()
        db.refresh(event)

        return to_change_event_out(event)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating change event {event_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating change event: {str(e)}")
