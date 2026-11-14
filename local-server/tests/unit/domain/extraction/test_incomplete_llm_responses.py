"""
Unit tests for incomplete LLM responses in triple extraction.

A response that is not the model's whole answer (its content is not the JSON
asked for: cut short by a provider error or the output limit, or another
shape) says nothing about the text. The extraction asks again a bounded number
of times and, if no attempt completes, fails where the caller can see it
instead of returning an empty success.
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
from domain.extraction.exceptions import InvalidInputError
from domain.extraction.llm_calls import MAX_LLM_ATTEMPTS as _MAX_LLM_ATTEMPTS
from domain.extraction.services import ExtractionService
from domain.pipelines.ports import LLMResponse

TEXT = "Nextflow runs on Slurm."


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


class _ScriptedLLM:
    """
    Returns the scripted (content, finish_reason) responses in order, and
    records the requests it is told to forget.
    """

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls: list[str] = []
        self.forgotten: list[dict] = []

    def complete(self, system_prompt, user_prompt, model, **kwargs):
        self.calls.append(user_prompt)
        content, finish_reason = self._responses.pop(0)
        return LLMResponse(
            content=content,
            tokens_in=10,
            tokens_out=5,
            duration_ms=1.0,
            finish_reason=finish_reason,
            model=model,
        )

    def forget(self, **request):
        self.forgotten.append(request)


class _CachingLLM:
    """
    A provider that keeps its response to each request, as OpenRouterProvider
    does, in front of a scripted model.
    """

    def __init__(self, *responses):
        self.model = _ScriptedLLM(*responses)
        self._kept: dict[str, LLMResponse] = {}

    def complete(self, system_prompt, user_prompt, model, **kwargs):
        if user_prompt not in self._kept:
            self._kept[user_prompt] = self.model.complete(system_prompt, user_prompt, model)
        return self._kept[user_prompt]

    def forget(self, system_prompt, user_prompt, model, **_):
        self._kept.pop(user_prompt, None)


class _BareOntologyRepo:
    """A taxonomy with no classes or relationship types."""

    def get_taxonomy(self, taxonomy_id):
        if taxonomy_id == "missing":
            return None
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


def _extract(llm, ontology_id="tax-1"):
    run_repo = _RunRepo()
    service = ExtractionService(
        ontology_repo=_BareOntologyRepo(),
        embedding_service=None,
        llm=llm,
        nlp=None,
        reference_sources=[],
        event_publisher=_Publisher(),
        extraction_repo=None,
        extraction_run_repo=run_repo,
    )
    result = service.extract_triples(TEXT, ontology_id, "model-1", 0.0)
    return result, run_repo.run


def _labels(result):
    return [(t["subject"]["label"], t["predicate"]["label"]) for t in result.triples]


EXPECTED = [("Nextflow", "is_a"), ("Slurm", "is_a"), ("Nextflow", "runs on")]


class TestIncompleteResponseIsAskedAgain:
    def test_complete_first_responses_are_used_without_asking_again(self):
        llm = _ScriptedLLM((IDENTIFIED, "stop"), (RELATED, "stop"))
        result, run = _extract(llm)
        assert _labels(result) == EXPECTED
        assert len(llm.calls) == 2
        assert result.failure_reason is None
        assert result.incomplete_response is False
        assert result.metadata["tokens_used"] == 30
        assert run.status == ExtractionRunStatus.COMPLETED
        assert llm.forgotten == []

    @pytest.mark.parametrize(
        "content, finish_reason",
        [
            (CUT_SHORT, "error"),  # the provider failed part-way
            (CUT_SHORT, "length"),  # cut at the output limit (OpenAI, OpenRouter)
            (CUT_SHORT, "max_tokens"),  # cut at the output limit (Anthropic)
            (CUT_SHORT, "stop"),  # JSON cut before any object closes
            (IDENTIFIED[:-2], "stop"),  # JSON that does not parse
            ("I could not find anything.", "stop"),  # no JSON at all
            (None, "stop"),  # no content
            # JSON that parses but is not the shape asked for
            ("{}", "stop"),
            ('{"individuals": [{"label": "Nextflow"}]}', "stop"),
            ('{"error": {"message": "overloaded"}}', "stop"),
            ('{"triples": null}', "stop"),
            (json.dumps([_typing("Nextflow")]), "stop"),  # a top-level array
            ("[]", None),
        ],
    )
    def test_incomplete_identify_response_then_a_good_one_yields_the_good_ones_triples(
        self, content, finish_reason
    ):
        llm = _ScriptedLLM((content, finish_reason), (IDENTIFIED, "stop"), (RELATED, "stop"))
        result, run = _extract(llm)
        assert _labels(result) == EXPECTED
        assert result.failure_reason is None
        assert result.warnings == []
        assert run.status == ExtractionRunStatus.COMPLETED
        # The retry repeats the same prompt
        assert llm.calls[0] == llm.calls[1]
        assert len(llm.calls) == 3
        # The provider was told to forget exactly the request it answered badly
        (forgotten,) = llm.forgotten
        assert forgotten["user_prompt"] == llm.calls[0]
        assert (forgotten["max_tokens"], forgotten["response_format"]) == (8000, "json")

    @pytest.mark.parametrize("finish_reason", ["length", "max_tokens", "error", None])
    def test_a_response_that_parses_is_the_whole_answer_whatever_its_finish_reason(
        self, finish_reason
    ):
        # An object cut short cannot parse, so one that does was not cut short
        llm = _ScriptedLLM((IDENTIFIED, finish_reason), (RELATED, finish_reason))
        result, _ = _extract(llm)
        assert _labels(result) == EXPECTED
        assert result.failure_reason is None
        assert len(llm.calls) == 2

    def test_incomplete_relationship_response_then_a_good_one_keeps_the_relationships(self):
        llm = _ScriptedLLM((IDENTIFIED, "stop"), (RELATED[:30], "length"), (RELATED, "stop"))
        result, _ = _extract(llm)
        assert _labels(result) == EXPECTED
        assert result.failure_reason is None
        assert llm.calls[1] == llm.calls[2]

    def test_no_triples_is_a_complete_answer(self):
        llm = _ScriptedLLM(('{"triples": []}', "stop"))
        result, run = _extract(llm)
        assert result.triples == []
        assert result.failure_reason is None
        assert len(llm.calls) == 1
        assert run.status == ExtractionRunStatus.COMPLETED


class TestResponseThatNeverCompletes:
    @pytest.mark.parametrize(
        "content, finish_reason, problem",
        [
            (CUT_SHORT, "error", "it holds no complete JSON object (finish_reason=error)"),
            (CUT_SHORT, "length", "it holds no complete JSON object (finish_reason=length)"),
            (IDENTIFIED[:-2], "stop", "its JSON does not parse"),
            ("nothing here", "stop", "it holds no complete JSON object (finish_reason=stop)"),
            ("{}", "stop", "its JSON has no triples list (finish_reason=stop)"),
            ('{"triples": null}', "stop", "its JSON has no triples list (finish_reason=stop)"),
            ("[]", None, "it holds no complete JSON object (finish_reason=None)"),
        ],
    )
    def test_is_a_failure_the_caller_can_see_not_an_empty_success(
        self, content, finish_reason, problem
    ):
        llm = _ScriptedLLM(*[(content, finish_reason)] * _MAX_LLM_ATTEMPTS)
        result, run = _extract(llm)
        assert len(llm.calls) == _MAX_LLM_ATTEMPTS
        assert result.triples == []
        assert result.failure_reason.startswith(
            "The LLM response for identify_individuals was still incomplete after"
            f" {_MAX_LLM_ATTEMPTS} attempts: {problem}"
        )
        assert result.warnings == [f"Extraction failed: {result.failure_reason}"]
        assert result.incomplete_response is True
        assert run.status == ExtractionRunStatus.FAILED
        # Every rejected response was dropped, the last one too
        assert len(llm.forgotten) == _MAX_LLM_ATTEMPTS

    def test_relationship_pass_that_never_completes_fails_the_extraction(self):
        llm = _ScriptedLLM((IDENTIFIED, "stop"), *[(RELATED[:30], "error")] * _MAX_LLM_ATTEMPTS)
        result, run = _extract(llm)
        assert result.triples == []
        assert result.failure_reason.startswith(
            "The LLM response for derive_relationships was still incomplete after"
        )
        assert "finish_reason=error" in result.failure_reason
        assert run.status == ExtractionRunStatus.FAILED
        # 1 identify call, then every attempt of the derive call
        assert len(llm.calls) == 1 + _MAX_LLM_ATTEMPTS

    def test_another_failure_is_not_an_incomplete_response(self):
        class _Broken(_ScriptedLLM):
            def complete(self, *args, **kwargs):
                raise RuntimeError("OpenRouter rate limit exceeded")

        result, run = _extract(_Broken())
        assert result.failure_reason == "OpenRouter rate limit exceeded"
        assert result.incomplete_response is False
        assert run.status == ExtractionRunStatus.FAILED


class TestProviderThatKeepsResponses:
    """A response the extraction rejects is never served again from the provider's cache."""

    @pytest.mark.parametrize(
        "rejected", ["{}", '{"triples": null}', '{"relationships": []}', "null", "[]"]
    )
    def test_rejected_then_good_makes_two_model_calls_and_does_not_poison_a_later_run(
        self, rejected
    ):
        llm = _CachingLLM((rejected, "stop"), (IDENTIFIED, "stop"), (RELATED, "stop"))
        result, _ = _extract(llm)
        assert _labels(result) == EXPECTED
        # identify: the rejected answer, then the good one; derive: one call
        assert len(llm.model.calls) == 3
        assert llm.model.calls[0] == llm.model.calls[1]

        # A later run of the same text is answered from the cache with the good answers
        later, _ = _extract(llm)
        assert _labels(later) == EXPECTED
        assert len(llm.model.calls) == 3

    def test_a_run_that_never_completes_leaves_nothing_cached_for_the_next(self):
        llm = _CachingLLM(
            *[("{}", "stop")] * _MAX_LLM_ATTEMPTS, (IDENTIFIED, "stop"), (RELATED, "stop")
        )
        failed, _ = _extract(llm)
        assert failed.incomplete_response is True
        assert len(llm.model.calls) == _MAX_LLM_ATTEMPTS

        later, _ = _extract(llm)
        assert _labels(later) == EXPECTED
        assert len(llm.model.calls) == _MAX_LLM_ATTEMPTS + 2


class TestUnknownOntology:
    def test_is_invalid_input_before_any_model_call(self):
        llm = _ScriptedLLM()
        with pytest.raises(InvalidInputError, match="Ontology missing not found"):
            _extract(llm, ontology_id="missing")
        assert llm.calls == []
