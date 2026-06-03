"""LLM-level recording and replay for deterministic pipeline quality tests.

Records LLM interactions at the LLMProvider protocol boundary as
(prompt_hash → LLMResponse) pairs, enabling compact cassettes that survive
SDK version changes and transport-layer modifications.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from domain.pipelines.ports import LLMResponse


class CassetteStaleError(Exception):
    """Raised when a cassette lacks a recorded response for a prompt hash.

    This indicates the cassette may be outdated relative to the test inputs,
    or the test has been modified since the cassette was recorded.
    """

    pass


class RecordingLLMProvider:
    """Wraps a real LLMProvider, recording interactions to disk.

    Records all prompt→response pairs during live execution. At the end of
    execution, call flush() to write the cassette file.
    """

    def __init__(self, delegate: Any, cassette_path: Path) -> None:
        """
        Initialize the recording provider.

        Args:
            delegate: Real LLMProvider to delegate calls to
            cassette_path: Path where cassette will be written (relative or absolute)
        """
        self._delegate = delegate
        self._cassette_path = Path(cassette_path)
        self._recordings: dict[str, dict[str, Any]] = {}

    def _hash_key(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        seed: int | None,
    ) -> str:
        """Compute a stable hash key for a prompt."""
        seed_part = str(seed) if seed is not None else "none"
        payload = f"{system_prompt}|{user_prompt}|{model}|{temperature}|{seed_part}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """Request a completion and record the response."""
        key = self._hash_key(system_prompt, user_prompt, model, temperature, seed)
        response = self._delegate.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )
        self._recordings[key] = {
            "content": response.content,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "model": response.model,
            "finish_reason": response.finish_reason,
        }
        return response

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """Request a completion (async) and record the response."""
        key = self._hash_key(system_prompt, user_prompt, model, temperature, seed)
        response = await self._delegate.complete_async(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )
        self._recordings[key] = {
            "content": response.content,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "model": response.model,
            "finish_reason": response.finish_reason,
        }
        return response

    def is_model_available(self, model: str) -> bool:
        """Check if a model is available."""
        return self._delegate.is_model_available(model)

    def list_available_models(self) -> list[str]:
        """Get list of available models."""
        return self._delegate.list_available_models()

    def flush(self) -> None:
        """Write recorded cassette to disk."""
        self._cassette_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cassette_path, "w") as f:
            json.dump(self._recordings, f, indent=2)


class RecordingHTTPTransport:
    """Records and replays HTTP interactions for grounding sources.

    This stub will be extended in Phase B.3 when grounding source adapters
    (DBpedia, ConceptNet, Wikidata) are integrated with quality testing.

    Records `(request_signature → response)` pairs using respx mocking at the
    httpx.AsyncClient transport layer.
    """

    def __init__(self, cassette_path: Path | None = None) -> None:
        """
        Initialize HTTP transport recording.

        Args:
            cassette_path: Path to HTTP cassette file (future use)
        """
        self._cassette_path = cassette_path
        self._recordings: dict[str, dict[str, Any]] = {}

    def record_call(self, request_sig: str, response_data: dict[str, Any]) -> None:
        """
        Record an HTTP request/response pair.

        Args:
            request_sig: Hash of request (method, URL, params)
            response_data: Response body and metadata
        """
        self._recordings[request_sig] = response_data

    def flush(self) -> None:
        """Write HTTP cassette to disk (stub for Phase B.3)."""
        if self._cassette_path:
            self._cassette_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cassette_path, "w") as f:
                json.dump(self._recordings, f, indent=2)


class CassetteLLMProvider:
    """Replays LLM responses from a recorded cassette file.

    All responses are deterministic, requiring zero network access.
    Raises CassetteStaleError if a prompt is not found in the cassette,
    directing the user to run with --refresh-cassettes.
    """

    def __init__(self, cassette_path: Path) -> None:
        """
        Initialize the cassette provider.

        Args:
            cassette_path: Path to the cassette JSON file

        Raises:
            FileNotFoundError: If cassette does not exist
            json.JSONDecodeError: If cassette is malformed
        """
        self._cassette_path = Path(cassette_path)
        with open(self._cassette_path, "r") as f:
            self._cassette: dict[str, dict[str, Any]] = json.load(f)

    def _hash_key(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        seed: int | None,
    ) -> str:
        """Compute a stable hash key for a prompt."""
        seed_part = str(seed) if seed is not None else "none"
        payload = f"{system_prompt}|{user_prompt}|{model}|{temperature}|{seed_part}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """Replay a response from the cassette."""
        key = self._hash_key(system_prompt, user_prompt, model, temperature, seed)

        if key not in self._cassette:
            raise CassetteStaleError(
                f"No recorded response for prompt hash {key[:12]}... "
                f"Cassette may be stale or test inputs changed. "
                f"Re-record by running: pytest --refresh-cassettes"
            )

        entry = self._cassette[key]
        return LLMResponse(
            content=entry["content"],
            tokens_in=entry["tokens_in"],
            tokens_out=entry["tokens_out"],
            duration_ms=0.0,
            finish_reason=entry["finish_reason"],
            model=entry["model"],
        )

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """Replay a response from the cassette (async)."""
        return self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )

    def is_model_available(self, model: str) -> bool:
        """Check if a model is available (always true for cassette)."""
        return True

    def list_available_models(self) -> list[str]:
        """Get list of available models (empty for cassette)."""
        return []
