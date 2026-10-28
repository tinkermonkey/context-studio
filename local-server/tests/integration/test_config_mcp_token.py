"""
Integration tests for generating and saving the MCP bearer token (#1358):
ConfigurationManager.ensure_mcp_auth_token against a real config.json.
"""

import json
import shutil
from pathlib import Path

from config import ConfigurationManager

E2E_CONFIG = Path(__file__).resolve().parents[2] / "config.e2e.json"


def test_a_fresh_install_without_config_json_starts_and_saves_a_token(tmp_path):
    """config.json is no longer shipped: the first start writes defaults, then the token."""
    config_file = tmp_path / "config.json"

    manager = ConfigurationManager(config_file=str(config_file))
    token = manager.ensure_mcp_auth_token()

    saved = json.loads(config_file.read_text())
    assert saved["mcp"]["auth_token"] == token
    assert "cors_origins" not in saved["server"]
    assert manager.get_settings().server.cors_origins == ["http://localhost:3100"]


def test_the_e2e_config_pins_its_token_so_the_e2e_server_never_writes_it(tmp_path):
    config_file = tmp_path / "config.e2e.json"
    shutil.copy(E2E_CONFIG, config_file)
    before = config_file.read_text()

    token = ConfigurationManager(config_file=str(config_file)).ensure_mcp_auth_token()

    assert token == "e2e-test-token"
    assert config_file.read_text() == before


ORIGINAL = """{
  "server": {
    "host": "127.0.0.1",
    "port": 8000
  },
  "llm": {
    "openai_api_key": ""
  },
  "recognition": {
    "individual_match_threshold": 0.95
  }
}"""


def test_generates_a_token_and_saves_it_beside_the_other_keys(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(ORIGINAL)
    manager = ConfigurationManager(config_file=str(config_file))

    token = manager.ensure_mcp_auth_token()

    assert len(token) >= 43  # token_urlsafe(32)
    assert manager.get_settings().mcp.auth_token == token
    saved = json.loads(config_file.read_text())
    assert saved["mcp"] == {"auth_token": token}
    # The rest of the file is kept as written, not replaced by a dump of every default
    assert {k: v for k, v in saved.items() if k != "mcp"} == json.loads(ORIGINAL)
    assert config_file.read_text().startswith(ORIGINAL[: ORIGINAL.rindex("}")].rstrip())
    assert not config_file.read_text().endswith("\n")


def test_a_saved_token_is_reused_on_the_next_start(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(ORIGINAL)
    token = ConfigurationManager(config_file=str(config_file)).ensure_mcp_auth_token()

    restarted = ConfigurationManager(config_file=str(config_file))

    assert restarted.get_settings().mcp.auth_token == token
    assert restarted.ensure_mcp_auth_token() == token


def test_a_configured_token_is_left_alone(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcp": {"auth_token": "chosen-by-hand"}}))
    before = config_file.read_text()

    token = ConfigurationManager(config_file=str(config_file)).ensure_mcp_auth_token()

    assert token == "chosen-by-hand"
    assert config_file.read_text() == before


def test_each_workspace_gets_its_own_token(tmp_path):
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    first.write_text("{}")
    second.write_text("{}")

    token_a = ConfigurationManager(config_file=str(first)).ensure_mcp_auth_token()
    token_b = ConfigurationManager(config_file=str(second)).ensure_mcp_auth_token()

    assert token_a != token_b


def test_an_unreadable_config_is_not_overwritten(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text("{ not json")
    manager = ConfigurationManager(config_file=str(config_file))

    token = manager.ensure_mcp_auth_token()

    assert token
    assert manager.get_settings().mcp.auth_token == token
    assert config_file.read_text() == "{ not json"


def test_non_ascii_text_is_kept_as_written(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"chat": {"system_prompt": "caf\u00e9"}}', encoding="utf-8")

    ConfigurationManager(config_file=str(config_file)).ensure_mcp_auth_token()

    assert '"caf\u00e9"' in config_file.read_text(encoding="utf-8")


def test_a_config_that_is_not_an_object_is_not_overwritten(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text("[]")
    manager = ConfigurationManager(config_file=str(config_file))

    assert manager.ensure_mcp_auth_token()
    assert config_file.read_text() == "[]"
