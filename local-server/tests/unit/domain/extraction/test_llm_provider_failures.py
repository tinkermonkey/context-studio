"""
Unit tests for LLM provider failures in triple extraction.

A provider that fails to answer says nothing about the text. A failure that may
pass (a rate limit, a server error, a timeout) is asked again after a short
wait, within the same attempts as an incomplete response. One that cannot pass
(a rejected key, an unknown model) is not asked again. A failure that any other
text would meet too is reported as such, so a run of many chunks can stop. The
tokens of every response count, whether or not the extraction used it.
"""

import json
import os
import sys
from types import SimpleNamespace

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.extraction.entities import ExtractionRunStatus
from domain.extraction.services import _MAX_LLM_ATTEMPTS, ExtractionService
from domain.pipelines.exceptions import (
    LLMRateLimitError,
    LLMRequestRefusedError,
    LLMTransientError,
)
from domain.pipelines.ports import LLMResponse

TEXT = "Nextflow runs on Slurm."

# What every scripted response costs: 10 tokens in, 5 out
RESPONSE_TOKENS = 15


def _typing(label):
    return {
        "subject": {"kind": "individual", "label": label},
        "predicate": {"label": "is_a"},
        "object": {"kind": "class", "label": "Tool"},
        "confidence": 0.9,
        "provenance": {"raw": label},
    }


IDENTIFIED = json.dumps({"triples": [_typing("Nextflow"), _typing("Slurm")]})
RELATED = json.dumps(
    {
        "triples": [
            {
                "subject": {"kind": "individual", "label": "Nextflow"},
                "predicate": {"label": "runs on"},
                "object": {"kind": "individual", "label": "Slurm"},
                "confidence": 0.8,
                "provenance": {"raw": "runs on"},
            }
        ]
    }
)
CUT_SHORT = IDENTIFIED[:40]

SERVER_ERROR = LLMTransientError("OpenRouter API error: 503")
TIMEOUT = LLMTransientError("OpenRouter did not answer: ReadTimeout")
RATE_LIMIT = LLMRateLimitError("OpenRouter rate limit exceeded")
BAD_KEY = LLMRequestRefusedError("OpenRouter API key is invalid or unauthorized")
NO_MODEL = LLMRequestRefusedError("Model not found on OpenRouter: model-1")


class _ScriptedLLM:
    """
    Answers each call with the next scripted step: an exception is raised, a
    string is returned as a complete response's content.
    """

    def __init__(self, *steps):
        self._steps = list(steps)
        self.calls: list[str] = []
        self.forgotten: list[dict] = []

    def complete(self, system_prompt, user_prompt, model, **kwargs):
        self.calls.append(user_prompt)
        step = self._steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return LLMResponse(
            content=step,
            tokens_in=10,
            tokens_out=5,
            duration_ms=1.0,
            finish_reason="stop",
            model=model,
        )

    def forget(self, **request):
        self.forgotten.append(request)


class _BareOntologyRepo:
    """A taxonomy with no classes or relationship types."""

    def get_taxonomy(self, taxonomy_id):
        return SimpleNamespace(id=taxonomy_id, title="Tools")

    def list_concept_schemes(self, taxonomy_id, limit=None):
        return []

    def list_property_definitions(self, *args, **kwargs):
        return []


class _RunRepo:
    def __init__(self):
        self.run = None

    def save_extraction_run(self, run):
        self.run = run

    def update_extraction_run(self, run):
        self.run = run


class _Publisher:
    def publish(self, event):
        return []


def _extract(llm):
    """Run one extraction; returns (result, stored run, the waits between attempts)."""
    run_repo = _RunRepo()
    waits: list[float] = []
    service = ExtractionService(
        ontology_repo=_BareOntologyRepo(),
        embedding_service=None,
        llm=llm,
        nlp=None,
        reference_sources=[],
        event_publisher=_Publisher(),
        extraction_repo=None,
        extraction_run_repo=run_repo,
        sleep=waits.append,
    )
    result = service.extract_triples(TEXT, "tax-1", "model-1", 0.0)
    return result, run_repo.run, waits


def _labels(result):
    return [(t["subject"]["label"], t["predicate"]["label"]) for t in result.triples]


EXPECTED = [("Nextflow", "is_a"), ("Slurm", "is_a"), ("Nextflow", "runs on")]


class TestTransientFailureIsAskedAgain:
    @pytest.mark.parametrize("failure", [SERVER_ERROR, TIMEOUT, RATE_LIMIT])
    def test_a_failure_that_may_pass_then_an_answer_yields_the_answers_triples(self, failure):
        llm = _ScriptedLLM(failure, IDENTIFIED, RELATED)
        result, run, waits = _extract(llm)
        assert _labels(result) == EXPECTED
        assert result.failure_reason is None
        assert result.warnings == []
        assert run.status == ExtractionRunStatus.COMPLETED
        # The same request is made again, after one wait
        assert llm.calls[0] == llm.calls[1]
        assert len(llm.calls) == 3
        assert len(waits) == 1 and waits[0] > 0
        # No response was rejected, so there is none to forget
        assert llm.forgotten == []

    def test_the_relationship_pass_is_asked_again_too(self):
        llm = _ScriptedLLM(IDENTIFIED, SERVER_ERROR, RELATED)
        result, _, waits = _extract(llm)
        assert _labels(result) == EXPECTED
        assert llm.calls[1] == llm.calls[2]
        assert len(waits) == 1

    def test_each_wait_is_longer_than_the_one_before_and_all_are_short(self):
        llm = _ScriptedLLM(SERVER_ERROR, SERVER_ERROR, IDENTIFIED, RELATED)
        result, _, waits = _extract(llm)
        assert _labels(result) == EXPECTED
        assert len(waits) == _MAX_LLM_ATTEMPTS - 1
        assert waits == sorted(waits) and waits[0] < waits[-1]
        assert sum(waits) <= 10

    def test_an_incomplete_response_is_asked_again_without_waiting(self):
        llm = _ScriptedLLM(CUT_SHORT, IDENTIFIED, RELATED)
        result, _, waits = _extract(llm)
        assert _labels(result) == EXPECTED
        assert waits == []

    def test_failures_and_incomplete_responses_share_the_attempts(self):
        llm = _ScriptedLLM(SERVER_ERROR, CUT_SHORT, IDENTIFIED, RELATED)
        result, _, _ = _extract(llm)
        assert _labels(result) == EXPECTED
        assert len(llm.calls) == _MAX_LLM_ATTEMPTS + 1

        llm = _ScriptedLLM(CUT_SHORT, SERVER_ERROR, CUT_SHORT, IDENTIFIED, RELATED)
        result, run, _ = _extract(llm)
        assert len(llm.calls) == _MAX_LLM_ATTEMPTS
        assert result.triples == []
        assert result.incomplete_response is True
        assert run.status == ExtractionRunStatus.FAILED


class TestFailureThatNeverPasses:
    def test_a_server_error_on_every_attempt_fails_this_text_only(self):
        llm = _ScriptedLLM(*[SERVER_ERROR] * _MAX_LLM_ATTEMPTS)
        result, run, waits = _extract(llm)
        assert len(llm.calls) == _MAX_LLM_ATTEMPTS
        # No wait after the last attempt
        assert len(waits) == _MAX_LLM_ATTEMPTS - 1
        assert result.triples == []
        assert result.failure_reason == (
            "The LLM request for identify_individuals still failed after"
            f" {_MAX_LLM_ATTEMPTS} attempts: OpenRouter API error: 503"
        )
        assert result.warnings == [f"Extraction failed: {result.failure_reason}"]
        assert result.incomplete_response is False
        # The reason is the provider's, written for the caller
        assert result.provider_failed is True
        # Another text may be answered: the provider may be back by then
        assert result.provider_refused is False
        assert run.status == ExtractionRunStatus.FAILED

    def test_a_rate_limit_on_every_attempt_is_a_refusal_any_text_would_meet(self):
        llm = _ScriptedLLM(*[RATE_LIMIT] * _MAX_LLM_ATTEMPTS)
        result, run, _ = _extract(llm)
        assert len(llm.calls) == _MAX_LLM_ATTEMPTS
        assert result.failure_reason == (
            "The LLM request for identify_individuals still failed after"
            f" {_MAX_LLM_ATTEMPTS} attempts: OpenRouter rate limit exceeded"
        )
        assert result.provider_failed is True
        assert result.provider_refused is True
        assert result.incomplete_response is False
        assert run.status == ExtractionRunStatus.FAILED


class TestAttemptsThatFailedInDifferentWays:
    """
    No one failure outlasted the attempts, so the extraction says so and
    reports the last. A rate limit that was not met by every attempt is no
    refusal any other text would meet: it was never asked again.
    """

    @staticmethod
    def _mixed(last):
        return (
            "The LLM gave no complete answer for identify_individuals in"
            f" {_MAX_LLM_ATTEMPTS} attempts that failed in different ways, the last with: {last}"
        )

    @pytest.mark.parametrize(
        "attempts",
        [
            (SERVER_ERROR, SERVER_ERROR, RATE_LIMIT),
            (CUT_SHORT, CUT_SHORT, RATE_LIMIT),
            (RATE_LIMIT, SERVER_ERROR, RATE_LIMIT),
            (RATE_LIMIT, CUT_SHORT, RATE_LIMIT),
        ],
        ids=["503-503-429", "cut-cut-429", "429-503-429", "429-cut-429"],
    )
    def test_a_rate_limit_not_met_by_every_attempt_is_no_refusal(self, attempts):
        llm = _ScriptedLLM(*attempts)
        result, run, _ = _extract(llm)
        assert len(llm.calls) == _MAX_LLM_ATTEMPTS
        assert result.triples == []
        assert result.failure_reason == self._mixed("OpenRouter rate limit exceeded")
        assert "still failed after" not in result.failure_reason
        assert result.provider_failed is True
        assert result.provider_refused is False
        assert result.incomplete_response is False
        assert run.status == ExtractionRunStatus.FAILED

    def test_rate_limits_then_a_server_error_reports_the_server_error(self):
        llm = _ScriptedLLM(RATE_LIMIT, RATE_LIMIT, SERVER_ERROR)
        result, _, _ = _extract(llm)
        assert result.failure_reason == self._mixed("OpenRouter API error: 503")
        assert result.provider_failed is True
        assert result.provider_refused is False

    def test_provider_failures_then_an_incomplete_response_is_an_incomplete_response(self):
        llm = _ScriptedLLM(RATE_LIMIT, SERVER_ERROR, CUT_SHORT)
        result, _, _ = _extract(llm)
        assert result.failure_reason.startswith(
            self._mixed("it holds no complete JSON object")[:-1]
        )
        assert "still incomplete after" not in result.failure_reason
        assert result.incomplete_response is True
        assert result.provider_failed is False
        assert result.provider_refused is False

    def test_two_kinds_of_failure_that_may_pass_are_one_way_of_failing(self):
        # A server error and a timeout are both "the provider did not answer"
        llm = _ScriptedLLM(SERVER_ERROR, TIMEOUT, SERVER_ERROR)
        result, _, _ = _extract(llm)
        assert result.failure_reason == (
            "The LLM request for identify_individuals still failed after"
            f" {_MAX_LLM_ATTEMPTS} attempts: OpenRouter API error: 503"
        )


class TestFailureThatCannotPass:
    @pytest.mark.parametrize("refusal", [BAD_KEY, NO_MODEL])
    def test_a_refusal_is_not_asked_again(self, refusal):
        llm = _ScriptedLLM(refusal, IDENTIFIED, RELATED)
        result, run, waits = _extract(llm)
        assert len(llm.calls) == 1
        assert waits == []
        assert result.triples == []
        assert result.failure_reason == str(refusal)
        assert result.provider_failed is True
        assert result.provider_refused is True
        assert result.incomplete_response is False
        assert run.status == ExtractionRunStatus.FAILED

    def test_a_failure_of_no_known_kind_is_not_asked_again(self):
        llm = _ScriptedLLM(RuntimeError("OpenRouter response missing 'usage' field"), IDENTIFIED)
        result, _, waits = _extract(llm)
        assert len(llm.calls) == 1
        assert waits == []
        assert result.failure_reason == "OpenRouter response missing 'usage' field"
        # Its reason is not known to be written for the caller
        assert result.provider_failed is False
        assert result.provider_refused is False

    def test_a_complete_extraction_is_no_refusal(self):
        result, _, _ = _extract(_ScriptedLLM(IDENTIFIED, RELATED))
        assert result.failure_reason is None
        assert result.provider_failed is False
        assert result.provider_refused is False


class TestTokensOfEveryAttemptCount:
    def test_identify_answered_and_derive_never_complete_counts_all_four_responses(self):
        llm = _ScriptedLLM(IDENTIFIED, *[RELATED[:30]] * _MAX_LLM_ATTEMPTS)
        result, run, _ = _extract(llm)
        assert result.incomplete_response is True
        assert len(llm.calls) == 1 + _MAX_LLM_ATTEMPTS
        spent = (1 + _MAX_LLM_ATTEMPTS) * RESPONSE_TOKENS
        assert result.metadata["tokens_used"] == spent
        assert run.tokens_used == spent
        assert run.status == ExtractionRunStatus.FAILED

    def test_identify_never_complete_counts_its_responses(self):
        llm = _ScriptedLLM(*[CUT_SHORT] * _MAX_LLM_ATTEMPTS)
        result, run, _ = _extract(llm)
        assert result.metadata["tokens_used"] == _MAX_LLM_ATTEMPTS * RESPONSE_TOKENS
        assert run.tokens_used == _MAX_LLM_ATTEMPTS * RESPONSE_TOKENS

    def test_a_refusal_after_identify_keeps_what_identify_cost(self):
        llm = _ScriptedLLM(IDENTIFIED, BAD_KEY)
        result, run, _ = _extract(llm)
        assert result.provider_refused is True
        assert result.metadata["tokens_used"] == RESPONSE_TOKENS
        assert run.tokens_used == RESPONSE_TOKENS

    def test_a_call_that_raised_has_no_tokens_to_count(self):
        llm = _ScriptedLLM(*[SERVER_ERROR] * _MAX_LLM_ATTEMPTS)
        result, run, _ = _extract(llm)
        assert result.metadata["tokens_used"] == 0
        assert run.tokens_used == 0

    def test_a_rejected_response_counts_in_an_extraction_that_then_completes(self):
        llm = _ScriptedLLM(CUT_SHORT, SERVER_ERROR, IDENTIFIED, RELATED)
        result, run, _ = _extract(llm)
        assert _labels(result) == EXPECTED
        assert result.metadata["tokens_used"] == 3 * RESPONSE_TOKENS
        assert run.tokens_used == 3 * RESPONSE_TOKENS
