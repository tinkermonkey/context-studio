"""Unit tests for ConfigChatSettings: chat settings are read from config.json on every call."""

import json

from adapters.chat.context import ConfigChatSettings
from config import ConfigurationManager


def test_reads_current_chat_section(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"chat": {"model": "anthropic/claude-opus-4-7"}}))
    manager = ConfigurationManager(config_file=str(config_file))
    settings = ConfigChatSettings(manager)

    assert settings.model() == "anthropic/claude-opus-4-7"
    assert settings.max_tool_rounds() == 8

    # A Settings save replaces the manager's settings; the next turn sees it
    manager.settings = manager.settings.model_copy(
        update={"chat": manager.settings.chat.model_copy(update={"max_tool_rounds": 3})}
    )
    assert settings.max_tool_rounds() == 3
