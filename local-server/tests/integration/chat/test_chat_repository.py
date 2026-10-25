"""
Integration tests for SqliteConversationRepository against a real operations.db.
"""

from datetime import datetime, timedelta, timezone

from domain.chat.entities import ChatMessage, Conversation
from domain.chat.value_objects import (
    ChatRole,
    ContextBlock,
    EntityRef,
    PageContext,
    ReasoningBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)


def _conversation(conversation_id, updated_minutes_ago=0):
    updated = datetime.now(timezone.utc) - timedelta(minutes=updated_minutes_ago)
    return Conversation(id=conversation_id, title="t", model="m", updated_at=updated)


async def test_round_trips_every_block_type(dr_workspace):
    repository = dr_workspace.conversations
    await repository.save_conversation(_conversation("c1"))
    page = PageContext(route="/app/schema/classes/x", entity_kind="class", entity_id="x")
    user = ChatMessage(
        id="m0",
        conversation_id="c1",
        seq=0,
        role=ChatRole.USER,
        blocks=(ContextBlock("Workspace contents: ..."), TextBlock("Hi")),
        page_context=page,
    )
    assistant = ChatMessage(
        id="m1",
        conversation_id="c1",
        seq=1,
        role=ChatRole.ASSISTANT,
        blocks=(
            ReasoningBlock(provider="anthropic", data={"type": "thinking", "signature": "s"}),
            TextBlock("Looking"),
            ToolUseBlock(id="tu", name="search_entities", input={"query": "Op", "limit": 5}),
        ),
        tokens_in=12,
        tokens_out=3,
    )
    results = ChatMessage(
        id="m2",
        conversation_id="c1",
        seq=2,
        role=ChatRole.USER,
        blocks=(
            ToolResultBlock(
                tool_use_id="tu",
                content='{"results": []}',
                is_error=False,
                summary="Found 1",
                entities=(EntityRef("x", "class", "Operation"),),
            ),
        ),
    )
    for message in (assistant, user, results):  # stored order doesn't matter; seq does
        await repository.add_message(message)

    loaded = await repository.list_messages("c1")

    assert [m.id for m in loaded] == ["m0", "m1", "m2"]
    assert loaded[0].blocks == user.blocks and loaded[0].page_context == page
    assert loaded[1].blocks == assistant.blocks
    assert (loaded[1].tokens_in, loaded[1].tokens_out) == (12, 3)
    assert loaded[2].blocks == results.blocks
    assert loaded[1].role == ChatRole.ASSISTANT


async def test_save_updates_and_lists_latest_first(dr_workspace):
    repository = dr_workspace.conversations
    await repository.save_conversation(_conversation("old", updated_minutes_ago=10))
    await repository.save_conversation(_conversation("new", updated_minutes_ago=1))

    assert [c.id for c in await repository.list_conversations(10)] == ["new", "old"]

    touched = await repository.get_conversation("old")
    touched.title = "Renamed"
    touched.updated_at = datetime.now(timezone.utc)
    await repository.save_conversation(touched)

    listed = await repository.list_conversations(1)
    assert [(c.id, c.title) for c in listed] == [("old", "Renamed")]
    assert await repository.get_conversation("missing") is None


async def test_delete_cascades_to_messages(dr_workspace):
    repository = dr_workspace.conversations
    await repository.save_conversation(_conversation("c1"))
    await repository.add_message(
        ChatMessage(
            id="m0", conversation_id="c1", seq=0, role=ChatRole.USER, blocks=(TextBlock("x"),)
        )
    )

    assert await repository.delete_conversation("c1") is True
    assert await repository.delete_conversation("c1") is False
    assert await repository.list_messages("c1") == []
