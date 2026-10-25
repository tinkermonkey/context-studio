"""
Chat API routes.

Endpoints:
- GET    /api/chat/status                               - Configured model and availability
- POST   /api/chat/conversations                        - Start a conversation
- GET    /api/chat/conversations                        - Conversations, latest first
- GET    /api/chat/conversations/{id}                   - A conversation with its messages
- DELETE /api/chat/conversations/{id}                   - Delete a conversation
- POST   /api/chat/conversations/{id}/messages          - Send a message; SSE stream of the turn

The message stream is Server-Sent Events. Each event's `event:` name equals the
`type` field of its JSON `data` (see ChatStreamEvent): message_start, then any
text_delta / tool_start / tool_end, then exactly one message_end or error.
"""

from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from adapters.web.dependencies import get_chat_service
from adapters.web.schemas.chat import (
    ChatMessageResponse,
    ChatStatusResponse,
    ChatStreamEvent,
    ConversationDetailResponse,
    ConversationResponse,
    ErrorEvent,
    MessageStartEvent,
    SendMessageRequest,
    stream_event_from_domain,
)
from domain.chat.entities import Conversation
from domain.chat.exceptions import ConversationNotFoundError
from domain.chat.services import ChatService
from utils.logger import get_logger

router = APIRouter(prefix="/api/chat", tags=["chat"])

_logger = get_logger(__name__)


async def get_existing_conversation(
    conversation_id: str, service: ChatService = Depends(get_chat_service)
) -> Conversation:
    """Resolve the path's conversation, or 404 before any response starts."""
    try:
        return await service.get_conversation(conversation_id)
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/status", response_model=ChatStatusResponse)
async def get_status(service: ChatService = Depends(get_chat_service)) -> ChatStatusResponse:
    """Report the configured chat model and whether a configured provider serves it."""
    return ChatStatusResponse.from_domain(service.status())


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    service: ChatService = Depends(get_chat_service),
) -> ConversationResponse:
    """Start an empty conversation."""
    return ConversationResponse.from_domain(await service.create_conversation())


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    service: ChatService = Depends(get_chat_service),
) -> list[ConversationResponse]:
    """List conversations, most recently updated first (the first is the one to resume)."""
    conversations = await service.list_conversations(limit=limit)
    return [ConversationResponse.from_domain(c) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation: Conversation = Depends(get_existing_conversation),
    service: ChatService = Depends(get_chat_service),
) -> ConversationDetailResponse:
    """Return a conversation with its messages, for resuming it."""
    messages = await service.list_messages(conversation.id)
    return ConversationDetailResponse(
        **ConversationResponse.from_domain(conversation).model_dump(),
        messages=[ChatMessageResponse.from_domain(m) for m in messages],
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation: Conversation = Depends(get_existing_conversation),
    service: ChatService = Depends(get_chat_service),
) -> None:
    """Delete a conversation and its messages."""
    try:
        await service.delete_conversation(conversation.id)
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/conversations/{conversation_id}/messages",
    response_class=EventSourceResponse,
    responses={404: {"description": "Conversation not found"}},
)
async def send_message(
    request: SendMessageRequest,
    conversation: Conversation = Depends(get_existing_conversation),
    service: ChatService = Depends(get_chat_service),
) -> AsyncIterable[ChatStreamEvent]:
    """
    Send a user message and stream the assistant's turn as Server-Sent Events.

    Answers cite entities as `[Title](entity:<kind>/<id>)`. A link is valid when
    its id appeared in a `tool_end` event's `entities` (or in the conversation's
    stored tool results) or is the entity in a message's `page_context`.
    """
    yield _sse(MessageStartEvent(conversation_id=conversation.id))
    page_context = request.page_context.to_domain() if request.page_context else None
    try:
        async for event in service.send(conversation.id, request.text, page_context):
            yield _sse(stream_event_from_domain(event))
    except ConversationNotFoundError:
        yield _sse(ErrorEvent(message="This conversation was deleted."))
    except Exception:  # noqa: BLE001 - the stream must always end with an event
        _logger.exception("Chat turn failed")
        yield _sse(ErrorEvent(message="The chat turn failed unexpectedly."))


def _sse(payload) -> ServerSentEvent:
    return ServerSentEvent(event=payload.type, data=payload)
