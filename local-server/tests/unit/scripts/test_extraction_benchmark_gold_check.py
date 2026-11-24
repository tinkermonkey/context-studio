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
    _with_origins,
    check_document,
    check_operations,
    gold_check_problem,
    gold_text,
    rewrite_gold,
    split_of,
    written_by,
)
from tests.integration.pipelines._harness.benchmark import (
    BENCHMARK_DIR,
    SCHEMA_BUNDLE,
    benchmark_documents,
    validate_gold,
)

AT = "2026-11-17T12:00:00+00:00"
CHECKED = {"by": "user", "at": AT, "proposal": "proposal-1"}


def rewrite(*args, **kwargs) -> dict:
    """The rewritten gold file."""
    return rewrite_gold(*args, **kwargs).gold


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

        rewritten = rewrite(gold, proposal_of(gold, document), [], CLASS_REF)

        assert rewritten == gold
        assert gold_text(rewritten) == text

    def test_the_input_is_left_as_it_is(self):
        gold = gold_file()
        before = copy.deepcopy(gold)
        proposal = proposal_of(gold)
        decisions = [decide(proposal, 3, "rejected", reason="Not an element")]

        rewrite(gold, proposal, decisions, CLASS_REF)

        assert gold == before


class TestVerdicts:
    def test_correct_marks_it_checked(self):
        gold = gold_file()
        proposal = proposal_of(gold)

        rewritten = rewrite(gold, proposal, [decide(proposal, 1, "applied")], CLASS_REF)

        item = by_key(rewritten)["edit-check"]
        assert item["checked"] == CHECKED
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

        item = by_key(rewrite(gold, proposal, [decision], CLASS_REF))["reference-check"]

        assert item["class"] == "product.softwarecapability"
        assert "acceptable_classes" not in item
        assert item["checked"] == CHECKED

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

        item = by_key(rewrite(gold, proposal, [decision], CLASS_REF))["reference-check"]

        assert item["class"] == "product.softwarecapability"
        assert item["acceptable_classes"] == ["product.feature"]

    def test_an_acceptable_class_chosen_as_the_class_leaves_the_acceptable_ones(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        edit = {"title": "Edit Check", "class_ids": ["id:product.feature"]}
        decision = decide(
            proposal, 1, "applied", decision="applied_with_edits", applied_fields=edit
        )

        item = by_key(rewrite(gold, proposal, [decision], CLASS_REF))["edit-check"]

        assert item["class"] == "product.feature"
        assert item["acceptable_classes"] == []

    def test_a_title_edit_keeps_the_old_title_as_an_alias(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        edit = {"title": "Edit check", "class_ids": ["id:product.softwarecapability"]}
        decision = decide(
            proposal, 1, "applied", decision="applied_with_edits", applied_fields=edit
        )

        item = by_key(rewrite(gold, proposal, [decision], CLASS_REF))["edit-check"]

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

        item = by_key(rewrite(gold, proposal, [decision], CLASS_REF))["editors"]

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

        rewritten = rewrite(gold, proposal, [decision], CLASS_REF)

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

        rewritten = rewrite(gold, proposal, [decision], CLASS_REF)

        added = rewritten["individuals"][-1]
        assert added == {
            "key": "edit-check-2",
            "title": "Edit Check",
            "class": "product.feature",
            "tier": "core",
            "description": "",
            "evidence": [{"quote": "Edit Check", "start": 50, "end": 60}],
            "checked": CHECKED,
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

        rewritten = rewrite(gold, proposal, [decide(proposal, 99, "applied")], CLASS_REF)

        assert rewritten["individuals"][-1]["key"] == "visual-editor"
        assert rewritten["individuals"][-1]["tier"] == "supporting"

    def test_relationships_applied_are_checked_and_rejected_removed(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        realizes, uses = [o["seq"] for o in proposal["operations"] if o["kind"] == "relationship"]
        decisions = [decide(proposal, realizes, "applied"), decide(proposal, uses, "rejected")]

        rewritten = rewrite(gold, proposal, decisions, CLASS_REF)

        [kept] = rewritten["relationships"]
        assert (kept["source"], kept["checked"]) == ("reference-check", CHECKED)
        assert by_key(rewritten).keys() == by_key(gold).keys()

    def test_pending_and_failed_change_nothing(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        proposal["operations"][0]["status"] = "failed"

        assert rewrite(gold, proposal, [], CLASS_REF) == gold

    def test_a_superseded_decision_is_ignored(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        decision = {**decide(proposal, 1, "applied"), "superseded_at": AT}
        proposal["operations"][0]["status"] = "pending"

        assert rewrite(gold, proposal, [decision], CLASS_REF) == gold


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

    rewritten = rewrite(gold, proposal, decisions, CLASS_REF)
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


# ---------------------------------------------------------------- review follow-ups


def revert(proposal):
    """A revert's end state: what was undecided is rejected, and no decision is recorded."""
    for operation in proposal["operations"]:
        if operation["status"] in ("pending", "failed"):
            operation["status"] = "rejected"
            operation["reason"] = "proposal reverted"


class TestOnlyAPersonsDecisionIsAVerdict:
    def test_a_reverted_check_writes_nothing(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        revert(proposal)

        assert rewrite(gold, proposal, [], CLASS_REF) == gold

    def test_a_rejection_by_a_policy_or_a_bundle_is_not_a_verdict(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        decisions = [
            {**decide(proposal, 1, "rejected"), "decided_by": "policy"},
            {**decide(proposal, 2, "rejected"), "decided_by": "bundle"},
            {**decide(proposal, 3, "applied"), "decided_by": "unknown"},
        ]

        assert rewrite(gold, proposal, decisions, CLASS_REF) == gold

    def test_write_gold_refuses_a_reverted_proposal(self):
        proposal = {**proposal_of(gold_file(), "edit_check"), "status": "reverted"}
        proposal["client_metadata"]["origin"] = {"implementation_id": "gold_check"}

        assert "was reverted" in gold_check_problem(proposal, "edit_check", "tax-1")


class TestWhatWriteGoldRefuses:
    def proposal(self, **changes):
        proposal = {**proposal_of(gold_file(), "edit_check"), "status": "open", **changes}
        proposal["client_metadata"]["origin"] = {"implementation_id": "gold_check"}
        return proposal

    def test_a_gold_check_of_the_document_in_the_taxonomy_is_fine(self):
        assert gold_check_problem(self.proposal(), "edit_check", "tax-1") is None

    def test_another_taxonomy(self):
        problem = gold_check_problem(self.proposal(), "edit_check", "tax-2")
        assert "another taxonomy" in problem

    def test_another_document(self):
        problem = gold_check_problem(self.proposal(), "gitlab_architecture", "tax-1")
        assert "not gitlab_architecture" in problem

    def test_not_a_gold_check(self):
        proposal = self.proposal()
        proposal["client_metadata"]["origin"] = {"implementation_id": "single_call"}
        assert "not a gold check" in gold_check_problem(proposal, "edit_check", "tax-1")


class TestClassEditData:
    def test_values_the_new_class_does_not_define_are_dropped_and_noted(self):
        gold = gold_file()
        gold["individuals"][0]["data"] = {"status": "delivered", "owner": "Editing"}
        proposal = proposal_of(gold)
        edit = {"title": "Edit Check", "class_ids": ["id:product.feature"]}
        decision = decide(
            proposal, 1, "applied", decision="applied_with_edits", applied_fields=edit
        )
        attributes = {"product.feature": {"status"}, "product.softwarecapability": {"status"}}

        result = rewrite_gold(gold, proposal, [decision], CLASS_REF, attributes)

        item = by_key(result.gold)["edit-check"]
        assert item["data"] == {"status": "delivered"}
        assert result.notes == [
            "seq 1 'Edit Check': dropped data owner='Editing'; product.feature has no attribute"
            " owner"
        ]

    def test_no_value_left_drops_data(self):
        gold = gold_file()
        gold["individuals"][0]["data"] = {"status": "delivered"}
        proposal = proposal_of(gold)
        edit = {"title": "Edit Check", "class_ids": ["id:product.feature"]}
        decision = decide(
            proposal, 1, "applied", decision="applied_with_edits", applied_fields=edit
        )

        result = rewrite_gold(gold, proposal, [decision], CLASS_REF, {"product.feature": set()})

        assert "data" not in by_key(result.gold)["edit-check"]

    def test_a_second_class_is_noted_and_not_written(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        edit = {"title": "Editors", "class_ids": ["id:business.businessrole", "id:product.persona"]}
        decision = decide(
            proposal, 3, "applied", decision="applied_with_edits", applied_fields=edit
        )

        result = rewrite_gold(gold, proposal, [decision], CLASS_REF)

        assert by_key(result.gold)["editors"]["class"] == "business.businessrole"
        assert "only the first, business.businessrole, is written" in result.notes[0]

    def test_a_problem_names_the_operation_behind_it(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        edit = {"title": "Reference Check", "class_ids": ["id:product.persona"]}
        decision = decide(
            proposal, 2, "applied", decision="applied_with_edits", applied_fields=edit
        )
        result = rewrite_gold(gold, proposal, [decision], CLASS_REF)
        problems = [
            "reference-check realizes edit-check: not a relationship type of the schema",
            "duplicate title 'x'",
        ]

        named = _with_origins(problems, result.origins)

        assert named == [
            "reference-check realizes edit-check: not a relationship type of the schema"
            " (from seq 2 'Reference Check')",
            "duplicate title 'x'",
        ]
        assert result.origins["reference-check"] == "seq 2 'Reference Check'"


class TestSecondRun:
    def added_proposal(self, gold):
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
                "evidence": [{"start": 50, "end": 63, "quote": "visual editor"}],
            }
        )
        return proposal

    def test_writing_the_same_review_again_changes_nothing(self):
        gold = gold_file()
        proposal = self.added_proposal(gold)
        edit = {"title": "Edit check", "class_ids": ["id:product.feature"]}
        decisions = [
            decide(proposal, 1, "applied", decision="applied_with_edits", applied_fields=edit),
            decide(proposal, 3, "rejected", reason="Not an element"),
            decide(proposal, 99, "applied"),
        ]
        realizes = next(o["seq"] for o in proposal["operations"] if o["kind"] == "relationship")
        decisions.append(decide(proposal, realizes, "applied", annotations={"tier": "supporting"}))

        once = rewrite(gold, proposal, decisions, CLASS_REF)
        twice = rewrite(once, proposal, decisions, CLASS_REF)

        assert twice == once
        assert gold_text(twice) == gold_text(once)
        assert [i["key"] for i in once["individuals"]].count("visual-editor") == 1
        assert [e["label"] for e in once["excluded"]].count("Editors") == 1

    def test_an_excluded_label_is_not_added_twice(self):
        gold = gold_file()
        gold["excluded"].append({"label": "Editors", "reason": "Already out."})
        proposal = proposal_of(gold)

        result = rewrite(gold, proposal, [decide(proposal, 3, "rejected")], CLASS_REF)

        assert [e["label"] for e in result["excluded"]].count("Editors") == 1

    def test_a_file_this_proposal_wrote_is_recognised(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        written = rewrite(gold, proposal, [decide(proposal, 1, "applied")], CLASS_REF)

        assert written_by(written, "proposal-1")
        assert not written_by(gold, "proposal-1")
        assert not written_by(written, "another-proposal")


def test_an_applied_relationship_takes_its_tier_annotation():
    gold = gold_file()
    proposal = proposal_of(gold)
    uses = [o["seq"] for o in proposal["operations"] if o["kind"] == "relationship"][1]

    result = rewrite(
        gold, proposal, [decide(proposal, uses, "applied", annotations={"tier": "core"})], CLASS_REF
    )

    assert result["relationships"][1]["tier"] == "core"
    assert result["relationships"][1]["checked"] == CHECKED


class TestEditedRelationships:
    """A relationship accepted with another type or end replaces the gold one."""

    def _applied_ends(self, proposal):
        """Accept every individual, each creating an entity named after its key."""
        decisions = []
        for operation in proposal["operations"]:
            if operation["kind"] == "individual":
                decisions.append(decide(proposal, operation["seq"], "applied"))
                operation["result_entity_id"] = f"ent:{operation['ref']}"
        return decisions

    def test_another_predicate_and_end_replace_the_relationship(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        decisions = self._applied_ends(proposal)
        uses = [o["seq"] for o in proposal["operations"] if o["kind"] == "relationship"][1]
        operation = next(o for o in proposal["operations"] if o["seq"] == uses)
        # applied_fields are the proposed fields with the edit over them: the source stays a $ref.
        edit = {
            **operation["fields"],
            "property_definition_id": "prop-serves",
            "target_id": "ent:reference-check",
        }
        decisions.append(
            decide(proposal, uses, "applied", "applied_with_edits", applied_fields=edit)
        )

        result = rewrite(
            gold, proposal, decisions, CLASS_REF, property_predicate={"prop-serves": "serves"}
        )

        triples = [(r["source"], r["predicate"], r["target"]) for r in result["relationships"]]
        assert ("editors", "uses", "edit-check") not in triples
        assert ("editors", "serves", "reference-check") in triples
        replaced = next(r for r in result["relationships"] if r["predicate"] == "serves")
        assert replaced["checked"] == CHECKED
        assert replaced["evidence"] == gold["relationships"][1]["evidence"]

    def test_an_end_outside_the_gold_check_is_left_as_it_is_and_noted(self):
        gold = gold_file()
        proposal = proposal_of(gold)
        decisions = self._applied_ends(proposal)
        uses = [o["seq"] for o in proposal["operations"] if o["kind"] == "relationship"][1]
        decisions.append(
            decide(
                proposal,
                uses,
                "applied",
                "applied_with_edits",
                applied_fields={"target_id": "elsewhere"},
            )
        )

        result = rewrite_gold(
            gold, proposal, decisions, CLASS_REF, property_predicate={"prop-serves": "serves"}
        )

        assert result.gold["relationships"][1] == gold["relationships"][1]
        assert any("left as it is" in note for note in result.notes)


class _FakeApi:
    """Just enough of the API for check: the new proposal comes back as `status` says."""

    def __init__(self, status):
        self.status = status
        self.posted = []
        self.bodies = []

    def get(self, path, **query):
        if path == "/api/datasets":
            return []
        if path.endswith("/text"):
            return {"text": (BENCHMARK_DIR / "edit_check" / "source.md").read_text("utf-8")}
        raise AssertionError(path)

    def post(self, path, body, **query):
        self.posted.append((path, query))
        self.bodies.append((path, body))
        if path == "/api/datasets":
            return {"id": "dataset-1", **body}
        operations = [
            {**o, "id": f"op-{o['seq']}", "status": "pending"} for o in body["operations"]
        ]
        operations[0]["status"] = self.status
        return {"id": "proposal-1", "operations": operations}

    def upload(self, path, fields, file_name, data):
        return {"id": "source-1", "status": "ready"}


class _FakeSchema:
    taxonomy_id = "tax-1"
    class_id = _ClassIds()
    property_id = _AnyProperty()

    def __init__(self):
        gold = json.loads((BENCHMARK_DIR / "edit_check" / "gold.json").read_text("utf-8"))
        self.class_id = {i["class"]: class_id(i["class"]) for i in gold["individuals"]}


class TestCheckDocument:
    def test_all_pending_is_ready_to_review(self):
        api = _FakeApi("pending")

        proposal = check_document(api, _FakeSchema(), "edit_check")

        assert proposal["id"] == "proposal-1"
        assert [q for p, q in api.posted if p == "/api/proposals"] == [{"dry_run": "true"}, {}]
        # #1628: no approval policy may apply a gold check
        assert all(b["review_only"] is True for p, b in api.bodies if p == "/api/proposals")

    def test_an_operation_the_approval_policy_applied_stops_it(self):
        with pytest.raises(SystemExit, match="approval policy") as raised:
            check_document(_FakeApi("applied"), _FakeSchema(), "edit_check")

        message = str(raised.value)
        assert "seq 1 applied" in message and "Revert proposal proposal-1" in message
