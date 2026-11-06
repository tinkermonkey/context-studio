"""
Decision model served by Cloudflare Workers AI's state-plus-questions API.

POST {base_url}/accounts/{account_id}/ai/run/{model}
    {"model": <request model>, "state": <text>, "questions": {<name>: <question>}}

Each question is {"type": "choice"|"score"|"noul", "instructions", "criteria"}.
The model id comes from the instance config; account id, token, request model
and base URL come from the instance's adapter options (WorkersAIOptions).
Nothing here names a particular model.

Requests that get HTTP 429 (honoring Retry-After) or 5xx, or fail to connect,
are retried with exponential backoff; if they still fail the error is
DecisionModelUnavailableError, which lets a fallback instance answer. Other
4xx responses raise DecisionModelRequestError and are not retried or passed to
a fallback. At most `concurrency` requests are in flight at once per instance.
latency_ms is measured from when the request gets a concurrency slot, so it
covers the call and its retries, not time spent queued.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Awaitable, Callable, Mapping, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

from adapters.decision.common import ConcurrencyLimit, cost_share, finish_answers, request_cost
from adapters.decision.parsing import as_number, choice_of, score_of, yes_no_of
from domain.decision.exceptions import (
    DecisionModelError,
    DecisionModelNotConfiguredError,
    DecisionModelRequestError,
    DecisionModelUnavailableError,
)
from domain.decision.value_objects import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
    YesNoAnswer,
    YesNoQuestion,
)
from utils.logger import get_logger

logger = get_logger(__name__)

WORKERS_AI_BASE_URL = "https://api.cloudflare.com/client/v4"
_MAX_ERROR_TEXT = 500
_MAX_RETRY_AFTER_SECONDS = 60.0


class WorkersAIOptions(BaseModel):
    """The `options` object of a workers_ai instance in config.json."""

    # Errors must never echo input values: api_token is one of them
    model_config = ConfigDict(hide_input_in_errors=True)

    account_id: str = Field(default="", description="Cloudflare account id")
    api_token: str = Field(default="", description="API token with Workers AI access")
    request_model: Optional[str] = Field(
        default=None,
        description="Model name sent in the request body; defaults to the last segment of model",
    )
    base_url: str = Field(default=WORKERS_AI_BASE_URL, description="API base URL")


def wire_question(question: Question) -> dict[str, Any]:
    """The Workers AI wire form of a question (yes/no is the wire's 'noul' type)."""
    if isinstance(question, ChoiceQuestion):
        return {
            "type": "choice",
            "instructions": question.instructions,
            "criteria": question.options(),
        }
    if isinstance(question, ScoreQuestion):
        return {
            "type": "score",
            "instructions": question.instructions,
            "criteria": list(question.levels),
        }
    if isinstance(question, YesNoQuestion):
        return {"type": "noul", "instructions": question.instructions}
    raise TypeError(f"Unsupported question type: {type(question).__name__}")


def _parse_one(question: Question, wire: Any, meta: Mapping[str, Any]) -> Optional[Answer]:
    """One typed answer, or None when the wire answer is missing or unusable."""
    if not isinstance(wire, Mapping):
        return None
    if isinstance(question, ChoiceQuestion):
        choice, probabilities, confidence = choice_of(wire, offered=question.options())
        if choice is None:
            return None
        return ChoiceAnswer(
            choice=choice, probabilities=probabilities, confidence=confidence, **meta
        )
    if isinstance(question, ScoreQuestion):
        score, distribution = score_of(wire, len(question.levels))
        return (
            None if score is None else ScoreAnswer(score=score, probabilities=distribution, **meta)
        )
    p_yes = yes_no_of(wire)
    return None if p_yes is None else YesNoAnswer(p_yes=p_yes, **meta)


def parse_answers(
    payload: Any,
    questions: Mapping[str, Question],
    *,
    model_name: str,
    latency_ms: float,
    price_per_mtok_in: Optional[float],
    price_per_mtok_out: Optional[float] = None,
) -> dict[str, Answer]:
    """
    Turn a Workers AI response body into one answer per question.

    A question without a usable answer gets an empty answer (value None) and
    is logged. The request's cost is split evenly across its answers, so
    summing cost_usd over answers gives the cost of the calls.

    Raises:
        DecisionModelError: if the body reports failure or no question was answered
    """
    if not isinstance(payload, Mapping):
        raise DecisionModelError(f"{model_name}: response is not a JSON object")
    if payload.get("success") is False:
        errors = payload.get("errors") or payload
        raise DecisionModelError(f"{model_name}: request failed: {str(errors)[:_MAX_ERROR_TEXT]}")
    result = payload.get("result")
    result = result if isinstance(result, Mapping) else {}
    # Some deployments return the result unwrapped
    answers = result.get("answers") or payload.get("answers") or {}
    usage = result.get("usage") or payload.get("usage") or {}
    if not isinstance(answers, Mapping):
        raise DecisionModelError(f"{model_name}: response answers are not an object")
    usage = usage if isinstance(usage, Mapping) else {}
    tokens_in = int(as_number(usage.get("input_tokens")) or 0)
    tokens_out = int(as_number(usage.get("output_tokens")) or 0)
    cost = request_cost(tokens_in, tokens_out, price_per_mtok_in, price_per_mtok_out)
    meta = {"model": model_name, "latency_ms": latency_ms, "cost_usd": cost_share(cost, questions)}
    parsed = {name: _parse_one(q, answers.get(name), meta) for name, q in questions.items()}
    return finish_answers(parsed, questions, meta)


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _retry_after(response: httpx.Response) -> Optional[float]:
    """Seconds to wait from a Retry-After header (seconds or an HTTP date), capped."""
    value = response.headers.get("Retry-After", "").strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    return min(max(seconds, 0.0), _MAX_RETRY_AFTER_SECONDS)


class WorkersAIDecisionModel:
    """DecisionModel adapter for the Workers AI state-plus-questions API."""

    def __init__(
        self,
        name: str,
        *,
        model: str,
        options: WorkersAIOptions,
        price_per_mtok_in: Optional[float] = None,
        price_per_mtok_out: Optional[float] = None,
        concurrency: int = 4,
        timeout_seconds: float = 60.0,
        max_attempts: int = 4,
        backoff_seconds: float = 1.0,
        transport: Optional[httpx.BaseTransport] = None,
        async_transport: Optional[httpx.AsyncBaseTransport] = None,
        sleep: Callable[[float], None] = time.sleep,
        async_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._name = name
        self._model = model
        self._options = options
        # The body names the model by its short name, e.g. the last segment of the id
        self._request_model = options.request_model or model.rsplit("/", 1)[-1]
        self._price_in = price_per_mtok_in
        self._price_out = price_per_mtok_out
        self._timeout = timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._backoff = backoff_seconds
        self._transport = transport
        self._async_transport = async_transport
        self._sleep = sleep
        self._async_sleep = async_sleep
        self._limit = ConcurrencyLimit(concurrency)

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_configured(self) -> bool:
        return bool(self._options.account_id and self._options.api_token and self._model)

    def _url(self) -> str:
        base = self._options.base_url.rstrip("/")
        return f"{base}/accounts/{self._options.account_id}/ai/run/{self._model}"

    def _request(self, state: str, questions: Mapping[str, Question]) -> dict[str, Any]:
        if not self.is_configured:
            raise DecisionModelNotConfiguredError(
                f"Decision model '{self._name}' needs options.account_id and options.api_token"
            )
        if not questions:
            raise ValueError("At least one question is required")
        return {
            "model": self._request_model,
            "state": state,
            "questions": {name: wire_question(q) for name, q in questions.items()},
        }

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._options.api_token}"}

    def _delay(self, attempt: int, response: Optional[httpx.Response]) -> float:
        """Backoff before the next attempt; at least the server's Retry-After on a 429."""
        delay = self._backoff * (2**attempt)
        if response is not None and response.status_code == 429:
            retry_after = _retry_after(response)
            if retry_after is not None:
                delay = max(delay, retry_after)
        return delay

    def _final_response(self, response: httpx.Response) -> Any:
        """The JSON body of a non-retryable response, or a DecisionModelError."""
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.is_error:
            detail = (
                str(payload.get("errors") or payload)
                if isinstance(payload, Mapping)
                else response.text
            )
            raise DecisionModelRequestError(
                f"{self._name}: HTTP {response.status_code}: {detail[:_MAX_ERROR_TEXT]}"
            )
        if payload is None:
            raise DecisionModelError(f"{self._name}: response is not JSON")
        return payload

    def _parse(self, payload: Any, questions: Mapping[str, Question], started: float):
        return parse_answers(
            payload,
            questions,
            model_name=self._name,
            latency_ms=(time.perf_counter() - started) * 1000,
            price_per_mtok_in=self._price_in,
            price_per_mtok_out=self._price_out,
        )

    def _retry_error(self, attempt: int, detail: str) -> DecisionModelUnavailableError:
        logger.warning(
            "Decision model %s: attempt %d/%d failed (%s)",
            self._name,
            attempt + 1,
            self._max_attempts,
            detail,
        )
        return DecisionModelUnavailableError(f"{self._name}: {detail}")

    def decide(self, state: str, questions: Mapping[str, Question]) -> dict[str, Answer]:
        body = self._request(state, questions)
        last_error: Optional[DecisionModelError] = None
        last_response: Optional[httpx.Response] = None
        with self._limit.slot():
            started = time.perf_counter()
            try:
                with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                    for attempt in range(self._max_attempts):
                        if attempt:
                            self._sleep(self._delay(attempt - 1, last_response))
                        try:
                            response = client.post(self._url(), headers=self._headers(), json=body)
                        except httpx.TransportError as e:
                            last_error = self._retry_error(attempt, f"{type(e).__name__}: {e}")
                            last_response = None
                            continue
                        if _is_retryable_status(response.status_code):
                            last_error = self._retry_error(
                                attempt, f"HTTP {response.status_code}: {response.text[:300]}"
                            )
                            last_response = response
                            continue
                        return self._parse(self._final_response(response), questions, started)
            except DecisionModelError:
                raise
            except Exception as e:
                raise DecisionModelError(f"{self._name}: {type(e).__name__}: {e}") from e
        assert last_error is not None
        raise last_error

    async def decide_async(
        self, state: str, questions: Mapping[str, Question]
    ) -> dict[str, Answer]:
        body = self._request(state, questions)
        last_error: Optional[DecisionModelError] = None
        last_response: Optional[httpx.Response] = None
        async with self._limit.async_slot():
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(
                    transport=self._async_transport, timeout=self._timeout
                ) as client:
                    for attempt in range(self._max_attempts):
                        if attempt:
                            await self._async_sleep(self._delay(attempt - 1, last_response))
                        try:
                            response = await client.post(
                                self._url(), headers=self._headers(), json=body
                            )
                        except httpx.TransportError as e:
                            last_error = self._retry_error(attempt, f"{type(e).__name__}: {e}")
                            last_response = None
                            continue
                        if _is_retryable_status(response.status_code):
                            last_error = self._retry_error(
                                attempt, f"HTTP {response.status_code}: {response.text[:300]}"
                            )
                            last_response = response
                            continue
                        return self._parse(self._final_response(response), questions, started)
            except DecisionModelError:
                raise
            except Exception as e:
                raise DecisionModelError(f"{self._name}: {type(e).__name__}: {e}") from e
        assert last_error is not None
        raise last_error
