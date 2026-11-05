"""
Decision model served by Cloudflare Workers AI's state-plus-questions API.

POST {base_url}/accounts/{account_id}/ai/run/{model}
    {"model": <request model>, "state": <text>, "questions": {<name>: <question>}}

Each question is {"type": "choice"|"score"|"noul", "instructions", "criteria"}.
The model id, the request model name, credentials and price all come from
config; nothing here names a particular model.

Requests that get HTTP 429 or 5xx, or fail to connect, are retried with
exponential backoff. At most `concurrency` requests are in flight at once
per instance (separately for sync and async callers).
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Awaitable, Callable, Mapping, Optional

import httpx

from adapters.decision.parsing import choice_of, score_of, yes_no_of
from domain.decision.exceptions import DecisionModelError, DecisionModelNotConfiguredError
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


def request_cost(
    tokens_in: int,
    tokens_out: int,
    price_per_mtok_in: Optional[float],
    price_per_mtok_out: Optional[float] = None,
) -> Optional[float]:
    """USD cost of one request, or None when no input price is configured."""
    if price_per_mtok_in is None:
        return None
    cost = tokens_in * price_per_mtok_in / 1e6
    if price_per_mtok_out is not None:
        cost += tokens_out * price_per_mtok_out / 1e6
    return cost


def parse_answers(
    payload: Any,
    questions: Mapping[str, Question],
    *,
    model_name: str,
    latency_ms: float,
    price_per_mtok_in: Optional[float],
) -> dict[str, Answer]:
    """
    Turn a Workers AI response body into one answer per question.

    The request's cost is split evenly across its answers, so summing cost_usd
    over answers gives the cost of the calls.

    Raises:
        DecisionModelError: if the body reports failure or lacks an answer
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
    tokens_in = int(usage.get("input_tokens") or 0) if isinstance(usage, Mapping) else 0
    tokens_out = int(usage.get("output_tokens") or 0) if isinstance(usage, Mapping) else 0
    cost = request_cost(tokens_in, tokens_out, price_per_mtok_in)
    share = cost / len(questions) if cost is not None and questions else cost

    parsed: dict[str, Answer] = {}
    for name, question in questions.items():
        wire = answers.get(name)
        if not isinstance(wire, Mapping):
            raise DecisionModelError(f"{model_name}: no answer for question '{name}'")
        meta: dict[str, Any] = {"model": model_name, "latency_ms": latency_ms, "cost_usd": share}
        if isinstance(question, ChoiceQuestion):
            choice, probabilities, confidence = choice_of(wire)
            parsed[name] = ChoiceAnswer(
                choice=choice, probabilities=probabilities, confidence=confidence, **meta
            )
        elif isinstance(question, ScoreQuestion):
            score, distribution = score_of(wire, len(question.levels))
            parsed[name] = ScoreAnswer(score=score, probabilities=distribution, **meta)
        else:
            parsed[name] = YesNoAnswer(p_yes=yes_no_of(wire), **meta)
    return parsed


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


class WorkersAIDecisionModel:
    """DecisionModel adapter for the Workers AI state-plus-questions API."""

    def __init__(
        self,
        name: str,
        *,
        model: str,
        account_id: str,
        api_token: str,
        request_model: Optional[str] = None,
        price_per_mtok_in: Optional[float] = None,
        concurrency: int = 4,
        timeout_seconds: float = 60.0,
        max_attempts: int = 4,
        backoff_seconds: float = 1.0,
        base_url: str = WORKERS_AI_BASE_URL,
        transport: Optional[httpx.BaseTransport] = None,
        async_transport: Optional[httpx.AsyncBaseTransport] = None,
        sleep: Callable[[float], None] = time.sleep,
        async_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._name = name
        self._model = model
        self._account_id = account_id
        self._api_token = api_token
        # The body names the model by its short name, e.g. the last segment of the id
        self._request_model = request_model or model.rsplit("/", 1)[-1]
        self._price_per_mtok_in = price_per_mtok_in
        self._timeout = timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._backoff = backoff_seconds
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._async_transport = async_transport
        self._sleep = sleep
        self._async_sleep = async_sleep
        self._concurrency = concurrency
        self._sync_slots = threading.BoundedSemaphore(concurrency)
        self._async_slots: Optional[tuple[asyncio.AbstractEventLoop, asyncio.Semaphore]] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_configured(self) -> bool:
        return bool(self._account_id and self._api_token and self._model)

    def _url(self) -> str:
        return f"{self._base_url}/accounts/{self._account_id}/ai/run/{self._model}"

    def _request(self, state: str, questions: Mapping[str, Question]) -> dict[str, Any]:
        if not self.is_configured:
            raise DecisionModelNotConfiguredError(
                f"Decision model '{self._name}' needs account_id and api_token"
            )
        if not questions:
            raise ValueError("At least one question is required")
        return {
            "model": self._request_model,
            "state": state,
            "questions": {name: wire_question(q) for name, q in questions.items()},
        }

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_token}"}

    def _delay(self, attempt: int) -> float:
        return self._backoff * (2**attempt)

    def _final_response(self, response: httpx.Response) -> Any:
        """The JSON body of a non-retryable response, or a DecisionModelError."""
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.is_error and not (
            isinstance(payload, Mapping) and payload.get("success") is False
        ):
            raise DecisionModelError(
                f"{self._name}: HTTP {response.status_code}: {response.text[:_MAX_ERROR_TEXT]}"
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
            price_per_mtok_in=self._price_per_mtok_in,
        )

    def _retry_error(self, attempt: int, detail: str) -> DecisionModelError:
        logger.warning(
            "Decision model %s: attempt %d/%d failed (%s)",
            self._name,
            attempt + 1,
            self._max_attempts,
            detail,
        )
        return DecisionModelError(f"{self._name}: {detail}")

    def decide(self, state: str, questions: Mapping[str, Question]) -> dict[str, Answer]:
        body = self._request(state, questions)
        started = time.perf_counter()
        last_error: Optional[DecisionModelError] = None
        with (
            self._sync_slots,
            httpx.Client(transport=self._transport, timeout=self._timeout) as client,
        ):
            for attempt in range(self._max_attempts):
                if attempt:
                    self._sleep(self._delay(attempt - 1))
                try:
                    response = client.post(self._url(), headers=self._headers(), json=body)
                except httpx.TransportError as e:
                    last_error = self._retry_error(attempt, f"{type(e).__name__}: {e}")
                    continue
                if _is_retryable_status(response.status_code):
                    last_error = self._retry_error(
                        attempt, f"HTTP {response.status_code}: {response.text[:300]}"
                    )
                    continue
                return self._parse(self._final_response(response), questions, started)
        assert last_error is not None
        raise last_error

    def _async_semaphore(self) -> asyncio.Semaphore:
        """The async concurrency limit for the running event loop."""
        loop = asyncio.get_running_loop()
        if self._async_slots is None or self._async_slots[0] is not loop:
            self._async_slots = (loop, asyncio.Semaphore(self._concurrency))
        return self._async_slots[1]

    async def decide_async(
        self, state: str, questions: Mapping[str, Question]
    ) -> dict[str, Answer]:
        body = self._request(state, questions)
        started = time.perf_counter()
        last_error: Optional[DecisionModelError] = None
        async with self._async_semaphore():
            async with httpx.AsyncClient(
                transport=self._async_transport, timeout=self._timeout
            ) as client:
                for attempt in range(self._max_attempts):
                    if attempt:
                        await self._async_sleep(self._delay(attempt - 1))
                    try:
                        response = await client.post(
                            self._url(), headers=self._headers(), json=body
                        )
                    except httpx.TransportError as e:
                        last_error = self._retry_error(attempt, f"{type(e).__name__}: {e}")
                        continue
                    if _is_retryable_status(response.status_code):
                        last_error = self._retry_error(
                            attempt, f"HTTP {response.status_code}: {response.text[:300]}"
                        )
                        continue
                    return self._parse(self._final_response(response), questions, started)
        assert last_error is not None
        raise last_error
