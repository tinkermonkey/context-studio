"""A fake LLMProvider for the notes-to-claims pipeline: scripted splits per note."""

import json
from typing import Any

from domain.pipelines.ports import LLMResponse


class FakeNoteSplitter:
    """
    Replies to a split prompt by the first scripted fragment found in its note
    (the text between the prompt's triple quotes), and records every call.

    A reply is a list of claim dicts (sent as {"claims": [...]}), a raw string,
    or an exception to raise.
    """

    def __init__(self, replies: dict[str, Any], tokens_in: int = 100, tokens_out: int = 50):
        self.replies = replies
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.calls: list[dict[str, Any]] = []

    def complete(self, system_prompt: str, user_prompt: str, model: str, **kwargs) -> LLMResponse:
        self.calls.append({"system": system_prompt, "user": user_prompt, "model": model, **kwargs})
        note = user_prompt.split('"""')[1]
        for fragment, reply in self.replies.items():
            if fragment in note:
                if isinstance(reply, Exception):
                    raise reply
                content = reply if isinstance(reply, str) else json.dumps({"claims": reply})
                return LLMResponse(content, self.tokens_in, self.tokens_out, 12.5, "stop", model)
        raise AssertionError(f"no scripted split for {note!r}")

    async def complete_async(
        self, system_prompt: str, user_prompt: str, model: str, **kwargs
    ) -> LLMResponse:
        return self.complete(system_prompt, user_prompt, model, **kwargs)

    def is_model_available(self, model: str) -> bool:
        return True

    def list_available_models(self) -> list[str]:
        return []
