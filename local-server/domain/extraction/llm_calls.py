"""
One LLM call of an extraction stage, asked again until it gives a whole answer.

Every stage of individual extraction asks the LLM for something it can parse.
A response that does not parse says nothing about the text, so it is never read
as "found nothing": the provider is told to forget it and the same call is made
again. A provider failure that may pass is asked again after a short wait. Both
spend the same few attempts; what the last attempt met is what the call reports.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Mapping, TypeVar

from domain.pipelines.exceptions import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRequestRefusedError,
    LLMTransientError,
)
from domain.pipelines.ports import LLMProvider, LLMResponse

from .exceptions import IncompleteLLMResponseError

_logger = logging.getLogger(__name__)

# How many times a stage's call is made before it fails: an attempt is spent by
# a response that is not the model's whole answer and by a provider failure
# that may pass
MAX_LLM_ATTEMPTS = 3

# Seconds waited before the second attempt after a provider failure that may
# pass; the wait doubles before each attempt after that
FIRST_RETRY_WAIT_SECONDS = 1.0

_T = TypeVar("_T")


class TokenTally:
    """
    The tokens of every LLM response received, whether or not it could be used.

    One tally belongs to one thread at a time: calls made side by side each
    keep their own, and whoever started them adds the totals up.
    """

    def __init__(self) -> None:
        self.total = 0

    def add(self, response: LLMResponse) -> None:
        self.total += response.tokens_in + response.tokens_out


def no_whole_answer(
    stage: str, failures: list[IncompleteLLMResponseError | LLMTransientError]
) -> IncompleteLLMResponseError | LLMTransientError:
    """
    The failure of a stage whose every attempt got no whole answer, from why
    each attempt failed, in order.

    Attempts that all failed the same way are reported as that failure
    outlasting them. Attempts that failed in different ways are reported by
    the last, as an incomplete response or a provider failure that may pass:
    never as a rate limit, since a rate limit that was not met every time did
    not outlast the attempts and says nothing about the next text.
    """
    last = failures[-1]
    incomplete = isinstance(last, IncompleteLLMResponseError)
    if len({type(failure) for failure in failures}) > 1:
        kind = IncompleteLLMResponseError if incomplete else LLMTransientError
        message = (
            f"The LLM gave no complete answer for {stage} in {len(failures)} attempts"
            f" that failed in different ways, the last with: {last}"
        )
    elif incomplete:
        kind = IncompleteLLMResponseError
        message = (
            f"The LLM response for {stage} was still incomplete after"
            f" {len(failures)} attempts: {last}"
        )
    else:
        kind = type(last)
        message = f"The LLM request for {stage} still failed after {len(failures)} attempts: {last}"
    failure = kind(message)
    failure.__cause__ = last
    return failure


def complete_parsed(
    llm: LLMProvider,
    sleep: Callable[[float], None],
    stage: str,
    request: Mapping[str, Any],
    parse: Callable[[str], _T],
    spent: TokenTally,
) -> _T:
    """
    Ask the LLM for a stage's answer, asking again when it got no whole answer:
    the response did not parse, or the provider failed in a way that may pass.

    A response is the whole answer when ``parse`` accepts it, whatever its
    finish_reason: an answer cut short cannot parse. Any other response is
    forgotten by the provider, so it is never served again from a response
    cache, and the same call is made again. A complete first response is used
    as is.

    A provider failure that may pass (LLMTransientError: a rate limit, a server
    error, a timeout) is asked again after a short wait. One that cannot pass
    (a rejected key, an unknown model) or whose kind is not known is raised at
    once. Both kinds of attempt count toward the same MAX_LLM_ATTEMPTS.

    Args:
        llm: The provider to ask
        sleep: Waits the given seconds before a call is made again
        stage: The stage key, named in the failure
        request: The keyword arguments of ``LLMProvider.complete``
        parse: Reads a response's content; raises IncompleteLLMResponseError
            when it is not the whole answer
        spent: Counts the tokens of every response received, used or not

    Returns:
        What ``parse`` made of the first whole answer

    Raises:
        IncompleteLLMResponseError: If the last attempt's response was incomplete
        LLMTransientError: If the last attempt met a provider failure that may
            pass; an LLMRateLimitError only when every attempt met the rate limit
    """
    # Why each attempt got no whole answer, in order
    failures: list[IncompleteLLMResponseError | LLMTransientError] = []
    for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
        try:
            response = llm.complete(**request)
        except LLMTransientError as exc:
            _logger.warning(
                "LLM request for %s failed, attempt %d of %d: %s",
                stage,
                attempt,
                MAX_LLM_ATTEMPTS,
                exc,
            )
            failures.append(exc)
            if attempt < MAX_LLM_ATTEMPTS:
                sleep(FIRST_RETRY_WAIT_SECONDS * 2 ** (attempt - 1))
            continue
        spent.add(response)
        try:
            return parse(response.content)
        except IncompleteLLMResponseError as exc:
            problem = f"{exc} (finish_reason={response.finish_reason})"
            _logger.warning(
                "Incomplete LLM response for %s, attempt %d of %d: %s",
                stage,
                attempt,
                MAX_LLM_ATTEMPTS,
                problem,
            )
            llm.forget(**{k: v for k, v in request.items() if k in _FORGET_KEYS})
            failures.append(IncompleteLLMResponseError(problem))
    raise no_whole_answer(stage, failures)


# The arguments of LLMProvider.complete that LLMProvider.forget also takes
_FORGET_KEYS = frozenset(
    {"system_prompt", "user_prompt", "model", "temperature", "max_tokens", "response_format"}
)


def failure_fields(exc: Exception) -> dict[str, Any]:
    """
    How a failed stage is reported on its result: the reason, and what kind of
    failure it was.

    - ``incomplete_response``: an LLM response stayed incomplete
    - ``provider_failed``: the LLM provider did not answer a request
    - ``provider_refused``: that provider failure is one any other text would
      meet too (it refuses the model's requests, or its rate limit turned
      every attempt away: a rate limit that reaches here was met by every
      attempt)

    With any of the three the reason is written for the run's caller; any
    other may quote an internal error.
    """
    return {
        "failure_reason": str(exc) or type(exc).__name__,
        "incomplete_response": isinstance(exc, IncompleteLLMResponseError),
        "provider_failed": isinstance(exc, LLMProviderError),
        "provider_refused": isinstance(exc, (LLMRequestRefusedError, LLMRateLimitError)),
    }
