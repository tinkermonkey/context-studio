"""
Unit tests (#1613): a gold check's proposal is built from a gold file, and the
decisions taken on it are written back by a pure rewrite of the gold file.
"""

import os
import shutil
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import copy
import json

import pytest

from scripts.extraction_benchmark import (
    GOLD_CHECK_KEY,
    Schema,
    check_operations,
    gold_text,
    rewrite_gold,
    split_of,
)
from tests.integration.pipelines._harness.benchmark import (
    BENCHMARK_DIR,
    SCHEMA_BUNDLE,
    benchmark_documents,
    validate_gold,
)

AT = "2026-11-17T12:00:00+00:00"


class _AnyProperty(dict):
    """Every relationship type's id, for building operations without a schema."""

    def __missing__(self, triple):
        return "prop:" + "|".join(triple)


def class_id(ref: str) -> str:
    return f"id:{ref}"


class _ClassIds(dict):
    def __missing__(self, ref):
        return class_id(ref)


class _ClassRefs(dict):
    def __missing__(self, identifier):
        if not identifier.startswith("id:"):
            raise KeyError(identifier)
        return identifier[3:]

    def __contains__(self, identifier):
        return isinstance(identifier, str) and identifier.startswith("id:")


CLASS_REF = _ClassRefs()


def proposal_of(gold: dict, document: str = "doc") -> dict:
    """The proposal a gold check makes of a gold file, as the API returns it: all pending."""
    operations, mapping = check_operations(gold, _ClassIds(), _AnyProperty(), "src-1")
    return {
        "id": "proposal-1",
        "taxonomy_id": "tax-1",
        "client_metadata": {
            "source_id": "src-1",
            GOLD_CHECK_KEY: {"document": document, **mapping},
        },
        "operations": [
            {**o, "id": f"op-{o['seq']}", "status": "pending", "added_by_reviewer": False}
            for o in operations
        ],
    }


def gold_file() -> dict:
    return {
        "format": "extraction-benchmark/1",
        "individuals": [
            {
                "key": "edit-check",
                "title": "Edit Check",
                "class": "product.softwarecapability",
                "tier": "core",
                "description": "Checks edits.",
                "aliases": ["Edit check"],
                "acceptable_classes": ["product.feature"],
                "evidence": [{"quote": "Edit check", "start": 0, "end": 10}],
            },
            {
                "key": "reference-check",
                "title": "Reference Check",
                "class": "product.feature",
                "tier": "core",
                "description": "Asks for a reference.",
                "evidence": [{"quote": "Reference check", "start": 20, "end": 35}],
            },
            {
                "key": "editors",
                "title": "Editors",
                "class": "business.businessactor",
                "tier": "supporting",
                "description": "People who edit.",
                "evidence": [{"quote": "editors", "start": 40, "end": 47}],
            },
        ],
        "relationships": [
            {
                "source": "reference-check",
                "predicate": "realizes",
                "target": "edit-check",
                "tier": "core",
                "evidence": [{"quote": "Reference check", "start": 20, "end": 35}],
            },
            {
                "source": "editors",
                "predicate": "uses",
                "target": "edit-check",
                "tier": "supporting",
                "evidence": [{"quote": "editors", "start": 40, "end": 47}],
            },
        ],
        "excluded": [{"label": "Edit filter", "reason": "Prior art."}],
    }


def decide(proposal, seq, status, decision=None, **fields):
    """Set an operation's outcome and return its decision, as the gold API lists it."""
    operation = next(o for o in proposal["operations"] if o["seq"] == seq)
    operation["status"] = status
    if status == "rejected":
        operation["reason"] = fields.get("reason")
        operation["reason_code"] = fields.get("reason_code")
    if fields.get("applied_fields") is not None:
        operation["applied_fields"] = fields["applied_fields"]
    return {
        "operation_id": operation["id"],
        "seq": seq,
        "decision": decision or ("rejected" if status == "rejected" else "applied"),
        "decided_by": "user",
        "decided_at": AT,
        "proposed": {"fields": dict(operation["fields"])},
        "applied_fields": fields.get("applied_fields"),
        "reason": fields.get("reason"),
        "reason_code": fields.get("reason_code"),
        "annotations": fields.get("annotations"),
        "added": False,
        "superseded_at": None,
    }


def by_key(gold: dict) -> dict:
    return {i["key"]: i for i in gold["individuals"]}


class TestCheckOperations:
    def test_each_element_keeps_its_gold_key_tier_and_acceptable_classes(self):
        proposal = proposal_of(gold_file(), "edit_check")

        individuals = [o for o in proposal["operations"] if o["kind"] == "individual"]
        assert [o["ref"] for o in individuals] == ["edit-check", "reference-check", "editors"]
        assert individuals[0]["fields"] == {
            "title": "Edit Check",
            "class_ids": ["id:product.softwarecapability"],
        }
        assert individuals[0]["evidence"][0]["source_id"] == "src-1"
        meta = proposal["client_metadata"][GOLD_CHECK_KEY]
        assert meta["elements"]["edit-check"] == {
            "key": "edit-check",
            "tier": "core",
            "acceptable_classes": ["product.feature"],
            "aliases": ["Edit check"],
        }
        [first, _] = [o for o in proposal["operations"] if o["kind"] == "relationship"]
        assert first["fields"]["source_id"] == "$reference-check"
        assert meta["relationships"][str(first["seq"])] == {
            "source": "reference-check",
            "predicate": "realizes",
            "target": "edit-check",
            "tier": "core",
        }

    def test_the_holdout_document_is_the_holdout_split(self):
        assert split_of("wikimedia_enterprise") == "holdout"
        assert split_of("edit_check") == "dev"


class TestRoundTrip:
    @pytest.mark.parametrize("document", benchmark_documents())
    def test_no_decisions_give_the_gold_file_back(self, document):
        text = (BENCHMARK_DIR / document / "gold.json").read_text(encoding="utf-8")
        gold = json.loads(text)

        rewritten = rewrite_gold(gold, proposal_of(gold, document), [], CLASS_REF)

        assert rewritten == gold
        assert gold_text(rewritten) == text

    def test_the_input_is_left_as_it_is(self):
        gold = gold_file()
        before = copy.deepcopy(gold)
        proposal = proposal_of(gold)
        decisions = [decide(proposal, 3, "rejected", reason="Not an element")]

        rewrite_gold(gold, proposal, decisions, CLASS_REF)

        assert gold == before


class TestVerdicts:
    def test_correct_marks_it_checked(self):
        gold = gold_file()
        proposal = proposal_of(gold)

        rewritten = rewrite_gold(gold, proposal, [decide(proposal, 1, "applied")], CLASS_REF)

        item = by_key(rewritten)["edit-check"]
        assert item["checked"] == {"by": "user", "at": AT}
        assert list(item)[-1] == "checked"  # the other keys keep their order
        assert {k: v for k, v in item.items() if k != "checked"} == by_key(gold)["edit-check"]
        assert "checked" not in by_key(rewritten)["reference-check"]

    def test_a_better_class_replaces_it_and_drops_the_old_one(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        edit = {"title": "Reference Check", "class_ids": ["id:product.softwarecapability"]}
        decision = decide(
            proposal, 2, "applied", decision="applied_with_edits", applied_fields=edit
        )

        item = by_key(rewrite_gold(gold, proposal, [decision], CLASS_REF))["reference-check"]

        assert item["class"] == "product.softwarecapability"
        assert "acceptable_classes" not in item
        assert item["checked"] == {"by": "user", "at": AT}

    def test_a_better_class_keeps_the_old_one_when_marked_defensible(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        edit = {"title": "Reference Check", "class_ids": ["id:product.softwarecapability"]}
        decision = decide(
            proposal,
            2,
            "applied",
            decision="applied_with_edits",
            applied_fields=edit,
            annotations={"also_defensible": ["id:product.feature"]},
        )

        item = by_key(rewrite_gold(gold, proposal, [decision], CLASS_REF))["reference-check"]

        assert item["class"] == "product.softwarecapability"
        assert item["acceptable_classes"] == ["product.feature"]

    def test_an_acceptable_class_chosen_as_the_class_leaves_the_acceptable_ones(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        edit = {"title": "Edit Check", "class_ids": ["id:product.feature"]}
        decision = decide(
            proposal, 1, "applied", decision="applied_with_edits", applied_fields=edit
        )

        item = by_key(rewrite_gold(gold, proposal, [decision], CLASS_REF))["edit-check"]

        assert item["class"] == "product.feature"
        assert item["acceptable_classes"] == []

    def test_a_title_edit_keeps_the_old_title_as_an_alias(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        edit = {"title": "Edit check", "class_ids": ["id:product.softwarecapability"]}
        decision = decide(
            proposal, 1, "applied", decision="applied_with_edits", applied_fields=edit
        )

        item = by_key(rewrite_gold(gold, proposal, [decision], CLASS_REF))["edit-check"]

        assert item["title"] == "Edit check"
        assert item["aliases"] == ["Edit Check"]

    def test_tier_and_also_defensible_annotations(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        decision = decide(
            proposal,
            3,
            "applied",
            annotations={
                "tier": "core",
                "also_defensible": ["id:business.businessrole", "id:business.businessactor"],
            },
        )

        item = by_key(rewrite_gold(gold, proposal, [decision], CLASS_REF))["editors"]

        assert item["tier"] == "core"
        # Its own class is never one of its acceptable ones
        assert item["acceptable_classes"] == ["business.businessrole"]
        assert list(item)[:5] == ["key", "title", "class", "tier", "description"]

    @pytest.mark.parametrize(
        ("reason", "reason_code", "written"),
        [
            ("Named only as prior art", "out_of_scope", "Named only as prior art"),
            (None, "too_generic", "Too generic to be an element."),
            (None, None, "Rejected in review."),
        ],
    )
    def test_not_an_element_moves_to_excluded_with_its_relationships(
        self, reason, reason_code, written
    ):
        gold = gold_file()
        proposal = proposal_of(gold)
        decision = decide(proposal, 3, "rejected", reason=reason, reason_code=reason_code)

        rewritten = rewrite_gold(gold, proposal, [decision], CLASS_REF)

        assert "editors" not in by_key(rewritten)
        assert rewritten["excluded"][-1] == {"label": "Editors", "reason": written}
        assert [r["source"] for r in rewritten["relationships"]] == ["reference-check"]

    def test_added_from_the_text_is_a_new_individual(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        proposal["operations"].append(
            {
                "id": "op-added",
                "seq": 99,
                "op": "create",
                "kind": "individual",
                "status": "applied",
                "added_by_reviewer": True,
                "fields": {"title": "Edit Check", "class_ids": ["id:product.feature"]},
                "evidence": [
                    {
                        "source_id": "src-1",
                        "page": None,
                        "start": 50,
                        "end": 60,
                        "quote": "Edit Check",
                    }
                ],
            }
        )
        decision = {
            **decide(proposal, 99, "applied", annotations={"tier": "core"}),
            "added": True,
        }

        rewritten = rewrite_gold(gold, proposal, [decision], CLASS_REF)

        added = rewritten["individuals"][-1]
        assert added == {
            "key": "edit-check-2",
            "title": "Edit Check",
            "class": "product.feature",
            "tier": "core",
            "description": "",
            "evidence": [{"quote": "Edit Check", "start": 50, "end": 60}],
            "checked": {"by": "user", "at": AT},
        }

    def test_an_added_element_without_a_tier_is_supporting(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        proposal["operations"].append(
            {
                "id": "op-added",
                "seq": 99,
                "op": "create",
                "kind": "individual",
                "status": "applied",
                "added_by_reviewer": True,
                "fields": {
                    "title": "Visual Editor",
                    "class_ids": ["id:application.applicationcomponent"],
                },
                "evidence": [],
            }
        )

        rewritten = rewrite_gold(gold, proposal, [decide(proposal, 99, "applied")], CLASS_REF)

        assert rewritten["individuals"][-1]["key"] == "visual-editor"
        assert rewritten["individuals"][-1]["tier"] == "supporting"

    def test_relationships_applied_are_checked_and_rejected_removed(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        realizes, uses = [o["seq"] for o in proposal["operations"] if o["kind"] == "relationship"]
        decisions = [decide(proposal, realizes, "applied"), decide(proposal, uses, "rejected")]

        rewritten = rewrite_gold(gold, proposal, decisions, CLASS_REF)

        [kept] = rewritten["relationships"]
        assert (kept["source"], kept["checked"]) == ("reference-check", {"by": "user", "at": AT})
        assert by_key(rewritten).keys() == by_key(gold).keys()

    def test_pending_and_failed_change_nothing(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        proposal["operations"][0]["status"] = "failed"

        assert rewrite_gold(gold, proposal, [], CLASS_REF) == gold

    def test_a_superseded_decision_is_ignored(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        decision = {**decide(proposal, 1, "applied"), "superseded_at": AT}
        proposal["operations"][0]["status"] = "pending"

        assert rewrite_gold(gold, proposal, [decision], CLASS_REF) == gold


def test_written_back_on_a_real_gold_file_it_still_validates(tmp_path):
    """Each verdict on edit_check, written as write-gold writes it, passes validate."""
    document = "edit_check"
    shutil.copy(BENCHMARK_DIR / SCHEMA_BUNDLE, tmp_path / SCHEMA_BUNDLE)
    folder = tmp_path / document
    folder.mkdir()
    shutil.copy(BENCHMARK_DIR / document / "source.md", folder / "source.md")
    gold = json.loads((BENCHMARK_DIR / document / "gold.json").read_text(encoding="utf-8"))
    source = (folder / "source.md").read_text(encoding="utf-8")
    proposal = proposal_of(gold, document)
    ends = {k for r in gold["relationships"] for k in (r["source"], r["target"])}
    # A class edit on an element no relationship uses (one that does could leave a
    # relationship that is no type of the schema: validate refuses that, and write-gold
    # then leaves the file as it was)
    seq, retyped = next(
        (n, item)
        for n, item in enumerate(gold["individuals"], start=1)
        if item["key"] not in ends and item.get("acceptable_classes")
    )
    dropped_seq, dropped = next(
        (n, item)
        for n, item in enumerate(gold["individuals"], start=1)
        if item["key"] not in ends and n != seq
    )
    other_class = retyped["acceptable_classes"][0]
    quote = "Reference check"
    start = source.index(quote)
    proposal["operations"].append(
        {
            "id": "op-added",
            "seq": 999,
            "op": "create",
            "kind": "individual",
            "status": "applied",
            "added_by_reviewer": True,
            "fields": {"title": "A reviewer's element", "class_ids": ["id:product.feature"]},
            "evidence": [{"start": start, "end": start + len(quote), "quote": quote}],
        }
    )
    relationship_seq = next(o["seq"] for o in proposal["operations"] if o["kind"] == "relationship")
    decisions = [
        decide(
            proposal,
            seq,
            "applied",
            decision="applied_with_edits",
            applied_fields={"title": retyped["title"], "class_ids": [f"id:{other_class}"]},
            annotations={"tier": "supporting", "also_defensible": [f"id:{retyped['class']}"]},
        ),
        decide(proposal, 1, "applied"),
        decide(proposal, dropped_seq, "rejected", reason_code="mentioned_only"),
        decide(proposal, relationship_seq, "rejected"),
        decide(proposal, 999, "applied"),
    ]

    rewritten = rewrite_gold(gold, proposal, decisions, CLASS_REF)
    (folder / "gold.json").write_text(gold_text(rewritten), encoding="utf-8")

    assert validate_gold(document, tmp_path) == []
    items = by_key(rewritten)
    assert items[retyped["key"]]["class"] == other_class
    assert retyped["class"] in items[retyped["key"]]["acceptable_classes"]
    assert dropped["key"] not in items
    assert len(rewritten["relationships"]) == len(gold["relationships"]) - 1
    assert rewritten["individuals"][-1]["key"] == "a-reviewer-s-element"


def test_a_class_is_read_by_its_dr_reference_whatever_its_first_is():
    """A bundle import puts its own reference first; the DR one names the type."""
    cls = {
        "identifier": "api_callback",
        "external_references": [
            {"source": "dr_spec", "identifier": "api_callback"},
            {"source": "documentation_robotics", "identifier": "api.callback"},
        ],
    }

    assert Schema._ref(cls) == "api.callback"
    assert Schema._ref({**cls, "external_references": cls["external_references"][:1]}) == (
        "api_callback"
    )
