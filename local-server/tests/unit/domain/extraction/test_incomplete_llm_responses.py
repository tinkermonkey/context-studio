"""
Unit tests for incomplete LLM responses in triple extraction.

A response that is not the model's whole answer (it stopped on a provider
error or at the output limit, or its content is not the JSON asked for) says
nothing about the text. The extraction asks again a bounded number of times
and, if no attempt completes, fails where the caller can see it instead of
returning an empty success.
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
    """Returns the scripted (content, finish_reason) responses in order."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls: list[str] = []

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
    result = service.extract_triples(TEXT, "tax-1", "model-1", 0.0)
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
        assert result.metadata["tokens_used"] == 30
        assert run.status == ExtractionRunStatus.COMPLETED

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

    def test_a_response_that_parses_but_stopped_early_is_not_trusted(self):
        fewer = json.dumps({"triples": [_typing("Nextflow")]})
        llm = _ScriptedLLM((fewer, "length"), (IDENTIFIED, "stop"), (RELATED, "stop"))
        result, _ = _extract(llm)
        assert _labels(result) == EXPECTED

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
            (CUT_SHORT, "error", "it stopped early (finish_reason=error)"),
            (CUT_SHORT, "length", "it stopped early (finish_reason=length)"),
            (IDENTIFIED[:-2], "stop", "its JSON does not parse"),
            (CUT_SHORT, "stop", "it holds no complete JSON object"),
            ("nothing here", "stop", "it holds no complete JSON object"),
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
            f"The LLM response was still incomplete after {_MAX_LLM_ATTEMPTS} attempts: {problem}"
        )
        assert result.warnings == [f"Extraction failed: {result.failure_reason}"]
        assert run.status == ExtractionRunStatus.FAILED

    def test_relationship_pass_that_never_completes_fails_the_extraction(self):
        llm = _ScriptedLLM((IDENTIFIED, "stop"), *[(RELATED[:30], "error")] * _MAX_LLM_ATTEMPTS)
        result, run = _extract(llm)
        assert result.triples == []
        assert "finish_reason=error" in result.failure_reason
        assert run.status == ExtractionRunStatus.FAILED
