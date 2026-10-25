"""
ChatService: the read-only assistant's agent loop.

One user turn runs model -> tools -> model until the model answers without
calling tools or the turn uses up `max_tool_rounds`. Every message is stored as
it completes and the system prompt and tool list never change, so the history
sent to the model is append-only: earlier requests are never edited, which
models that replay reasoning blocks require.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional, Sequence
from uuid import uuid4

from domain.chat.entities import ChatMessage, Conversation
from domain.chat.exceptions import ConversationNotFoundError
from domain.chat.ports import (
    ChatModel,
    ChatSettings,
    ChatTool,
    ConversationRepository,
    WorkspaceContext,
)
from domain.chat.value_objects import (
    ChatEvent,
    ChatFailed,
    ChatRole,
    ChatStatus,
    ContentBlock,
    ContextBlock,
    ModelTurnEnded,
    PageContext,
    StopReason,
    TextBlock,
    TextDelta,
    ToolFinished,
    ToolOutcome,
    ToolResultBlock,
    ToolStarted,
    ToolUseBlock,
    TurnCompleted,
)

logger = logging.getLogger(__name__)

NEW_CONVERSATION_TITLE = "New chat"
_TITLE_LENGTH = 60

SYSTEM_PROMPT = """\
You are the Context Studio assistant. You answer questions about the user's \
knowledge graph workspace: taxonomies, concept schemes and classes (the schema), \
individuals (the data), and the typed relationships between them.

Use the tools to look up workspace contents, even when you feel confident; do \
not answer from general knowledge about what the workspace holds. You are \
read-only: you cannot create, change or delete anything. If the user asks for a \
change, say you can't make edits and describe what they could change themselves.

Links: every time you mention a workspace entity, write it as a Markdown link \
[Title](entity:<kind>/<id>), with the kind and id exactly as a tool returned \
them. The kinds are taxonomy, scheme, class, individual and property. Only link \
entities whose id came from a tool result, or from a note about the page the user \
is viewing, in this conversation; never guess or construct an id. To mention an \
entity you have not looked up, look it up first. For example: the \
[Operation](entity:class/6f1c2a9e-...) class.

Keep answers short and concrete. Use a list when you name several entities.\
"""

LIMIT_NOTE = (
    "Tool-call limit for this message reached. Answer now with what you have found,"
    " without calling more tools, and say what you could not check."
)

_NOT_RUN_LIMIT = "Not run: the tool-call limit for this message was reached."
_NOT_RUN_CUT_OFF = "Not run: the response was cut off before the tool call finished."


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChatService:
    """Runs conversations with the read-only, tool-calling assistant."""

    def __init__(
        self,
        model: ChatModel,
        tools: Sequence[ChatTool],
        repository: ConversationRepository,
        settings: ChatSettings,
        workspace: WorkspaceContext,
        max_tokens: int = 16000,
    ) -> None:
        """
        Initialize the service.

        Args:
            model: Streaming tool-calling chat model
            tools: Read-only tools offered to the model on every request
            repository: Conversation storage
            settings: Chat configuration, read on every turn
            workspace: Describes the workspace and the viewed page to the model
            max_tokens: Output token limit per model request
        """
        self._model = model
        self._tools = {tool.spec.name: tool for tool in tools}
        self._tool_specs = [tool.spec for tool in tools]
        self._repository = repository
        self._settings = settings
        self._workspace = workspace
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def status(self) -> ChatStatus:
        """Report the configured model and whether a provider can serve it."""
        model = self._settings.model()
        return ChatStatus(
            model=model,
            available=self._model.supports_model(model),
            max_tool_rounds=self._settings.max_tool_rounds(),
        )

    async def create_conversation(self) -> Conversation:
        """Start an empty conversation."""
        conversation = Conversation(
            id=str(uuid4()), title=NEW_CONVERSATION_TITLE, model=self._settings.model()
        )
        await self._repository.save_conversation(conversation)
        return conversation

    async def get_conversation(self, conversation_id: str) -> Conversation:
        """
        Return a conversation.

        Raises:
            ConversationNotFoundError: If it does not exist
        """
        conversation = await self._repository.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    async def list_conversations(self, limit: int = 20) -> list[Conversation]:
        """Return conversations, most recently updated first."""
        return await self._repository.list_conversations(limit)

    async def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        """
        Return a conversation's messages in order.

        Raises:
            ConversationNotFoundError: If the conversation does not exist
        """
        await self.get_conversation(conversation_id)
        return await self._repository.list_messages(conversation_id)

    async def delete_conversation(self, conversation_id: str) -> None:
        """
        Delete a conversation and its messages.

        Raises:
            ConversationNotFoundError: If it does not exist
        """
        if not await self._repository.delete_conversation(conversation_id):
            raise ConversationNotFoundError(conversation_id)

    # ------------------------------------------------------------------
    # The agent loop
    # ------------------------------------------------------------------

    async def send(
        self,
        conversation_id: str,
        text: str,
        page_context: Optional[PageContext] = None,
    ) -> AsyncIterator[ChatEvent]:
        """
        Answer a user message, streaming events as the turn runs.

        Yields TextDelta, ToolStarted and ToolFinished while the turn runs, then
        exactly one TurnCompleted or ChatFailed. Failures are yielded, not
        raised, except a missing conversation, which is raised on the first
        iteration, before anything is yielded.

        Raises:
            ConversationNotFoundError: If the conversation does not exist
        """
        conversation = await self.get_conversation(conversation_id)
        history = await self._repository.list_messages(conversation_id)
        model = self._settings.model()
        max_rounds = self._settings.max_tool_rounds()

        context = await self._context_blocks(first_message=not history, page=page_context)
        await self._append(
            conversation,
            history,
            ChatRole.USER,
            (*context, TextBlock(text)),
            page_context=page_context,
        )
        if conversation.title == NEW_CONVERSATION_TITLE:
            conversation.title = _title_from(text)
        conversation.model = model
        await self._touch(conversation)

        tokens_in = tokens_out = 0
        for round_index in range(max_rounds + 1):
            ended: Optional[ModelTurnEnded] = None
            try:
                async for event in self._model.stream_chat(
                    system=SYSTEM_PROMPT,
                    messages=history,
                    tools=self._tool_specs,
                    model=model,
                    max_tokens=self._max_tokens,
                ):
                    if isinstance(event, TextDelta):
                        yield event
                    elif isinstance(event, ModelTurnEnded):
                        ended = event
            except Exception as e:  # noqa: BLE001 - any model failure ends the turn
                logger.warning("Chat model request failed: %s: %s", type(e).__name__, e)
                yield ChatFailed(message=_failure_message(e))
                return
            if ended is None:
                yield ChatFailed(message="The model stream ended before the answer finished.")
                return

            tokens_in += ended.tokens_in
            tokens_out += ended.tokens_out
            await self._append(
                conversation,
                history,
                ChatRole.ASSISTANT,
                ended.blocks,
                tokens_in=ended.tokens_in,
                tokens_out=ended.tokens_out,
            )
            await self._touch(conversation)

            tool_uses = [b for b in ended.blocks if isinstance(b, ToolUseBlock)]
            if not tool_uses:
                yield TurnCompleted(ended.stop_reason, tokens_in, tokens_out)
                return

            # Every tool call must be answered before the next request, even one
            # that won't run, or the stored history becomes invalid.
            if ended.stop_reason != StopReason.TOOL_USE:
                # Cut off (max_tokens, refusal) mid tool call: the input may be partial.
                await self._append(
                    conversation, history, ChatRole.USER, _unrun(tool_uses, _NOT_RUN_CUT_OFF)
                )
                yield TurnCompleted(ended.stop_reason, tokens_in, tokens_out)
                return
            if round_index == max_rounds:
                await self._append(
                    conversation, history, ChatRole.USER, _unrun(tool_uses, _NOT_RUN_LIMIT)
                )
                yield ChatFailed(
                    message=(
                        f"The assistant used all {max_rounds} tool rounds for this message"
                        " without finishing its answer. Try a narrower question."
                    )
                )
                return

            results: list[ContentBlock] = []
            for tool_use in tool_uses:
                yield ToolStarted(tool_use.id, tool_use.name, tool_use.input)
                outcome = await self._run_tool(tool_use)
                yield ToolFinished(
                    tool_use.id, tool_use.name, outcome.summary, outcome.entities, outcome.is_error
                )
                results.append(
                    ToolResultBlock(
                        tool_use_id=tool_use.id,
                        content=outcome.content,
                        is_error=outcome.is_error,
                        summary=outcome.summary,
                        entities=outcome.entities,
                    )
                )
            if round_index == max_rounds - 1:
                results.append(ContextBlock(LIMIT_NOTE))
            await self._append(conversation, history, ChatRole.USER, tuple(results))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _context_blocks(
        self, first_message: bool, page: Optional[PageContext]
    ) -> tuple[ContextBlock, ...]:
        blocks: list[ContextBlock] = []
        if first_message:
            blocks.append(ContextBlock(await self._workspace.summarize()))
        if page is not None:
            description = await self._workspace.describe_page(page)
            if description:
                blocks.append(ContextBlock(description))
        return tuple(blocks)

    async def _append(
        self,
        conversation: Conversation,
        history: list[ChatMessage],
        role: ChatRole,
        blocks: tuple[ContentBlock, ...],
        page_context: Optional[PageContext] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        message = ChatMessage(
            id=str(uuid4()),
            conversation_id=conversation.id,
            seq=len(history),
            role=role,
            blocks=blocks,
            page_context=page_context,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        await self._repository.add_message(message)
        history.append(message)

    async def _touch(self, conversation: Conversation) -> None:
        conversation.updated_at = _now()
        await self._repository.save_conversation(conversation)

    async def _run_tool(self, tool_use: ToolUseBlock) -> ToolOutcome:
        tool = self._tools.get(tool_use.name)
        if tool is None:
            known = ", ".join(sorted(self._tools))
            return ToolOutcome(
                content=json.dumps({"error": f"Unknown tool {tool_use.name!r}. Tools: {known}"}),
                summary=f"Unknown tool {tool_use.name}",
                is_error=True,
            )
        try:
            return await tool.execute(tool_use.input)
        except Exception as e:  # noqa: BLE001 - a tool bug must not end the turn
            logger.exception("Chat tool %s failed", tool_use.name)
            return ToolOutcome(
                content=json.dumps({"error": f"{type(e).__name__}: {e}"}),
                summary=f"{tool_use.name} failed",
                is_error=True,
            )


def _unrun(tool_uses: list[ToolUseBlock], reason: str) -> tuple[ContentBlock, ...]:
    return tuple(
        ToolResultBlock(
            tool_use_id=t.id,
            content=json.dumps({"error": reason}),
            is_error=True,
            summary="Not run",
        )
        for t in tool_uses
    )


def _title_from(text: str) -> str:
    title = " ".join(text.split())
    if not title:
        return NEW_CONVERSATION_TITLE
    if len(title) <= _TITLE_LENGTH:
        return title
    return title[: _TITLE_LENGTH - 1].rstrip() + "…"


def _failure_message(error: Exception) -> str:
    status = getattr(error, "status_code", None)
    if status in (401, 403):
        return "The chat model provider rejected its API key. Check the API keys in Settings."
    if status == 429:
        return "The chat model provider is rate limiting requests. Try again shortly."
    if isinstance(error, ValueError):
        return str(error)
    return f"The chat model request failed ({type(error).__name__})."
