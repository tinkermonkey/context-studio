"""
Tests for the extraction example library (#1315): the shipped file and its loader.
"""

import json
import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest
from pydantic import ValidationError

from adapters.factories.orchestrator_factory import build_run_specific_data
from adapters.web.extraction_examples import load_extraction_examples
from domain.pipelines.entities import PipelineType


def _write(tmp_path, examples):
    path = tmp_path / "examples.json"
    path.write_text(json.dumps({"examples": examples}))
    return path


def _example(example_id="a", **fields):
    return {
        "id": example_id,
        "title": "A",
        "description": "Exercises A.",
        "pipelines": ["schema_extraction"],
        "text": "Some text.",
        **fields,
    }


class TestShippedLibrary:
    def test_loads_with_unique_ids_and_text(self):
        examples = load_extraction_examples()
        assert len(examples) >= 10
        assert len({e.id for e in examples}) == len(examples)
        assert all(e.text.strip() and e.description.strip() for e in examples)

    def test_names_only_real_pipeline_types(self):
        for example in load_extraction_examples():
            for pipeline in example.pipelines:
                PipelineType(pipeline)

    def test_covers_both_extraction_pipelines(self):
        pipelines = {p for e in load_extraction_examples() for p in e.pipelines}
        assert {"schema_extraction", "individual_extraction"} <= pipelines


class TestLoader:
    def test_reads_examples_in_file_order(self, tmp_path):
        path = _write(tmp_path, [_example("b"), _example("a", taxonomy_hint="dr_spec")])
        examples = load_extraction_examples(path)
        assert [e.id for e in examples] == ["b", "a"]
        assert examples[1].taxonomy_hint == "dr_spec"
        assert examples[0].taxonomy_hint is None

    def test_rejects_duplicate_ids(self, tmp_path):
        with pytest.raises(ValueError, match="Duplicate extraction example id"):
            load_extraction_examples(_write(tmp_path, [_example("a"), _example("a")]))

    def test_rejects_an_example_without_text(self, tmp_path):
        with pytest.raises(ValidationError):
            load_extraction_examples(_write(tmp_path, [_example(text="")]))


class TestRunRecordsExample:
    @pytest.mark.parametrize(
        "pipeline_type, input_data",
        [
            (PipelineType.SCHEMA_EXTRACTION, {"documents": ["Text."], "scope": "tax-1"}),
            (PipelineType.INDIVIDUAL_EXTRACTION, {"text": "Text.", "ontology_id": "tax-1"}),
        ],
    )
    def test_example_id_is_kept_in_the_input_summary(self, pipeline_type, input_data):
        data = build_run_specific_data(pipeline_type, {**input_data, "example_id": "ddd"})
        assert data["input_summary"]["example_id"] == "ddd"

    def test_free_text_runs_have_no_example(self):
        data = build_run_specific_data(PipelineType.SCHEMA_EXTRACTION, {"documents": ["Text."]})
        assert "example_id" not in data.get("input_summary", {})
