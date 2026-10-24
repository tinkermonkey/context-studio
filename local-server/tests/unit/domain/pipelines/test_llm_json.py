"""Unit tests for the tolerant LLM JSON extraction helper."""

import json
import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.pipelines.llm_json import extract_json


class TestExtractJson:
    def test_plain_array(self):
        assert extract_json('["A", "B"]') == ["A", "B"]

    def test_plain_object_with_whitespace(self):
        assert extract_json('  \n{"a": 1}\n ') == {"a": 1}

    def test_fenced_array_without_language_tag(self):
        assert extract_json('```\n["Microservice", "API Gateway"]\n```') == [
            "Microservice",
            "API Gateway",
        ]

    def test_fenced_object_with_language_tag(self):
        text = '```json\n{"relationships": [], "properties": []}\n```'
        assert extract_json(text) == {"relationships": [], "properties": []}

    def test_fence_on_single_line(self):
        assert extract_json('```json["A"]```') == ["A"]

    def test_prose_before_and_after(self):
        text = 'Here is the result:\n{"a": [1, 2]}\nLet me know if you need more.'
        assert extract_json(text) == {"a": [1, 2]}

    def test_prose_around_fenced_block(self):
        text = 'Sure!\n```json\n["X", "Y"]\n```\nDone.'
        assert extract_json(text) == ["X", "Y"]

    def test_brackets_inside_strings(self):
        text = 'Result: {"label": "Set [x] {y}", "quote": "a \\"}\\" b"} trailing ]'
        assert extract_json(text) == {"label": "Set [x] {y}", "quote": 'a "}" b'}

    def test_skips_unparseable_bracket_span_in_prose(self):
        text = 'See [note] below: ["Real", "Answer"]'
        assert extract_json(text) == ["Real", "Answer"]

    @pytest.mark.parametrize("text", ["", "   ", "not json at all", "{unclosed", "```json\n```"])
    def test_raises_when_nothing_parseable(self, text):
        with pytest.raises(json.JSONDecodeError):
            extract_json(text)
