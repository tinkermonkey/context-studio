"""HTTP and LLM-level recording and replay for deterministic pipeline quality tests.

Records HTTP interactions at the httpx.AsyncClient transport layer and
LLM interactions at the LLMProvider protocol boundary, enabling cassettes
that survive SDK version changes and preserve request-response patterns.

HTTP cassettes record request/response pairs at the AsyncBaseTransport level,
enabling deterministic replay without network access. LLM cassettes store
prompt→response pairs indexed by prompt hash.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import httpx

from domain.pipelines.ports import LLMResponse


def _compute_prompt_hash(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    seed: int | None,
) -> str:
    """Compute a stable hash key for a prompt.

    The hash is based on semantic content (prompts and model) and parameters
    that affect LLM behavior. It survives SDK version changes and transport-layer
    modifications, enabling cassette replay consistency.
    """
    seed_part = str(seed) if seed is not None else "none"
    payload = f"{system_prompt}|{user_prompt}|{model}|{temperature}|{seed_part}"
    return hashlib.sha256(payload.encode()).hexdigest()


class RecordingHTTPTransport(httpx.AsyncBaseTransport):
    """Intercepts httpx.AsyncClient calls at the transport layer and records them to disk.

    Records HTTP interactions (request/response pairs) to a JSON cassette file,
    enabling deterministic replay in tests without network access.
    """

    def __init__(self, delegate: httpx.AsyncBaseTransport, cassette_path: Path) -> None:
        """
        Initialize the recording transport.

        Args:
            delegate: Real AsyncBaseTransport to delegate calls to
            cassette_path: Path where cassette will be written (relative or absolute)
        """
        self._delegate = delegate
        self._cassette_path = Path(cassette_path)
        self._recordings: list[dict[str, Any]] = []

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        """Handle an async request and record the interaction."""
        response = await self._delegate.handle_async_request(request)

        # Explicitly read the response body to handle streaming responses safely
        await response.aread()

        interaction = {
            "request": {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": request.content.decode() if request.content else None,
            },
            "response": {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
            },
        }
        self._recordings.append(interaction)

        return response

    async def aclose(self) -> None:
        """Close the transport and write the cassette."""
        await self._delegate.aclose()
        self.flush()

    def flush(self) -> None:
        """Write recorded cassette to disk."""
        try:
            self._cassette_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cassette_path, "w") as f:
                json.dump({"interactions": self._recordings}, f, indent=2)
        except OSError as e:
            raise IOError(f"Failed to write cassette to {self._cassette_path}: {e}") from e


class ReplayHTTPTransport(httpx.AsyncBaseTransport):
    """Replays HTTP responses from a recorded cassette file.

    All responses are deterministic, requiring zero network access.
    Raises an error if a request is not found in the cassette.
    """

    def __init__(self, cassette_path: Path) -> None:
        """
        Initialize the replay transport.

        Args:
            cassette_path: Path to the cassette JSON file

        Raises:
            FileNotFoundError: If cassette does not exist
            json.JSONDecodeError: If cassette is malformed
        """
        self._cassette_path = Path(cassette_path)
        with open(self._cassette_path, "r") as f:
            cassette = json.load(f)
            self._interactions: list[dict[str, Any]] = cassette.get("interactions", [])
        self._interaction_index = 0

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        """Replay a response from the cassette."""
        if self._interaction_index >= len(self._interactions):
            raise RuntimeError(
                f"Cassette exhausted: tried to replay interaction {self._interaction_index} "
                f"but cassette only has {len(self._interactions)} interactions"
            )

        interaction = self._interactions[self._interaction_index]
        self._interaction_index += 1

        response_data = interaction["response"]
        return httpx.Response(
            status_code=response_data["status_code"],
            headers=response_data.get("headers", {}),
            content=response_data.get("body", "").encode(),
        )

    async def aclose(self) -> None:
        """Close the transport (no-op for replay)."""
        pass


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
        key = _compute_prompt_hash(system_prompt, user_prompt, model, temperature, seed)
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
        key = _compute_prompt_hash(system_prompt, user_prompt, model, temperature, seed)
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
        try:
            self._cassette_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cassette_path, "w") as f:
                json.dump(self._recordings, f, indent=2)
        except OSError as e:
            raise IOError(f"Failed to write cassette to {self._cassette_path}: {e}") from e


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
        key = _compute_prompt_hash(system_prompt, user_prompt, model, temperature, seed)

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
