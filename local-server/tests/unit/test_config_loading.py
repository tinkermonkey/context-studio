"""Unit tests for loading config.json: one invalid value never discards the rest of the file."""

import json
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from config import LLM_KEY_ENV_FALLBACKS, ConfigurationManager

KEY_FIELDS = list(LLM_KEY_ENV_FALLBACKS)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """No .env file and none of the key variables, so only the file's content counts."""
    monkeypatch.setattr("config.load_dotenv", lambda *args, **kwargs: None)
    for env_var in LLM_KEY_ENV_FALLBACKS.values():
        monkeypatch.delenv(env_var, raising=False)


def load(tmp_path, content) -> ConfigurationManager:
    """Write content as config.json and load it."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(content))
    return ConfigurationManager(config_file=str(config_file))


class TestLLMKeys:
    """null, "" and a missing key all mean "not set", and the environment fallback applies."""

    @pytest.mark.parametrize("field", KEY_FIELDS)
    @pytest.mark.parametrize("llm_section", ["null", "empty", "missing"])
    def test_unset_key_loads_as_empty(self, tmp_path, field, llm_section):
        llm = {"null": {field: None}, "empty": {field: ""}, "missing": {}}[llm_section]

        settings = load(tmp_path, {"llm": llm}).get_settings()

        assert getattr(settings.llm, field) == ""

    @pytest.mark.parametrize("field", KEY_FIELDS)
    @pytest.mark.parametrize("llm_section", ["null", "empty", "missing"])
    def test_unset_key_takes_the_environment_variable(
        self, tmp_path, monkeypatch, field, llm_section
    ):
        monkeypatch.setenv(LLM_KEY_ENV_FALLBACKS[field], "from-env")
        llm = {"null": {field: None}, "empty": {field: ""}, "missing": {}}[llm_section]

        settings = load(tmp_path, {"llm": llm}).get_settings()

        assert getattr(settings.llm, field) == "from-env"

    @pytest.mark.parametrize("field", KEY_FIELDS)
    def test_a_key_in_the_file_is_kept(self, tmp_path, field):
        settings = load(tmp_path, {"llm": {field: "from-file"}}).get_settings()

        assert getattr(settings.llm, field) == "from-file"

    @pytest.mark.parametrize("field", KEY_FIELDS)
    def test_null_key_warns_naming_the_field_and_keeps_the_rest_of_the_file(
        self, tmp_path, caplog, field
    ):
        content = {"server": {"port": 9123}, "llm": {field: None}}

        with caplog.at_level(logging.WARNING, logger="config"):
            settings = load(tmp_path, content).get_settings()

        assert any(
            record.levelno == logging.WARNING and f"llm.{field}" in record.getMessage()
            for record in caplog.records
        )
        assert settings.server.port == 9123

    def test_the_warning_is_logged_once_even_when_other_values_are_invalid(self, tmp_path, caplog):
        content = {
            "llm": {"openai_api_key": None},
            "server": {"port": 80},
            "chat": {"max_tool_rounds": 0},
        }

        with caplog.at_level(logging.WARNING, logger="config"):
            load(tmp_path, content)

        warnings = [r for r in caplog.records if "llm.openai_api_key" in r.getMessage()]
        assert len(warnings) == 1

    def test_a_key_that_is_not_a_string_is_not_set(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger="config"):
            settings = load(tmp_path, {"llm": {"openai_api_key": 12345}}).get_settings()

        assert settings.llm.openai_api_key == ""
        assert "llm.openai_api_key" in caplog.text


class TestInvalidValues:
    """An invalid value is named in the log and takes its default; the rest loads."""

    def test_an_out_of_range_value_takes_its_default_and_other_fields_stay(self, tmp_path, caplog):
        content = {
            "server": {"port": 9123},
            "chat": {"max_tool_rounds": 999, "model": "claude-opus-5-5"},
            "database": {"local_db_path": "/data/mine.db"},
        }

        with caplog.at_level(logging.ERROR, logger="config"):
            settings = load(tmp_path, content).get_settings()

        assert settings.chat.max_tool_rounds == 8
        assert settings.chat.model == "claude-opus-5-5"
        assert settings.server.port == 9123
        assert settings.database.local_db_path == "/data/mine.db"
        assert "chat.max_tool_rounds" in caplog.text

    def test_a_value_inside_a_list_sets_the_whole_list_aside(self, tmp_path, caplog):
        content = {"sources": {"allowed_roots": ["/ok", "relative/path"], "max_bytes": 1000}}

        with caplog.at_level(logging.ERROR, logger="config"):
            settings = load(tmp_path, content).get_settings()

        assert settings.sources.allowed_roots == []
        assert settings.sources.max_bytes == 1000
        assert "sources.allowed_roots" in caplog.text

    def test_a_section_that_fails_as_a_whole_is_set_aside(self, tmp_path, caplog):
        content = {"sync": {"adapter": "s3"}, "server": {"port": 9123}}

        with caplog.at_level(logging.ERROR, logger="config"):
            settings = load(tmp_path, content).get_settings()

        assert settings.sync is None
        assert settings.server.port == 9123
        assert "sync" in caplog.text

    def test_a_missing_required_key_sets_the_object_that_lacks_it_aside(self, tmp_path, caplog):
        content = {
            "decision_models": {
                "models": {
                    "broken": {"model": "m"},
                    "fine": {"adapter": "llm", "model": "m"},
                }
            }
        }

        with caplog.at_level(logging.ERROR, logger="config"):
            settings = load(tmp_path, content).get_settings()

        assert list(settings.decision_models.models) == ["fine"]
        assert "decision_models.models.broken.adapter is missing" in caplog.text

    def test_several_invalid_values_are_all_named(self, tmp_path, caplog):
        content = {"server": {"port": 80}, "chat": {"max_tool_rounds": 0}, "llm": {}}

        with caplog.at_level(logging.ERROR, logger="config"):
            settings = load(tmp_path, content).get_settings()

        assert settings.server.port == 8000
        assert settings.chat.max_tool_rounds == 8
        assert "server.port" in caplog.text
        assert "chat.max_tool_rounds" in caplog.text

    def test_the_log_does_not_echo_a_credential_given_as_an_invalid_value(self, tmp_path, caplog):
        content = {"server": {"port": "sk-secret-credential-value"}}

        with caplog.at_level(logging.ERROR, logger="config"):
            load(tmp_path, content)

        assert "server.port" in caplog.text
        assert "sk-secret-credential-value" not in caplog.text

    def test_a_file_that_is_not_json_still_loads_the_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("{not json")

        settings = ConfigurationManager(config_file=str(config_file)).get_settings()

        assert settings.server.port == 8000
