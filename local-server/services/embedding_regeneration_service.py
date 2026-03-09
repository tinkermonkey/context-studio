# mypy: ignore-errors
"""
Service for regenerating embeddings for structure_nodes with WebSocket progress updates.
"""

import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import WebSocket

from database.utils import get_db
from embeddings.generate_embeddings import generate_embedding
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EmbeddingProgress:
    """Progress tracking for embedding regeneration."""

    total_nodes: int
    completed_nodes: int
    current_node_title: str
    current_node_type: str
    start_time: datetime
    current_time: datetime
    estimated_remaining_seconds: float
    processing_rate_per_second: float
    error_count: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_nodes == 0:
            return 100.0
        return (self.completed_nodes / self.total_nodes) * 100.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_nodes": self.total_nodes,
            "completed_nodes": self.completed_nodes,
            "current_node_title": self.current_node_title,
            "current_node_type": self.current_node_type,
            "completion_percentage": self.completion_percentage,
            "start_time": self.start_time.isoformat(),
            "current_time": self.current_time.isoformat(),
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "processing_rate_per_second": self.processing_rate_per_second,
            "error_count": self.error_count,
            "errors": self.errors[-5:] if self.errors else [],  # Last 5 errors
        }


class EmbeddingRegenerationService:
    """Service to regenerate embeddings for structure_nodes with progress tracking."""

    def __init__(self):
        self.is_running = False
        self._current_session: Optional[Session] = None

    async def regenerate_all_embeddings(
        self, websocket: WebSocket, force_regenerate: bool = False
    ) -> None:
        """
        Regenerate embeddings for all structure_nodes with WebSocket progress updates.

        Args:
            websocket: WebSocket connection for progress updates
            force_regenerate: If True, regenerate embeddings even if they already exist
        """
        if self.is_running:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Embedding regeneration is already running",
                    }
                )
            )
            return

        self.is_running = True
        start_time = datetime.now()

        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "started",
                        "message": "Starting embedding regeneration...",
                        "start_time": start_time.isoformat(),
                    }
                )
            )

            # Get database session
            db = next(get_db())
            self._current_session = db

            # Get nodes that need embedding regeneration
            nodes = self._get_nodes_for_regeneration(db, force_regenerate)
            total_nodes = len(nodes)

            if total_nodes == 0:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "completed",
                            "message": "No nodes need embedding regeneration",
                            "total_processed": 0,
                        }
                    )
                )
                return

            logger.info(
                f"Starting embedding regeneration for {total_nodes} structure_nodes"
            )

            # Process nodes with progress updates
            await self._process_nodes_with_progress(db, nodes, websocket, start_time)

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "completed",
                        "message": f"Successfully regenerated embeddings for {total_nodes} structure_nodes",
                        "total_processed": total_nodes,
                        "duration_seconds": (
                            datetime.now() - start_time
                        ).total_seconds(),
                    }
                )
            )

        except Exception as e:
            logger.error(f"Error during embedding regeneration: {e}")
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Embedding regeneration failed: {str(e)}",
                    }
                )
            )
        finally:
            self.is_running = False
            if self._current_session:
                self._current_session.close()
                self._current_session = None

    def _get_nodes_for_regeneration(
        self, db: Session, force_regenerate: bool = False
    ) -> List[Dict]:
        """Get structure_nodes that need embedding regeneration."""
        if force_regenerate:
            # Regenerate all nodes
            query = text("""
                SELECT id, node_type, title, definition
                FROM structure_nodes
                ORDER BY node_type, title
            """)
        else:
            # Only regenerate nodes missing embeddings
            query = text("""
                SELECT id, node_type, title, definition
                FROM structure_nodes
                WHERE title_embedding IS NULL
                   OR definition_embedding IS NULL
                   OR (definition IS NOT NULL AND definition_embedding IS NULL)
                ORDER BY node_type, title
            """)

        result = db.execute(query)
        return [
            {"id": row[0], "node_type": row[1], "title": row[2], "definition": row[3]}
            for row in result.fetchall()
        ]

    async def _process_nodes_with_progress(
        self, db: Session, nodes: List[Dict], websocket: WebSocket, start_time: datetime
    ) -> None:
        """Process nodes with regular progress updates."""
        total_nodes = len(nodes)
        completed_nodes = 0
        error_count = 0
        errors = []

        for i, node in enumerate(nodes):
            current_time = datetime.now()

            # Calculate timing metrics
            elapsed_seconds = (current_time - start_time).total_seconds()
            if elapsed_seconds > 0:
                processing_rate = completed_nodes / elapsed_seconds
                if processing_rate > 0:
                    remaining_nodes = total_nodes - completed_nodes
                    estimated_remaining_seconds = remaining_nodes / processing_rate
                else:
                    estimated_remaining_seconds = 0.0
            else:
                processing_rate = 0.0
                estimated_remaining_seconds = 0.0

            # Create progress object
            progress = EmbeddingProgress(
                total_nodes=total_nodes,
                completed_nodes=completed_nodes,
                current_node_title=node["title"],
                current_node_type=node["node_type"],
                start_time=start_time,
                current_time=current_time,
                estimated_remaining_seconds=estimated_remaining_seconds,
                processing_rate_per_second=processing_rate,
                error_count=error_count,
                errors=errors,
            )

            # Send progress update
            await websocket.send_text(
                json.dumps({"type": "progress", "progress": progress.to_dict()})
            )

            # Process the node
            try:
                await self._regenerate_node_embeddings(db, node)
                completed_nodes += 1
            except Exception as e:
                error_count += 1
                error_msg = f"Error processing {node['title']}: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)

            # Small delay to prevent overwhelming the WebSocket
            await asyncio.sleep(0.01)

    async def _regenerate_node_embeddings(self, db: Session, node: Dict) -> None:
        """Regenerate embeddings for a single node."""
        node_id = node["id"]
        title = node["title"]
        definition = node["definition"]

        # Generate embeddings
        title_embedding = None
        definition_embedding = None

        if title:
            title_embedding = generate_embedding(title)

        if definition:
            definition_embedding = generate_embedding(definition)

        # Update the database
        update_query = text("""
            UPDATE structure_nodes
            SET title_embedding = :title_embedding,
                definition_embedding = :definition_embedding,
                last_modified = CURRENT_TIMESTAMP
            WHERE id = :node_id
        """)

        db.execute(
            update_query,
            {
                "title_embedding": title_embedding,
                "definition_embedding": definition_embedding,
                "node_id": node_id,
            },
        )
        db.commit()

        logger.debug(f"Updated embeddings for {node['node_type']}: {title}")

    def stop_regeneration(self) -> bool:
        """Stop the current regeneration process."""
        if self.is_running:
            self.is_running = False
            logger.info("Embedding regeneration stop requested")
            return True
        return False


# Global service instance
_embedding_service = None


def get_embedding_regeneration_service() -> EmbeddingRegenerationService:
    """Get the global embedding regeneration service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingRegenerationService()
    return _embedding_service
