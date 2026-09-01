import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from database.models import ChangeEvent
from sqlalchemy.orm import Session
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChangeRecord:
    """Represents a single change record for S3 storage."""

    change_id: str
    event_type: str  # create, update, delete
    record_type: str  # structure_node, structure_node_link, predicate
    record_id: str
    old_data: dict[str, Any] | None
    new_data: dict[str, Any] | None
    timestamp: str  # ISO timestamp
    batch_id: str
    author_id: str | None = None
    metadata: dict[str, Any] | None = None


class ChangeExtractor:
    """Extracts changes from SQLite and prepares for S3 sync."""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def extract_pending_changes(
        self, since: datetime | None = None
    ) -> list[ChangeRecord]:
        """Extract changes that need to be synchronized to S3."""

        query = self.db_session.query(ChangeEvent).filter(~ChangeEvent.processed)

        if since:
            query = query.filter(ChangeEvent.timestamp > since)

        query = query.order_by(ChangeEvent.timestamp)

        change_events = query.all()

        if not change_events:
            return []

        batch_id = str(uuid.uuid4())
        changes = []

        for event in change_events:
            change = ChangeRecord(
                change_id=str(event.id),
                event_type=str(event.event_type),
                record_type=str(
                    event.record_type
                ),  # RecordType enum requires explicit conversion to string
                record_id=str(event.record_id or ""),
                old_data=event.old_data,  # type: ignore
                new_data=event.new_data,  # type: ignore
                timestamp=event.timestamp.isoformat(),
                batch_id=batch_id,
            )
            changes.append(change)

        logger.info(f"Extracted {len(changes)} pending changes")
        return changes

    def create_change_dataframe(self, changes: list[ChangeRecord]) -> pd.DataFrame:
        """Convert change records to pandas DataFrame for Parquet serialization."""

        if not changes:
            return pd.DataFrame()

        # Convert to dictionaries
        change_dicts = [asdict(change) for change in changes]

        # Create DataFrame
        df = pd.DataFrame(change_dicts)

        # Optimize data types
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Convert complex objects to JSON strings for Parquet
        df["old_data"] = df["old_data"].apply(lambda x: json.dumps(x) if x else None)
        df["new_data"] = df["new_data"].apply(lambda x: json.dumps(x) if x else None)
        df["metadata"] = df["metadata"].apply(lambda x: json.dumps(x) if x else None)

        return df

    def mark_changes_processed(self, changes: list[ChangeRecord]):
        """Mark changes as processed in local database."""

        change_ids = [int(change.change_id) for change in changes]

        self.db_session.query(ChangeEvent).filter(
            ChangeEvent.id.in_(change_ids)
        ).update({ChangeEvent.processed: True}, synchronize_session=False)

        self.db_session.commit()
        logger.info(f"Marked {len(changes)} changes as processed")
