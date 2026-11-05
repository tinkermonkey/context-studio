"""
Helpers shared by the decision-model adapters: cost, empty answers for
questions the model did not answer, and the client-side concurrency limit.
"""

from __future__ import annotations

import asyncio
import threading
import weakref
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator, Mapping, Optional

from domain.decision.exceptions import DecisionModelError
from domain.decision.value_objects import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
    YesNoAnswer,
)
from utils.logger import get_logger

logger = get_logger(__name__)


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


def cost_share(cost: Optional[float], questions: Mapping[str, Question]) -> Optional[float]:
    """A request's cost split evenly across its answers (sums back to the request cost)."""
    return cost / len(questions) if cost is not None and questions else cost


def empty_answer(question: Question, **meta: Any) -> Answer:
    """An answer with no value, for a question the model left unanswered."""
    if isinstance(question, ChoiceQuestion):
        return ChoiceAnswer(choice=None, **meta)
    if isinstance(question, ScoreQuestion):
        return ScoreAnswer(score=None, **meta)
    return YesNoAnswer(p_yes=None, **meta)


def finish_answers(
    parsed: dict[str, Optional[Answer]],
    questions: Mapping[str, Question],
    meta: Mapping[str, Any],
) -> dict[str, Answer]:
    """
    Fill unanswered questions with empty answers (logged), keeping one bad answer
    from discarding the rest of the request.

    Raises:
        DecisionModelError: if no question was answered at all
    """
    missing = [name for name in questions if parsed.get(name) is None]
    if len(missing) == len(questions):
        raise DecisionModelError(f"{meta['model']}: no usable answer in the response")
    if missing:
        logger.warning("Decision model %s left unanswered: %s", meta["model"], ", ".join(missing))
    return {
        name: parsed.get(name) or empty_answer(question, **meta)
        for name, question in questions.items()
    }


class ConcurrencyLimit:
    """
    At most `limit` calls in flight: one semaphore for threads, and one per
    event loop for async callers (an asyncio.Semaphore belongs to one loop).
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._threads = threading.BoundedSemaphore(limit)
        self._loops: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
            weakref.WeakKeyDictionary()
        )
        self._lock = threading.Lock()

    @contextmanager
    def slot(self) -> Iterator[None]:
        with self._threads:
            yield

    @asynccontextmanager
    async def async_slot(self) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        with self._lock:
            semaphore = self._loops.get(loop)
            if semaphore is None:
                semaphore = self._loops[loop] = asyncio.Semaphore(self._limit)
        async with semaphore:
            yield
