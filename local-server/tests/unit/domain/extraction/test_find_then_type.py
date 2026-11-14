"""
Unit tests for find-then-type extraction: the find and type calls, their
prompts and parsers, and the service methods over them.

Each call is one LLM request under the shared retry rules; a failure is
reported on the result, never read as "mentions nothing" or "not something to
record".
"""

import json
import os
import sys
from types import SimpleNamespace

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.extraction import find_then_type
from domain.extraction.entities import Mention
from domain.extraction.exceptions import (
    ExtractionError,
    IncompleteLLMResponseError,
    InvalidInputError,
)
from domain.extraction.find_then_type import (
    CONTEXT_WINDOW_CHARS,
    CatalogClass,
    build_typing_prompt,
    kinds_grounding,
    mention_context,
    parse_mentions,
    parse_typing,
    typing_triple,
)
from domain.extraction.llm_calls import MAX_LLM_ATTEMPTS
from domain.extraction.prompts import FIND_THEN_TYPE_STAGES, TYPE_MENTION
from domain.extraction.services import ExtractionService
from domain.pipelines.exceptions import LLMRateLimitError, LLMRequestRefusedError
from domain.pipelines.ports import LLMResponse
from domain.pipelines.stage_prompts import resolve_stage_prompts

TEXT = "Workhorse is a smart reverse proxy. The team wants to reduce load on Puma."
PROMPTS = resolve_stage_prompts(FIND_THEN_TYPE_STAGES, None)
CLASSES = [
    CatalogClass("technology.systemsoftware", "System Software", "Technology", "Software run."),
    CatalogClass("application.component", "Component", "Application", "A unit of software."),
    CatalogClass("motivation.goal", "Goal", "Motivation", "An end state someone wants."),
]


def _found(*mentions):
    return json.dumps({"mentions": list(mentions)})


WORKHORSE = {"name": "Workhorse", "kind": "thing", "quote": "Workhorse is a smart reverse proxy"}
GOAL = {
    "name": "Reduce load on Puma",
    "kind": "statement",
    "quote": "The team wants to reduce load on Puma",
}


class _ScriptedLLM:
    """Answers with the scripted contents (or raises the scripted errors) in order."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests: list[dict] = []
        self.forgotten: list[dict] = []

    def complete(self, **request):
        self.requests.append(request)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return LLMResponse(
            content=response,
            tokens_in=100,
            tokens_out=10,
            duration_ms=1.0,
            finish_reason="stop",
            model=request["model"],
        )

    def forget(self, **request):
        self.forgotten.append(request)


def _no_sleep(_seconds):
    return None


class TestParseMentions:
    def test_mentions_are_read_with_their_passages_placed(self):
        mentions, warnings = parse_mentions(_found(WORKHORSE, GOAL), TEXT)

        assert [(m.name, m.kind) for m in mentions] == [
            ("Workhorse", "thing"),
            ("Reduce load on Puma", "statement"),
        ]
        assert TEXT[mentions[0].start : mentions[0].end] == "Workhorse is a smart reverse proxy"
        assert TEXT[mentions[1].start : mentions[1].end] == "The team wants to reduce load on Puma"
        assert warnings == []

    def test_a_quote_that_is_not_in_the_text_leaves_the_mention_without_a_passage(self):
        mentions, warnings = parse_mentions(
            _found({"name": "Gitaly", "kind": "thing", "quote": "Gitaly stores repositories"}), TEXT
        )

        assert mentions == [Mention("Gitaly", "thing", None, None, None)]
        assert warnings == ["The passage of 1 of 1 mentions was not found in the text"]

    def test_a_mention_without_a_name_is_skipped_and_an_unknown_kind_is_a_thing(self):
        mentions, _ = parse_mentions(
            _found(
                {"name": " ", "quote": "x"}, {"name": "Puma", "kind": "server"}, "not a mention"
            ),
            TEXT,
        )

        assert [(m.name, m.kind) for m in mentions] == [("Puma", "thing")]

    @pytest.mark.parametrize(
        "items",
        [["Workhorse", "Puma"], [{"label": "Workhorse"}], [{"name": None, "quote": "Puma"}]],
    )
    def test_an_answer_whose_items_are_all_unusable_is_not_no_mentions(self, items):
        with pytest.raises(IncompleteLLMResponseError, match="has a name"):
            parse_mentions(_found(*items), TEXT)

    def test_an_answer_wrapped_in_a_code_fence_is_read(self):
        mentions, _ = parse_mentions(f"```json\n{_found(WORKHORSE)}\n```", TEXT)

        assert [m.name for m in mentions] == ["Workhorse"]

    @pytest.mark.parametrize(
        "content, problem",
        [
            ("", "it holds no complete JSON object"),
            ('{"mentions": [{"name": "Work', "it holds no complete JSON object"),
            ('{"mentions": [}', "its JSON does not parse"),
            ("{}", "its JSON has no mentions list"),
            ('{"mentions": "none"}', "its JSON has no mentions list"),
        ],
    )
    def test_an_answer_that_is_not_a_mentions_list_is_incomplete(self, content, problem):
        with pytest.raises(IncompleteLLMResponseError, match=problem):
            parse_mentions(content, TEXT)

    def test_no_mentions_is_a_whole_answer(self):
        assert parse_mentions('{"mentions": []}', TEXT) == ([], [])


class TestParseTyping:
    REFS = {"motivation.goal": "motivation.goal", "application.component": "application.Component"}

    def test_a_listed_class_is_returned_as_the_catalog_writes_it(self):
        answer = '{"class": "Application.component", "confidence": 0.8}'

        assert parse_typing(answer, self.REFS) == ("application.Component", 0.8)

    def test_none_means_not_something_to_record(self):
        assert parse_typing('{"class": "none", "confidence": 0.7}', self.REFS) == (None, 0.7)

    def test_a_class_the_catalog_does_not_list_is_not_an_answer(self):
        """Never read as none: the call is made again."""
        with pytest.raises(IncompleteLLMResponseError, match="does not list \\(business.actor\\)"):
            parse_typing('{"class": "business.actor", "confidence": 0.9}', self.REFS)

    @pytest.mark.parametrize("content", ["{}", '{"class": ""}', '{"class": null}', "[]", "goal"])
    def test_an_answer_that_names_no_class_is_incomplete(self, content):
        with pytest.raises(IncompleteLLMResponseError):
            parse_typing(content, self.REFS)

    @pytest.mark.parametrize(
        "confidence, read",
        [("1.7", 1.0), ("-2", 0.0), ('"high"', 0.5), ("null", 0.5)],
    )
    def test_confidence_is_kept_between_0_and_1(self, confidence, read):
        answer = f'{{"class": "motivation.goal", "confidence": {confidence}}}'

        assert parse_typing(answer, self.REFS) == ("motivation.goal", read)

    def test_a_missing_confidence_is_the_middle(self):
        assert parse_typing('{"class": "motivation.goal"}', self.REFS) == ("motivation.goal", 0.5)

    @pytest.mark.parametrize("confidence", ["NaN", "1" + "0" * 400, '"high"', "null"])
    def test_a_confidence_that_is_no_number_is_the_middle(self, confidence):
        answer = f'{{"class": "motivation.goal", "confidence": {confidence}}}'

        assert parse_typing(answer, self.REFS) == ("motivation.goal", 0.5)


class TestTypingPrompt:
    def test_the_catalog_lists_every_class_by_reference_with_its_definition(self):
        prompt = build_typing_prompt("DR", CLASSES, PROMPTS[TYPE_MENTION])

        assert "Ontology: DR" in prompt.system
        assert (
            "- application.component: Component (Application): A unit of software.\n"
            "- motivation.goal: Goal (Motivation): An end state someone wants.\n"
            "- technology.systemsoftware: System Software (Technology): Software run."
        ) in prompt.system
        assert "{catalog}" not in prompt.system
        assert prompt.class_refs == {c.reference: c.reference for c in CLASSES}

    def test_the_prompt_does_not_depend_on_the_order_the_classes_were_read_in(self):
        """The system prompt is a cache key and a cassette key."""
        one = build_typing_prompt("DR", CLASSES, PROMPTS[TYPE_MENTION])
        other = build_typing_prompt("DR", list(reversed(CLASSES)), PROMPTS[TYPE_MENTION])

        assert one.system == other.system

    def test_a_long_definition_is_cut_and_put_on_one_line(self):
        long = CatalogClass("a.b", "B", "A", "word\n  " * 200)

        prompt = build_typing_prompt("T", [long], PROMPTS[TYPE_MENTION])

        line = next(line for line in prompt.system.splitlines() if line.startswith("- a.b:"))
        assert len(line) < 300
        assert "  " not in line

    def test_a_title_of_several_lines_is_put_on_one(self):
        split = CatalogClass("a.b", "Bee\nhive", "A\n layer", "Where bees live.")

        prompt = build_typing_prompt("T", [split], PROMPTS[TYPE_MENTION])

        assert "- a.b: Bee hive (A layer): Where bees live." in prompt.system.splitlines()

    def test_the_find_prompt_is_told_the_kinds_the_ontology_records(self):
        grounding = kinds_grounding("DR", [("Motivation Layer", "Why."), ("API Layer", "")])

        assert grounding == (
            "Ontology: DR\n\nIt records elements of these kinds:\n"
            "- Motivation Layer: Why.\n- API Layer"
        )
        assert kinds_grounding("Bare", []) == "Ontology: Bare"


class TestMentionContextAndTriple:
    LONG = "a" * 3000 + "Workhorse proxies requests." + "b" * 3000

    def test_the_context_is_the_passage_with_a_window_on_each_side(self):
        mention = Mention("Workhorse", "thing", "Workhorse proxies requests.", 3000, 3027)

        context = mention_context(self.LONG, mention)

        assert context == (
            "a" * CONTEXT_WINDOW_CHARS + "Workhorse proxies requests." + "b" * CONTEXT_WINDOW_CHARS
        )

    def test_an_unplaced_mention_is_typed_around_where_its_name_appears(self):
        context = mention_context(self.LONG, Mention("Workhorse", "thing"))

        assert context.startswith("a" * CONTEXT_WINDOW_CHARS + "Workhorse")
        assert len(context) == 2 * CONTEXT_WINDOW_CHARS + len("Workhorse")

    def test_a_mention_whose_name_is_not_in_the_text_is_typed_at_its_start(self):
        assert mention_context(self.LONG, Mention("Reduce load", "statement")) == (
            "a" * CONTEXT_WINDOW_CHARS
        )

    def test_a_typed_mention_is_the_typing_triple_of_the_two_pass_shape(self):
        mention = Mention("Workhorse", "thing", "Workhorse is a smart reverse proxy", 0, 34)

        assert typing_triple(mention, "application.component", 0.9) == {
            "subject": {"kind": "individual", "id": "", "label": "Workhorse", "class_ids": []},
            "predicate": {"property_definition_id": "", "label": "is_a"},
            "object": {"kind": "class", "id": "", "label": "application.component"},
            "confidence": 0.9,
            "provenance": {"quote": "Workhorse is a smart reverse proxy", "start": 0, "end": 34},
        }


class TestFindMentions:
    def _find(self, llm):
        return find_then_type.find_mentions(
            llm, _no_sleep, TEXT, "Ontology: DR", "model-1", 0.0, PROMPTS["find_mentions"]
        )

    def test_one_call_lists_the_mentions(self):
        llm = _ScriptedLLM(_found(WORKHORSE, GOAL))

        result = self._find(llm)

        assert [m.name for m in result.mentions] == ["Workhorse", "Reduce load on Puma"]
        assert result.failure_reason is None
        assert result.metadata["tokens_used"] == 110
        assert result.metadata["model"] == "model-1"
        request = llm.requests[0]
        assert TEXT in request["user_prompt"] and "Ontology: DR" in request["user_prompt"]
        assert request["response_format"] == "json"

    def test_an_incomplete_answer_is_forgotten_and_asked_again(self):
        llm = _ScriptedLLM('{"mentions": [{"na', _found(WORKHORSE))

        result = self._find(llm)

        assert [m.name for m in result.mentions] == ["Workhorse"]
        assert len(llm.forgotten) == 1
        assert result.metadata["tokens_used"] == 220  # the answer that was cut short cost too

    def test_a_text_that_could_not_be_read_is_a_failure_not_an_empty_list(self):
        llm = _ScriptedLLM(*["{}"] * MAX_LLM_ATTEMPTS)

        result = self._find(llm)

        assert result.mentions == []
        assert result.incomplete_response is True
        assert "was still incomplete after 3 attempts" in result.failure_reason
        assert result.metadata["tokens_used"] == 330
        assert result.warnings == [f"Extraction failed: {result.failure_reason}"]

    def test_a_refused_provider_is_reported_as_one(self):
        llm = _ScriptedLLM(LLMRequestRefusedError("The anthropic provider rejected its API key"))

        result = self._find(llm)

        assert result.provider_failed is True and result.provider_refused is True
        assert result.failure_reason == "The anthropic provider rejected its API key"
        assert len(llm.requests) == 1


class TestTypeMention:
    MENTION = Mention("Workhorse", "thing", "Workhorse is a smart reverse proxy", 0, 34)

    def _type(self, llm, mention=MENTION):
        prompt = build_typing_prompt("DR", CLASSES, PROMPTS[TYPE_MENTION])
        return find_then_type.type_mention(llm, _no_sleep, prompt, TEXT, mention, "model-1", 0.0)

    def test_one_call_types_the_mention(self):
        llm = _ScriptedLLM('{"class": "application.component", "confidence": 0.9}')

        result = self._type(llm)

        assert (result.class_ref, result.confidence) == ("application.component", 0.9)
        assert result.failure_reason is None
        request = llm.requests[0]
        assert "- application.component: Component" in request["system_prompt"]
        assert "Candidate: Workhorse" in request["user_prompt"]
        assert '"Workhorse is a smart reverse proxy"' in request["user_prompt"]
        assert TEXT in request["user_prompt"]

    def test_the_system_prompt_is_the_same_for_every_mention(self):
        """So a provider can cache the catalog."""
        llm = _ScriptedLLM(
            '{"class": "none", "confidence": 1}', '{"class": "motivation.goal", "confidence": 1}'
        )

        self._type(llm)
        self._type(llm, Mention("Reduce load on Puma", "statement"))

        assert llm.requests[0]["system_prompt"] == llm.requests[1]["system_prompt"]
        assert llm.requests[0]["user_prompt"] != llm.requests[1]["user_prompt"]
        assert "(no passage)" in llm.requests[1]["user_prompt"]

    def test_none_is_an_answer_not_a_failure(self):
        result = self._type(_ScriptedLLM('{"class": "none", "confidence": 0.8}'))

        assert result.class_ref is None
        assert result.failure_reason is None

    def test_an_unlisted_class_is_asked_again(self):
        llm = _ScriptedLLM(
            '{"class": "business.actor", "confidence": 0.9}',
            '{"class": "motivation.goal", "confidence": 0.6}',
        )

        result = self._type(llm)

        assert result.class_ref == "motivation.goal"
        assert len(llm.forgotten) == 1

    def test_a_mention_that_could_not_be_typed_is_a_failure_not_none(self):
        llm = _ScriptedLLM(*['{"class": "business.actor"}'] * MAX_LLM_ATTEMPTS)

        result = self._type(llm)

        assert result.class_ref is None
        assert result.incomplete_response is True
        assert "does not list (business.actor)" in result.failure_reason
        assert result.metadata["tokens_used"] == 330

    def test_a_rate_limit_that_outlasts_every_attempt_is_a_refusal(self):
        llm = _ScriptedLLM(*[LLMRateLimitError("rate limit")] * MAX_LLM_ATTEMPTS)

        result = self._type(llm)

        assert result.provider_refused is True
        assert result.metadata["tokens_used"] == 0


# The service methods


def _cls(reference, title, description, derived=False):
    return SimpleNamespace(
        id=f"id-{reference}",
        title=title,
        identifier=reference.replace(".", "_"),
        description=description,
        derived=derived,
        external_references=[SimpleNamespace(identifier=reference)],
    )


class _Repo:
    """A taxonomy with two concept schemes and no relationship types."""

    SCHEMES = [
        SimpleNamespace(id="s-app", title="Application", description="Software the team wrote."),
        SimpleNamespace(id="s-mot", title="Motivation", description=None),
    ]
    CLASSES = {
        "s-app": [
            _cls("application.component", "Component", "A unit of software."),
            _cls("application.kit", "Kit", "Computed by the client.", derived=True),
        ],
        "s-mot": [_cls("motivation.goal", "Goal", "An end state someone wants.")],
    }

    def get_taxonomy(self, taxonomy_id):
        return None if taxonomy_id == "missing" else SimpleNamespace(id=taxonomy_id, title="DR")

    def list_concept_schemes(self, taxonomy_id, limit=None):
        return self.SCHEMES

    def list_classes(self, concept_scheme_id, limit=None):
        return self.CLASSES[concept_scheme_id]

    def list_property_definitions(self, *args, **kwargs):
        return []


def _service(llm):
    return ExtractionService(
        ontology_repo=_Repo(),
        embedding_service=None,
        llm=llm,
        nlp=None,
        reference_sources=[],
        event_publisher=None,
        extraction_repo=None,
        extraction_run_repo=None,
        sleep=_no_sleep,
    )


def _related(subject, predicate, obj):
    return json.dumps(
        {
            "triples": [
                {
                    "subject": {"kind": "individual", "label": subject},
                    "predicate": {"label": predicate},
                    "object": {"kind": "individual", "label": obj},
                    "confidence": 0.8,
                    "provenance": {"raw": "Workhorse"},
                }
            ]
        }
    )


TYPED = [
    typing_triple(Mention("Workhorse", "thing"), "application.component", 0.9),
    typing_triple(Mention("Puma", "thing"), "application.component", 0.9),
]


class TestServiceMethods:
    def test_find_tells_the_prompt_the_ontology_s_kinds(self):
        llm = _ScriptedLLM(_found(WORKHORSE))

        result = _service(llm).find_mentions(TEXT, "tax-1", "model-1", 0.0)

        assert [m.name for m in result.mentions] == ["Workhorse"]
        assert (
            "Ontology: DR\n\nIt records elements of these kinds:\n"
            "- Application: Software the team wrote.\n- Motivation"
        ) in llm.requests[0]["user_prompt"]

    def test_find_uses_a_configuration_s_prompt(self):
        llm = _ScriptedLLM(_found())
        prompts = {"find_mentions": {"system": "List the parts.", "user": "{text}"}}

        _service(llm).find_mentions(TEXT, "tax-1", "model-1", 0.0, prompts)

        assert llm.requests[0]["system_prompt"] == "List the parts."
        assert llm.requests[0]["user_prompt"] == TEXT

    def test_find_rejects_bad_input_before_calling_the_llm(self):
        service = _service(_ScriptedLLM())

        with pytest.raises(ExtractionError):
            service.find_mentions("  ", "tax-1", "model-1", 0.0)
        with pytest.raises(InvalidInputError):
            service.find_mentions(TEXT, "missing", "model-1", 0.0)
        with pytest.raises(ValueError):
            service.find_mentions(TEXT, "tax-1", "model-1", 3.0)

    def test_the_typing_prompt_lists_every_class_but_derived_ones(self):
        prompt = _service(_ScriptedLLM()).typing_prompt("tax-1")

        assert set(prompt.class_refs.values()) == {"application.component", "motivation.goal"}
        assert "- application.component: Component (Application): A unit of software." in (
            prompt.system
        )
        assert "application.kit" not in prompt.system

    def test_the_typing_prompt_of_a_missing_ontology_is_an_input_error(self):
        with pytest.raises(InvalidInputError):
            _service(_ScriptedLLM()).typing_prompt("missing")

    def test_type_mention_makes_the_call(self):
        service = _service(_ScriptedLLM('{"class": "motivation.goal", "confidence": 0.7}'))
        prompt = service.typing_prompt("tax-1")

        result = service.type_mention(prompt, TEXT, Mention("Reduce load", "statement"), "m", 0.0)

        assert result.class_ref == "motivation.goal"

    def test_relate_keeps_relationships_between_the_given_individuals(self):
        llm = _ScriptedLLM(_related("Workhorse", "serves", "Puma"))

        result = _service(llm).relate(TEXT, TYPED, "tax-1", "model-1", 0.0)

        assert [(t["subject"]["label"], t["object"]["label"]) for t in result.triples] == [
            ("Workhorse", "Puma")
        ]
        assert result.failure_reason is None
        assert result.metadata["tokens_used"] == 110
        assert set(result.triples[0]["provenance"]) == {"quote", "start", "end"}

    def test_relate_leaves_out_a_relationship_to_something_that_was_not_typed(self):
        """The type stage is the one way an individual gets its class."""
        llm = _ScriptedLLM(_related("Workhorse", "improves", "readability"))

        result = _service(llm).relate(TEXT, TYPED, "tax-1", "model-1", 0.0)

        assert result.triples == []
        assert result.failure_reason is None

    def test_relate_makes_no_call_for_fewer_than_two_individuals(self):
        llm = _ScriptedLLM()

        result = _service(llm).relate(TEXT, TYPED[:1], "tax-1", "model-1", 0.0)

        assert result.triples == [] and result.failure_reason is None
        assert llm.requests == []

    def test_relationships_that_could_not_be_read_are_a_failure(self):
        llm = _ScriptedLLM(*["{}"] * MAX_LLM_ATTEMPTS)

        result = _service(llm).relate(TEXT, TYPED, "tax-1", "model-1", 0.0)

        assert result.triples == []
        assert result.incomplete_response is True
        assert result.metadata["tokens_used"] == 330

    def test_recognize_without_an_individual_index_returns_the_triples(self):
        assert _service(_ScriptedLLM()).recognize(TYPED, "tax-1") == TYPED
