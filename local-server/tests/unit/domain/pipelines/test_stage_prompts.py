"""
Unit tests for configurable stage prompts (#1317).

Covers the template helpers, and that the schema and individual extraction
pipelines send a configuration's prompt overrides while keeping the defaults
for every stage it leaves alone.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from types import SimpleNamespace

import pytest

from domain.extraction.prompts import INDIVIDUAL_EXTRACTION_STAGES
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.ports import LLMResponse
from domain.pipelines.schema_extraction.orchestrator import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
)
from domain.pipelines.schema_extraction.prompts import SCHEMA_EXTRACTION_STAGES
from domain.pipelines.stage_prompts import (
    StageDefinition,
    StagePrompt,
    render,
    resolve_stage_prompts,
    strip_defaults,
)

_STAGES = (
    StageDefinition(
        key="a",
        label="A",
        description="First",
        placeholders={"text": "The text"},
        default=StagePrompt(system="sys a", user="Text: {text}"),
    ),
    StageDefinition(
        key="b",
        label="B",
        description="Second",
        placeholders={},
        default=StagePrompt(system="sys b", user="user b"),
    ),
)


class TestRender:
    def test_fills_named_placeholders(self):
        assert render("Terms: {terms}\n{context}", {"terms": "A, B", "context": "ctx"}) == (
            "Terms: A, B\nctx"
        )

    def test_leaves_other_braces_literal(self):
        template = 'Return JSON: {"triples": []} for {text} and {unknown}'
        assert render(template, {"text": "T"}) == 'Return JSON: {"triples": []} for T and {unknown}'

    def test_brace_before_a_placeholder_stays(self):
        assert render("{{example}, ...}", {"example": '"A": "x"'}) == '{"A": "x", ...}'

    def test_values_are_not_rendered_again(self):
        assert render("{a} {b}", {"a": "{b}", "b": "B"}) == "{b} B"


class TestResolveStagePrompts:
    def test_defaults_without_overrides(self):
        resolved = resolve_stage_prompts(_STAGES, None)
        assert resolved == {"a": _STAGES[0].default, "b": _STAGES[1].default}

    def test_override_replaces_only_the_fields_it_sets(self):
        resolved = resolve_stage_prompts(_STAGES, {"a": {"system": "custom"}})
        assert resolved["a"] == StagePrompt(system="custom", user="Text: {text}")
        assert resolved["b"] == _STAGES[1].default

    def test_blank_and_malformed_overrides_fall_back(self):
        resolved = resolve_stage_prompts(_STAGES, {"a": {"system": "  ", "user": 3}, "b": "x"})
        assert resolved == {"a": _STAGES[0].default, "b": _STAGES[1].default}


class TestStripDefaults:
    def test_keeps_only_what_differs(self):
        overrides = {
            "a": {"system": "custom", "user": "Text: {text}"},
            "b": {"system": "sys b", "user": ""},
        }
        assert strip_defaults(_STAGES, overrides) == {"a": {"system": "custom"}}

    def test_null_stage_means_default(self):
        assert strip_defaults(_STAGES, {"a": None}) == {}

    def test_unknown_stage_is_rejected(self):
        with pytest.raises(ValueError, match="zzz"):
            strip_defaults(_STAGES, {"zzz": {"system": "x"}})

    def test_unknown_placeholder_is_rejected(self):
        with pytest.raises(ValueError, match=r"\{txt\}"):
            strip_defaults(_STAGES, {"a": {"user": "Text: {txt}"}})

    def test_json_braces_are_not_placeholders(self):
        overrides = {"a": {"user": 'Text: {text} -> {"triples": []}'}}
        assert strip_defaults(_STAGES, overrides) == overrides

    def test_every_default_uses_only_its_declared_placeholders(self):
        for stages in (SCHEMA_EXTRACTION_STAGES, INDIVIDUAL_EXTRACTION_STAGES):
            custom = {
                s.key: {"system": s.default.system + " ", "user": s.default.user + " "}
                for s in stages
            }
            assert set(strip_defaults(stages, custom)) == {s.key for s in stages}


class _RecordingLLM:
    """Returns a minimal valid reply per stage and records every prompt sent."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def complete_async(self, system_prompt, user_prompt, model, **kwargs):
        self.calls.append((system_prompt, user_prompt))
        if "Extract candidate classes" in user_prompt:
            content = '["Gateway"]'
        elif "relationships" in user_prompt:
            content = '{"relationships": [], "properties": []}'
        elif "ambiguous_terms" in user_prompt:
            content = '{"ambiguous_terms": []}'
        else:
            content = '{"Gateway": "An entry point."}'
        return LLMResponse(
            content=content,
            tokens_in=1,
            tokens_out=1,
            duration_ms=1,
            finish_reason="stop",
            model=model,
        )


def _schema_state() -> SchemaExtractionState:
    return SchemaExtractionState(
        run_id="run-1",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={"documents": ["The Gateway routes requests."], "model": "m"},
    )


class TestSchemaExtractionStagePrompts:
    def test_declares_its_stages(self):
        assert SchemaExtractionOrchestrator.STAGE_PROMPTS is SCHEMA_EXTRACTION_STAGES
        assert [s.key for s in SCHEMA_EXTRACTION_STAGES] == [
            "candidate_identification",
            "definition_synthesis",
            "placement",
            "connection_proposal",
            "disambiguation",
        ]

    @pytest.mark.asyncio
    async def test_configured_prompts_are_sent_and_others_keep_defaults(self):
        llm = _RecordingLLM()
        config = {
            "stage_prompts": {
                "candidate_identification": {
                    "system": "Custom identification system.",
                    "user": "Extract candidate classes from <<{chunk}>> as a JSON array.",
                },
            }
        }
        orchestrator = SchemaExtractionOrchestrator(llm_provider=llm, config=config)

        await orchestrator.execute(_schema_state())

        system, user = llm.calls[0]
        assert system == "Custom identification system."
        assert user == (
            "Extract candidate classes from <<The Gateway routes requests.>> as a JSON array."
        )
        definition_default = SCHEMA_EXTRACTION_STAGES[1].default
        assert llm.calls[1][0] == definition_default.system


class _RecordingExtraction:
    def __init__(self):
        self.kwargs: dict = {}

    def extract_triples(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(triples=[], warnings=[], metadata={}, failure_reason=None)


class TestIndividualExtractionStagePrompts:
    def test_declares_its_stages(self):
        assert IndividualExtractionOrchestrator.STAGE_PROMPTS is INDIVIDUAL_EXTRACTION_STAGES
        assert [s.key for s in INDIVIDUAL_EXTRACTION_STAGES] == [
            "identify_individuals",
            "derive_relationships",
        ]

    @pytest.mark.asyncio
    async def test_configured_prompts_reach_the_extraction_service(self):
        extraction = _RecordingExtraction()
        overrides = {"identify_individuals": {"system": "Custom."}}
        orchestrator = IndividualExtractionOrchestrator(
            llm_provider=None,
            extraction_service=extraction,
            config={"stage_prompts": overrides},
        )
        state = IndividualExtractionState(
            run_id="run-1",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data={"text": "Nextflow runs pipelines.", "ontology_id": "tax-1", "model": "m"},
        )

        await orchestrator.execute(state)

        assert extraction.kwargs["stage_prompts"] == overrides
