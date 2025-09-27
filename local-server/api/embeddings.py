"""
Embeddings API Endpoints

This module provides endpoints for managing embeddings for structure_nodes,
including WebSocket-based embedding regeneration with real-time progress updates.
"""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from services.embedding_regeneration_service import get_embedding_regeneration_service
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


@router.websocket("/regenerate")
async def websocket_regenerate_embeddings(
    websocket: WebSocket,
    force: bool = Query(False, description="Force regeneration even if embeddings exist")
):
    """
    WebSocket endpoint for regenerating structure_nodes embeddings with real-time progress.

    Query Parameters:
    - force: If true, regenerate all embeddings even if they already exist

    WebSocket Messages Sent:
    - {"type": "started", "message": "...", "start_time": "ISO timestamp"}
    - {"type": "progress", "progress": {...}} (see EmbeddingProgress.to_dict())
    - {"type": "completed", "message": "...", "total_processed": int, "duration_seconds": float}
    - {"type": "error", "message": "..."}

    Example usage:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/embeddings/regenerate?force=false');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
            console.log(`Progress: ${data.progress.completion_percentage}%`);
            console.log(`ETA: ${data.progress.estimated_remaining_seconds}s`);
        }
    };
    ```
    """
    await websocket.accept()

    try:
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "WebSocket connected for embedding regeneration",
            "force_regenerate": force
        }))

        # Get the embedding service
        service = get_embedding_regeneration_service()

        # Start the regeneration process
        await service.regenerate_all_embeddings(websocket, force_regenerate=force)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during embedding regeneration")
        # Attempt to stop the regeneration process
        service = get_embedding_regeneration_service()
        service.stop_regeneration()
    except Exception as e:
        logger.error(f"Error in embedding regeneration WebSocket: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Unexpected error: {str(e)}"
            }))
        except:
            # WebSocket might be closed already
            pass


@router.get("/status")
async def get_regeneration_status():
    """
    Get the current status of embedding regeneration.

    Returns:
    - is_running: Whether regeneration is currently in progress
    """
    service = get_embedding_regeneration_service()
    return {
        "is_running": service.is_running
    }


@router.post("/stop")
async def stop_regeneration():
    """
    Stop the current embedding regeneration process.

    Returns:
    - stopped: Whether a running process was stopped
    - message: Status message
    """
    service = get_embedding_regeneration_service()
    stopped = service.stop_regeneration()

    if stopped:
        return {
            "stopped": True,
            "message": "Embedding regeneration stop requested"
        }
    else:
        return {
            "stopped": False,
            "message": "No embedding regeneration process is currently running"
        }