"""Unit tests for cassette LLM providers.

Tests for CassetteLLMProvider and RecordingLLMProvider covering:
- Hash computation correctness
- Cassette recording and replay
- Stale cassette error handling
- File I/O error handling
"""

import json
import tempfile
from pathlib import Path

import pytest

from domain.pipelines.ports import LLMResponse
from tests.integration.pipelines._harness.cassettes import (
    CassetteLLMProvider,
    CassetteStaleError,
    RecordingLLMProvider,
    _compute_prompt_hash,
)


class TestComputePromptHash:
    """Tests for stable prompt hash computation."""

    def test_identical_prompts_same_hash(self):
        """Same inputs produce same hash."""
        hash1 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        hash2 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        assert hash1 == hash2

    def test_different_system_prompt_different_hash(self):
        """Different system prompts produce different hashes."""
        hash1 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        hash2 = _compute_prompt_hash(
            system_prompt="You are evil",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        assert hash1 != hash2

    def test_different_user_prompt_different_hash(self):
        """Different user prompts produce different hashes."""
        hash1 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        hash2 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 3+3?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        assert hash1 != hash2

    def test_different_model_different_hash(self):
        """Different models produce different hashes."""
        hash1 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        hash2 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="gpt-4",
            temperature=0.5,
            seed=42,
        )
        assert hash1 != hash2

    def test_different_temperature_different_hash(self):
        """Different temperatures produce different hashes."""
        hash1 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        hash2 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=1.0,
            seed=42,
        )
        assert hash1 != hash2

    def test_different_seed_different_hash(self):
        """Different seeds produce different hashes."""
        hash1 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        hash2 = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=43,
        )
        assert hash1 != hash2

    def test_none_seed_different_from_int_seed(self):
        """None seed is different from any int seed."""
        hash_none = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=None,
        )
        hash_int = _compute_prompt_hash(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="claude-3",
            temperature=0.5,
            seed=42,
        )
        assert hash_none != hash_int

    def test_hash_is_valid_hex_string(self):
        """Hash is a valid hex string (SHA256)."""
        hash_val = _compute_prompt_hash(
            system_prompt="test",
            user_prompt="test",
            model="test",
            temperature=0.0,
            seed=None,
        )
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
        assert all(c in "0123456789abcdef" for c in hash_val)


class FakeLLMProvider:
    """Fake LLM provider for testing RecordingLLMProvider."""

    def __init__(self, responses: dict[str, LLMResponse] | None = None):
        self.responses = responses or {}
        self.call_count = 0

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: str | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        self.call_count += 1
        key = _compute_prompt_hash(system_prompt, user_prompt, model, temperature, seed)
        if key in self.responses:
            return self.responses[key]
        return LLMResponse(
            content="default response",
            tokens_in=10,
            tokens_out=10,
            duration_ms=100.0,
            finish_reason="stop",
            model=model,
        )

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: str | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        return self.complete(
            system_prompt, user_prompt, model, temperature, max_tokens, response_format, timeout, seed
        )

    def is_model_available(self, model: str) -> bool:
        return True

    def list_available_models(self) -> list[str]:
        return ["test-model"]


class TestRecordingLLMProvider:
    """Tests for recording LLM provider."""

    def test_records_single_completion(self):
        """Recording provider captures a single completion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            delegate = FakeLLMProvider()
            recorder = RecordingLLMProvider(delegate, cassette_path)

            response = recorder.complete(
                system_prompt="sys",
                user_prompt="user",
                model="test",
                temperature=0.5,
                seed=42,
            )

            assert response.content == "default response"
            assert response.tokens_in == 10

            # Check that it was recorded
            assert len(recorder._recordings) == 1

    def test_records_multiple_completions(self):
        """Recording provider captures multiple completions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            delegate = FakeLLMProvider()
            recorder = RecordingLLMProvider(delegate, cassette_path)

            for i in range(3):
                recorder.complete(
                    system_prompt=f"sys{i}",
                    user_prompt=f"user{i}",
                    model="test",
                    temperature=0.5,
                    seed=42,
                )

            assert len(recorder._recordings) == 3

    def test_same_prompt_uses_same_key(self):
        """Same prompt hashes to same cassette key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            delegate = FakeLLMProvider()
            recorder = RecordingLLMProvider(delegate, cassette_path)

            # Make same request twice
            recorder.complete(
                system_prompt="sys",
                user_prompt="user",
                model="test",
                temperature=0.5,
                seed=42,
            )
            recorder.complete(
                system_prompt="sys",
                user_prompt="user",
                model="test",
                temperature=0.5,
                seed=42,
            )

            # Should have only one recording (second overwrites first)
            assert len(recorder._recordings) == 1

    def test_flush_writes_json_file(self):
        """Flush writes recordings to JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            delegate = FakeLLMProvider()
            recorder = RecordingLLMProvider(delegate, cassette_path)

            recorder.complete(
                system_prompt="sys",
                user_prompt="user",
                model="test",
                temperature=0.5,
                seed=42,
            )
            recorder.flush()

            assert cassette_path.exists()
            with open(cassette_path) as f:
                data = json.load(f)
            assert isinstance(data, dict)
            assert len(data) == 1

    def test_flush_creates_parent_directory(self):
        """Flush creates parent directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "subdir" / "deep" / "test.json"
            delegate = FakeLLMProvider()
            recorder = RecordingLLMProvider(delegate, cassette_path)

            recorder.complete(
                system_prompt="sys",
                user_prompt="user",
                model="test",
                temperature=0.5,
                seed=42,
            )
            recorder.flush()

            assert cassette_path.exists()
            assert cassette_path.parent.exists()

    def test_flush_io_error_raises(self):
        """Flush raises IOError on write failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a read-only file path
            cassette_path = Path(tmpdir) / "readonly" / "test.json"
            cassette_path.parent.mkdir(parents=True, exist_ok=True)

            # Create the directory and make it read-only
            import os

            os.chmod(cassette_path.parent, 0o444)

            try:
                delegate = FakeLLMProvider()
                recorder = RecordingLLMProvider(delegate, cassette_path)

                recorder.complete(
                    system_prompt="sys",
                    user_prompt="user",
                    model="test",
                    temperature=0.5,
                    seed=42,
                )

                with pytest.raises(IOError, match="Failed to write cassette"):
                    recorder.flush()
            finally:
                os.chmod(cassette_path.parent, 0o755)


class TestCassetteLLMProvider:
    """Tests for cassette replay provider."""

    def test_loads_cassette_from_file(self):
        """Cassette provider loads from valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            test_cassette = {
                "hash1": {
                    "content": "response 1",
                    "tokens_in": 10,
                    "tokens_out": 20,
                    "model": "test-model",
                    "finish_reason": "stop",
                }
            }
            with open(cassette_path, "w") as f:
                json.dump(test_cassette, f)

            provider = CassetteLLMProvider(cassette_path)
            assert provider._cassette == test_cassette

    def test_missing_cassette_raises(self):
        """Missing cassette file raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "nonexistent.json"

            with pytest.raises(FileNotFoundError):
                CassetteLLMProvider(cassette_path)

    def test_malformed_cassette_raises(self):
        """Malformed JSON raises JSONDecodeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            with open(cassette_path, "w") as f:
                f.write("{ invalid json }")

            with pytest.raises(json.JSONDecodeError):
                CassetteLLMProvider(cassette_path)

    def test_replays_recorded_response(self):
        """Cassette provider replays recorded responses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Record a response
            cassette_path = Path(tmpdir) / "test.json"
            delegate = FakeLLMProvider()
            recorder = RecordingLLMProvider(delegate, cassette_path)

            response = recorder.complete(
                system_prompt="sys",
                user_prompt="user",
                model="test",
                temperature=0.5,
                seed=42,
            )
            recorder.flush()

            # Replay it
            player = CassetteLLMProvider(cassette_path)
            replayed = player.complete(
                system_prompt="sys",
                user_prompt="user",
                model="test",
                temperature=0.5,
                seed=42,
            )

            assert replayed.content == response.content
            assert replayed.tokens_in == response.tokens_in
            assert replayed.tokens_out == response.tokens_out
            assert replayed.model == response.model
            assert replayed.finish_reason == response.finish_reason

    def test_stale_cassette_raises_for_missing_hash(self):
        """Missing prompt hash raises CassetteStaleError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            test_cassette = {
                "hash1": {
                    "content": "response 1",
                    "tokens_in": 10,
                    "tokens_out": 20,
                    "model": "test-model",
                    "finish_reason": "stop",
                }
            }
            with open(cassette_path, "w") as f:
                json.dump(test_cassette, f)

            provider = CassetteLLMProvider(cassette_path)

            with pytest.raises(CassetteStaleError, match="No recorded response"):
                provider.complete(
                    system_prompt="different_sys",
                    user_prompt="different_user",
                    model="test",
                    temperature=0.5,
                    seed=42,
                )

    def test_async_replay_delegates_to_sync(self):
        """Async replay delegates to sync method."""
        import asyncio

        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            delegate = FakeLLMProvider()
            recorder = RecordingLLMProvider(delegate, cassette_path)

            response = recorder.complete(
                system_prompt="sys",
                user_prompt="user",
                model="test",
                temperature=0.5,
                seed=42,
            )
            recorder.flush()

            player = CassetteLLMProvider(cassette_path)

            async def test():
                replayed = await player.complete_async(
                    system_prompt="sys",
                    user_prompt="user",
                    model="test",
                    temperature=0.5,
                    seed=42,
                )
                return replayed

            replayed = asyncio.run(test())
            assert replayed.content == response.content

    def test_is_model_available_always_true(self):
        """is_model_available always returns True for cassette."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            with open(cassette_path, "w") as f:
                json.dump({}, f)

            provider = CassetteLLMProvider(cassette_path)
            assert provider.is_model_available("any-model") is True
            assert provider.is_model_available("another-model") is True

    def test_list_available_models_empty(self):
        """list_available_models returns empty list for cassette."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            with open(cassette_path, "w") as f:
                json.dump({}, f)

            provider = CassetteLLMProvider(cassette_path)
            assert provider.list_available_models() == []


class TestRecordingAndReplayIntegration:
    """Integration tests for recording and replaying."""

    def test_roundtrip_record_and_replay(self):
        """Record multiple responses and replay them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test.json"
            delegate = FakeLLMProvider()
            recorder = RecordingLLMProvider(delegate, cassette_path)

            test_cases = [
                ("sys1", "user1", "model1", 0.0, 42),
                ("sys2", "user2", "model2", 0.5, 43),
                ("sys3", "user3", "model3", 1.0, None),
            ]

            recorded_responses = {}
            for sys, usr, mod, temp, seed in test_cases:
                response = recorder.complete(
                    system_prompt=sys,
                    user_prompt=usr,
                    model=mod,
                    temperature=temp,
                    seed=seed,
                )
                key = _compute_prompt_hash(sys, usr, mod, temp, seed)
                recorded_responses[key] = response

            recorder.flush()

            # Now replay
            player = CassetteLLMProvider(cassette_path)
            for sys, usr, mod, temp, seed in test_cases:
                replayed = player.complete(
                    system_prompt=sys,
                    user_prompt=usr,
                    model=mod,
                    temperature=temp,
                    seed=seed,
                )
                key = _compute_prompt_hash(sys, usr, mod, temp, seed)
                original = recorded_responses[key]
                assert replayed.content == original.content
