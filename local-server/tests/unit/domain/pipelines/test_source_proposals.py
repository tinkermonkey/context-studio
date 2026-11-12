"""
Unit tests (#1552): an extraction run's merged triples on a source become one
proposal. New individuals are creates with refs, evidence (every passage, page
from 1) and near-match alternatives; recognized ones get no create;
relationships point at "$ref" or existing ids; refused operations are dropped
with their dependents and the rest proposed again; a re-extraction supersedes
the earlier extraction's open proposal; schema candidates become class,
predicate and relationship-type creates.
"""

import asyncio

import pytest

from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.individual_extraction.source_operations import (
    plan_individual_operations,
)
from domain.pipelines.schema_extraction.orchestrator import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
)
from domain.pipelines.schema_extraction.source_operations import plan_schema_operations
from domain.pipelines.source_extraction import normalized_pages
from domain.pipelines.source_operations import passage_evidence
from domain.pipelines.source_proposals import SourceProposer
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationStatus, ProposalStatus
from domain.versioning.provenance import evidence_problem
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.unit.domain.versioning.test_proposal_service import (  # noqa: F401 - fixtures
    ontology,
    proposals,
    publisher,
    repo,
    reverter,
)

SOURCE = "src-manual"
PAGE_STARTS = [0, 100, 200]


@pytest.fixture()
def service(proposals, ontology, repo, reverter):
    return ProposalService(proposals, ontology, repo, reverter)


@pytest.fixture()
def house(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Resources")
    appliance = ontology.create_class(scheme.id, "Appliance", identifier="house_appliance")
    business = ontology.create_class(scheme.id, "Business", identifier="house_business")
    computed = ontology.create_class(scheme.id, "Computed", derived=True)
    made_by = ontology.create_property_definition(
        "made_by", "made by", domain_class_id=appliance.id, range_class_id=business.id
    )
    home = ontology.create_dataset(taxonomy.id, "home", "Home")
    cabin = ontology.create_dataset(taxonomy.id, "cabin", "Cabin")
    fridge = ontology.create_individual(appliance.id, "Kitchen refrigerator", dataset_id=home.id)
    whirlpool = ontology.create_individual(business.id, "Whirlpool Corporation", dataset_id=home.id)
    elsewhere = ontology.create_individual(appliance.id, "Cabin fridge", dataset_id=cabin.id)
    return {
        "taxonomy": taxonomy.id,
        "scheme": scheme.id,
        "appliance": appliance.id,
        "business": business.id,
        "computed": computed.id,
        "made_by": made_by.id,
        "home": home.id,
        "cabin": cabin.id,
        "fridge": fridge.id,
        "whirlpool": whirlpool.id,
        "elsewhere": elsewhere.id,
    }


def typing(
    label,
    class_label,
    passages=(),
    confidence=0.8,
    near=None,
    entity_id="",
    predicate=None,
):
    """
    A typing triple shaped as the two-pass extraction returns it: models follow
    the prompt's example and send property_definition_id "is_a" (#1450).
    """
    triple = {
        "subject": {"kind": "individual", "id": entity_id, "label": label, "class_ids": []},
        "predicate": predicate or {"property_definition_id": "is_a", "label": "is_a"},
        "object": {"kind": "class", "id": "", "label": class_label},
        "confidence": confidence,
        "provenance": dict(passages[0]) if passages else {},
        "passages": [dict(p) for p in passages],
    }
    if near is not None:
        triple["near_matches"] = near
    return triple


def relation(subject, property_id, obj, passages=(), confidence=0.7, subject_id="", object_id=""):
    return {
        "subject": {"kind": "individual", "id": subject_id, "label": subject},
        "predicate": {"property_definition_id": property_id, "label": "made_by"},
        "object": {"kind": "individual", "id": object_id, "label": obj},
        "confidence": confidence,
        "provenance": dict(passages[0]) if passages else {},
        "passages": [dict(p) for p in passages],
    }


def passage(quote, start, page):
    return {"quote": quote, "start": start, "end": start + len(quote), "page": page}


def plan(repo, house, triples, dataset="home"):
    return plan_individual_operations(
        triples,
        repo,
        taxonomy_id=house["taxonomy"],
        dataset_id=house[dataset],
        source_id=SOURCE,
        page_starts=PAGE_STARTS,
    )


def started(minute):
    """When an extraction started: minutes past a fixed hour."""
    return {"extraction_started_at": f"2026-11-11T10:{minute:02d}:00+00:00"}


def run_input(house, dataset="home", **extra):
    return {
        "source_id": SOURCE,
        "source_title": "WRF555 use and care guide",
        "ontology_id": house["taxonomy"],
        "dataset_id": house[dataset],
        "page_starts": PAGE_STARTS,
        **extra,
    }


@pytest.mark.parametrize(
    ("pages", "normalized"),
    [("2", "2"), (" 3 , 1-2", "1-3"), ("1-3, 7", "1-3, 7"), ("7, 2-2, 5-6", "2, 5-7")],
)
def test_page_selections_have_one_spelling(pages, normalized):
    assert normalized_pages(pages) == normalized


class TestPassageEvidence:
    def test_placed_passages_become_source_evidence(self):
        items = passage_evidence(
            [passage("WRF555SDFZ", 120, 2), passage("WRF555SDFZ", 120, 2)], SOURCE, PAGE_STARTS
        )
        assert items == [
            {"source_id": SOURCE, "page": 2, "start": 120, "end": 130, "quote": "WRF555SDFZ"}
        ]
        assert evidence_problem(items[0]) is None

    def test_page_comes_from_page_starts_when_missing_and_counts_from_1(self):
        items = passage_evidence([{"quote": "filter", "start": 5, "end": 11}], SOURCE, PAGE_STARTS)
        assert items[0]["page"] == 1
        bad = passage_evidence([{"quote": "x", "start": 5, "end": 6, "page": 0}], SOURCE, [])
        assert bad[0]["page"] is None

    def test_an_unplaced_quote_keeps_only_its_quote(self):
        items = passage_evidence(
            [{"quote": "somewhere", "start": None, "end": None}], SOURCE, PAGE_STARTS
        )
        assert items == [{"quote": "somewhere"}]


class TestIndividualOperations:
    def test_a_new_individual_is_a_create_with_ref_classes_evidence_and_probability(
        self, repo, house
    ):
        result = plan(
            repo,
            house,
            [
                typing(
                    "Whirlpool WRF555SDFZ",
                    "house_appliance",
                    [passage("WRF555SDFZ", 120, 2), passage("WRF555SDFZ", 210, 3)],
                    confidence=0.94,
                )
            ],
        )

        [planned] = result.operations
        draft = planned.draft
        assert (draft.seq, draft.op, draft.kind, draft.ref) == (1, "create", "individual", "i1")
        assert draft.fields == {
            "title": "Whirlpool WRF555SDFZ",
            "class_ids": [house["appliance"]],
        }
        assert draft.probability == 0.94
        assert [(e["page"], e["start"]) for e in draft.evidence] == [(2, 120), (3, 210)]
        assert all(e["source_id"] == SOURCE for e in draft.evidence)

    @pytest.mark.parametrize(
        "predicate",
        [
            {"property_definition_id": "is_a", "label": "is_a"},
            {"property_definition_id": "", "label": "is_a"},
            {"property_definition_id": None, "label": "is_a"},
            {"property_definition_id": "...", "label": "is a"},
            {"property_definition_id": "type", "label": "rdf:type"},
            {"property_definition_id": "is_a", "label": "instance_of"},
        ],
    )
    def test_every_typing_shape_the_extraction_sends_makes_a_create(self, repo, house, predicate):
        result = plan(
            repo,
            house,
            [
                typing("WRF555", "house_appliance", predicate=predicate),
                typing("Acme", "house_business", predicate=predicate),
                relation("WRF555", house["made_by"], "Acme"),
            ],
        )
        assert [(o.draft.kind, o.label) for o in result.operations] == [
            ("individual", "WRF555"),
            ("individual", "Acme"),
            ("relationship", "WRF555 made_by Acme"),
        ]
        assert result.skipped == []

    def test_the_class_is_found_by_title_reference_or_id(self, repo, house):
        result = plan(repo, house, [typing("Acme", "Business"), typing("Ice maker", "APPLIANCE")])
        assert [o.draft.fields["class_ids"] for o in result.operations] == [
            [house["business"]],
            [house["appliance"]],
        ]

    def test_a_mention_typed_twice_is_one_create_in_both_classes(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Whirlpool", "house_business", [passage("Whirlpool", 5, 1)], 0.6),
                typing("whirlpool", "house_appliance", [passage("Whirlpool", 150, 2)], 0.9),
            ],
        )
        [planned] = result.operations
        assert planned.draft.fields["class_ids"] == [house["business"], house["appliance"]]
        assert planned.draft.probability == 0.9
        assert len(planned.draft.evidence) == 2

    def test_unknown_and_derived_classes_skip_the_mention(self, repo, house):
        result = plan(repo, house, [typing("Gizmo", "no_such_class"), typing("X", "Computed")])
        assert result.operations == []
        assert result.skipped == [
            {"label": "Gizmo", "reason": "missing_class"},
            {"label": "X", "reason": "missing_class"},
        ]

    def test_a_recognized_individual_gets_no_create(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Kitchen refrigerator", "house_appliance", entity_id=house["fridge"]),
                typing("whirlpool corporation", "house_business"),  # its title, another case
            ],
        )
        assert result.operations == []

    def test_an_id_from_another_dataset_is_not_recognized(self, repo, house):
        result = plan(
            repo, house, [typing("Cabin fridge", "house_appliance", entity_id=house["elsewhere"])]
        )
        assert [o.draft.fields["title"] for o in result.operations] == ["Cabin fridge"]

    def test_near_matches_become_alternatives_of_the_dataset(self, repo, house):
        near = [
            {"entity_id": house["fridge"], "label": "Kitchen refrigerator", "similarity": 0.931},
            {"entity_id": house["elsewhere"], "label": "Cabin fridge", "similarity": 0.95},
            {"entity_id": "gone", "label": "Gone", "similarity": 0.99},
        ]
        result = plan(repo, house, [typing("WRF555 fridge", "house_appliance", near=near)])
        assert result.operations[0].draft.alternatives == [
            {"kind": "existing", "entity_id": house["fridge"], "similarity": 0.931}
        ]

    def test_relationships_point_at_refs_and_existing_ids(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("WRF555", "house_appliance"),
                typing("Acme", "house_business"),
                typing("Whirlpool Corporation", "house_business", entity_id=house["whirlpool"]),
                relation("WRF555", house["made_by"], "Acme", [passage("made by Acme", 130, 2)]),
                relation("WRF555", house["made_by"], "Whirlpool Corporation", confidence=0.9),
                relation(
                    "Kitchen refrigerator",
                    house["made_by"],
                    "Acme",
                    subject_id=house["fridge"],
                ),
            ],
        )
        relationships = [o for o in result.operations if o.draft.kind == "relationship"]
        assert [o.draft.fields for o in relationships] == [
            {"source_id": "$i1", "target_id": "$i2", "property_definition_id": house["made_by"]},
            {
                "source_id": "$i1",
                "target_id": house["whirlpool"],
                "property_definition_id": house["made_by"],
            },
            {
                "source_id": house["fridge"],
                "target_id": "$i2",
                "property_definition_id": house["made_by"],
            },
        ]
        assert [o.needs for o in relationships] == [
            frozenset({"i1", "i2"}),
            frozenset({"i1"}),
            frozenset({"i2"}),
        ]
        assert relationships[0].draft.evidence == [
            {"source_id": SOURCE, "page": 2, "start": 130, "end": 142, "quote": "made by Acme"}
        ]
        assert relationships[1].draft.probability == 0.9

    def test_unresolvable_existing_and_literal_relationships_are_skipped(
        self, ontology, repo, house
    ):
        ontology.create_relationship(house["fridge"], house["whirlpool"], house["made_by"])
        literal = relation("WRF555", house["made_by"], "x")
        literal["object"] = {"kind": "literal", "value": "25 cu ft"}
        result = plan(
            repo,
            house,
            [
                typing("WRF555", "house_appliance"),
                relation("WRF555", house["made_by"], "Nobody"),
                relation("WRF555", "no-such-type", "Acme"),
                relation(
                    "Kitchen refrigerator",
                    house["made_by"],
                    "Whirlpool Corporation",
                    subject_id=house["fridge"],
                    object_id=house["whirlpool"],
                ),
                literal,
            ],
        )
        assert [o.draft.kind for o in result.operations] == ["individual"]
        assert [s["reason"] for s in result.skipped] == [
            "unresolved_endpoint",
            "unresolved_predicate",
            "exists",
            "literal",
        ]

    def test_relationships_whose_ends_dont_fit_the_type_are_skipped(self, ontology, repo, house):
        # made_by runs Appliance -> Business; a Manufacturer is a Business.
        ontology.create_class(house["scheme"], "Manufacturer", parent_class_id=house["business"])
        result = plan(
            repo,
            house,
            [
                typing("WRF555", "house_appliance"),
                typing("Acme", "Manufacturer"),
                relation(
                    "WRF555", house["made_by"], "Kitchen refrigerator", object_id=house["fridge"]
                ),
                relation(
                    "Whirlpool Corporation",
                    house["made_by"],
                    "WRF555",
                    subject_id=house["whirlpool"],
                ),
                relation("WRF555", house["made_by"], "Acme"),
            ],
        )
        relationships = [
            o.draft.fields for o in result.operations if o.draft.kind == "relationship"
        ]
        assert relationships == [
            {"source_id": "$i1", "target_id": "$i2", "property_definition_id": house["made_by"]}
        ]
        assert result.skipped == [
            {"label": "WRF555 made_by Kitchen refrigerator", "reason": "domain_range_mismatch"},
            {"label": "Whirlpool Corporation made_by WRF555", "reason": "domain_range_mismatch"},
        ]


class TestProposeIndividuals:
    def test_a_run_becomes_one_pipeline_proposal_in_the_dataset(self, service, repo, house):
        outcome = SourceProposer(service, repo).propose_individuals(
            "run-1",
            run_input(house, pages="2-3", extraction_id="x-1", **started(5)),
            [
                typing("WRF555", "house_appliance", [passage("WRF555", 120, 2)]),
                typing("Acme", "house_business"),
                relation("WRF555", house["made_by"], "Acme"),
            ],
        )

        proposal = service.get(outcome.proposal_id)
        assert proposal.title == "Extraction: WRF555 use and care guide"
        assert proposal.source.value == "pipeline"
        assert proposal.source_detail == "individual_extraction run run-1 on source src-manual"
        assert proposal.dataset_id == house["home"]
        assert proposal.client_metadata == {
            "source_id": SOURCE,
            "run_id": "run-1",
            "pipeline": "individual_extraction",
            "pages": "2-3",
            "extraction_id": "x-1",
            "extraction_started_at": "2026-11-11T10:05:00+00:00",
        }
        assert [(o.kind.value, o.ref) for o in proposal.operations] == [
            ("individual", "i1"),
            ("individual", "i2"),
            ("relationship", None),
        ]
        assert outcome.operations == 3
        assert outcome.to_json()["proposal_id"] == proposal.id

    def test_refused_operations_are_dropped_with_their_dependents(
        self, service, repo, house, monkeypatch
    ):
        triples = [
            typing("WRF555", "house_appliance"),
            typing("Acme", "house_business"),
            typing("Maytag", "house_business"),
            relation("WRF555", house["made_by"], "Acme"),
            relation("WRF555", house["made_by"], "Maytag"),
        ]
        # Acme's create is refused (its class is gone by the time it is proposed)
        real = service.propose

        def refusing(**kwargs):
            for draft in kwargs["operations"]:
                if draft.fields.get("title") == "Acme":
                    draft.fields["class_ids"] = ["no-such-class"]
            return real(**kwargs)

        monkeypatch.setattr(service, "propose", refusing)
        outcome = SourceProposer(service, repo).propose_individuals("r", run_input(house), triples)

        proposal = service.get(outcome.proposal_id)
        titles = [
            o.fields.get("title") for o in proposal.operations if o.kind.value == "individual"
        ]
        assert titles == ["WRF555", "Maytag"]
        [link] = [o for o in proposal.operations if o.kind.value == "relationship"]
        assert link.fields["target_id"] == "$i3"
        assert [r["label"] for r in outcome.refused] == ["Acme", "WRF555 made_by Acme"]
        assert outcome.refused[1]["error"] == "points at a refused operation"
        assert any(w.startswith("Refused Acme") for w in outcome.warnings)

    def test_nothing_to_propose_makes_no_proposal_and_says_why(self, service, repo, house):
        outcome = SourceProposer(service, repo).propose_individuals(
            "r",
            run_input(house),
            [
                typing("Gizmo", "no_such_class"),
                typing("Widget", "no_such_class"),
                relation("Gizmo", house["made_by"], "Widget"),
            ],
        )
        assert outcome.proposal_id is None
        reason = (
            "None of the 3 candidates made an operation (missing_class 2, unresolved_endpoint 1)."
        )
        assert outcome.no_proposal_reason == reason
        assert outcome.warnings == [f"Nothing to propose. {reason}"]
        summary = outcome.to_json()
        assert summary["no_proposal_reason"] == reason
        assert summary["skipped_by_reason"] == {"missing_class": 2, "unresolved_endpoint": 1}
        assert service.list_proposals() == []

    def test_a_run_that_found_nothing_says_so(self, service, repo, house):
        outcome = SourceProposer(service, repo).propose_individuals("r", run_input(house), [])
        assert outcome.to_json()["no_proposal_reason"] == "The run found no candidates in the text."
        assert outcome.to_json()["skipped_by_reason"] == {}

    def test_a_proposal_gives_no_reason_and_an_individual_rationale(self, service, repo, house):
        outcome = SourceProposer(service, repo).propose_individuals(
            "r", run_input(house), [typing("WRF555", "house_appliance")]
        )
        assert outcome.to_json()["no_proposal_reason"] is None
        rationale = service.get(outcome.proposal_id).rationale
        assert rationale.startswith(
            "Individuals and relationships found in the source 'WRF555 use and care guide'."
        )

    def test_re_extracting_supersedes_the_earlier_open_proposal(self, service, repo, house):
        proposer = SourceProposer(service, repo)
        first = proposer.propose_individuals("r1", run_input(house), [typing("A", "Business")])
        other_dataset = proposer.propose_individuals(
            "r0", run_input(house, dataset="cabin"), [typing("C", "Business")]
        )
        second = proposer.propose_individuals("r2", run_input(house), [typing("B", "Business")])

        older = service.get(first.proposal_id)
        assert older.status is ProposalStatus.DONE
        assert [o.status for o in older.operations] == [OperationStatus.REJECTED]
        assert older.operations[0].reason == (
            f"superseded by extraction proposal {second.proposal_id}"
        )
        assert service.get(second.proposal_id).status is ProposalStatus.OPEN
        assert service.get(other_dataset.proposal_id).status is ProposalStatus.OPEN

    def test_another_page_selection_is_left_open(self, service, repo, house):
        proposer = SourceProposer(service, repo)
        first = proposer.propose_individuals(
            "r1", run_input(house, pages="1-10", **started(1)), [typing("A", "Business")]
        )
        second = proposer.propose_individuals(
            "r2", run_input(house, pages="11-20", **started(2)), [typing("B", "Business")]
        )
        third = proposer.propose_individuals(
            "r3", run_input(house, pages="1-10", **started(3)), [typing("C", "Business")]
        )

        assert service.get(first.proposal_id).status is ProposalStatus.DONE
        assert service.get(second.proposal_id).status is ProposalStatus.OPEN
        assert service.get(third.proposal_id).status is ProposalStatus.OPEN
        assert service.get(third.proposal_id).client_metadata["pages"] == "1-10"

    def test_an_older_extraction_finishing_late_never_supersedes_a_newer_one(
        self, service, repo, house
    ):
        proposer = SourceProposer(service, repo)
        newer = proposer.propose_individuals(
            "r2", run_input(house, **started(2)), [typing("B", "Business")]
        )
        late = proposer.propose_individuals(
            "r1", run_input(house, **started(1)), [typing("A", "Business")]
        )

        assert service.get(newer.proposal_id).status is ProposalStatus.OPEN
        stale = service.get(late.proposal_id)
        assert [o.status for o in stale.operations] == [OperationStatus.REJECTED]
        assert stale.operations[0].reason == (
            f"superseded by extraction proposal {newer.proposal_id}"
        )
        assert stale.client_metadata["extraction_started_at"] == started(1)["extraction_started_at"]

    def test_a_failure_to_supersede_is_a_warning_and_the_proposal_stands(
        self, service, repo, house, monkeypatch
    ):
        proposer = SourceProposer(service, repo)
        first = proposer.propose_individuals(
            "r1", run_input(house, **started(1)), [typing("A", "Business")]
        )

        def broken(*args, **kwargs):
            raise RuntimeError("database is locked")

        monkeypatch.setattr(service, "reject", broken)
        second = proposer.propose_individuals(
            "r2", run_input(house, **started(2)), [typing("B", "Business")]
        )

        assert second.proposal_id is not None
        assert service.get(second.proposal_id).status is ProposalStatus.OPEN
        assert service.get(first.proposal_id).status is ProposalStatus.OPEN
        assert second.warnings == [
            f"Could not supersede proposal {first.proposal_id}: database is locked"
        ]

    def test_a_derived_class_sharing_a_title_does_not_hide_the_real_one(
        self, ontology, repo, house
    ):
        computed = ontology.create_scheme(taxonomy_id=house["taxonomy"], title="Computed views")
        ontology.create_class(computed.id, "Widget", derived=True)
        concrete = ontology.create_scheme(taxonomy_id=house["taxonomy"], title="Things")
        widget = ontology.create_class(concrete.id, "Widget")

        result = plan(repo, house, [typing("Sprocket", "Widget")])

        assert [o.draft.fields["class_ids"] for o in result.operations] == [[widget.id]]


class TestMirroredTaxonomy:
    @pytest.mark.parametrize("via", ["api", "chat", None])
    def test_schema_proposals_to_a_mirrored_taxonomy_are_refused_before_any_model_call(
        self, ontology, service, repo, house, via
    ):
        ontology.set_taxonomy_mirrored(house["taxonomy"], True)
        llm = FakeLLMProvider(response_content="[]")
        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=llm,
            ontology_repo=repo,
            run_id="run-s",
            proposer=SourceProposer(service, repo),
        )
        state = SchemaExtractionState(
            run_id="run-s",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data={
                "documents": ["A water filter."],
                "scope": house["taxonomy"],
                "source_id": SOURCE,
                **({"requested_via": via} if via else {}),
            },
        )

        with pytest.raises(PipelineInputError, match="mirrors an external source"):
            asyncio.run(orchestrator.execute(state))
        assert llm.call_count == 0
        assert service.list_proposals() == []

    def test_its_client_over_mcp_may_propose(self, ontology, service, repo, house):
        ontology.set_taxonomy_mirrored(house["taxonomy"], True)
        SourceProposer(service, repo).check_may_propose(house["taxonomy"], {"requested_via": "mcp"})


class TestProposeSchema:
    def test_candidates_become_class_predicate_and_type_creates(self, service, repo, house):
        candidates = [
            {
                "kind": "class",
                "label": "Water Filter",
                "proposed_definition": "A replaceable filter",
                "confidence": 0.8,
                "provenance": [{"quote": "water filter", "start": 105, "end": 117}],
            },
            {"kind": "class", "label": "appliance", "confidence": 0.9, "provenance": []},
            {
                "kind": "property_definition",
                "label": "filters for",
                "proposed_domain": "Water Filter",
                "proposed_range": "Appliance",
                "confidence": 0.7,
                "provenance": [],
            },
        ]
        outcome = SourceProposer(service, repo).propose_schema(
            "run-s", {"source_id": SOURCE, "scope": house["taxonomy"]}, candidates
        )

        proposal = service.get(outcome.proposal_id)
        assert proposal.dataset_id is None
        assert proposal.client_metadata["pipeline"] == "schema_extraction"
        ops = proposal.operations
        assert [(o.kind.value, o.ref) for o in ops] == [
            ("class", "c1"),
            ("predicate", "p2"),
            ("property", "r3"),
        ]
        assert ops[0].fields == {
            "concept_scheme_id": house["scheme"],
            "title": "Water Filter",
            "identifier": "water_filter",
            "description": "A replaceable filter",
        }
        assert proposal.rationale.startswith(
            f"Classes and relationship types the source {SOURCE!r} names that the taxonomy lacks."
        )
        assert "individual" not in proposal.rationale
        assert ops[0].evidence == [
            {"source_id": SOURCE, "page": None, "start": 105, "end": 117, "quote": "water filter"}
        ]
        assert ops[2].fields["domain_class_id"] == "$c1"
        assert ops[2].fields["range_class_id"] == house["appliance"]
        assert ops[2].fields["canonical_predicate"] == "filters_for"
        assert outcome.skipped == [{"label": "appliance", "reason": "exists"}]

    def test_a_class_never_takes_a_relationship_types_identifier(self, ontology, repo, house):
        ontology.create_property_definition(
            "renter",
            "rented by",
            domain_class_id=house["appliance"],
            range_class_id=house["business"],
        )
        candidates = [
            {"kind": "class", "label": "Owner", "confidence": 0.8, "provenance": []},
            {"kind": "class", "label": "Renter", "confidence": 0.8, "provenance": []},
            {"kind": "property_definition", "label": "owner", "confidence": 0.7},
        ]
        result = plan_schema_operations(
            candidates, repo, taxonomy_id=house["taxonomy"], source_id=SOURCE, page_starts=[]
        )
        identifiers = {
            o.draft.kind.value: o.draft.fields["identifier"]
            for o in result.operations
            if o.draft.kind.value != "class"
        }
        classes = [
            o.draft.fields["identifier"] for o in result.operations if o.draft.kind.value == "class"
        ]
        assert identifiers == {"predicate": "owner", "property": "owner"}
        assert classes == ["owner_2", "renter_2"]

    def test_class_creates_get_unique_identifiers_from_their_titles(self, ontology, repo, house):
        ontology.create_class(house["scheme"], "Old heater", identifier="heating_system")
        candidates = [
            {"kind": "class", "label": label, "confidence": 0.8, "provenance": []}
            for label in ("Heating System", "Heating-System!", "3D Printer", "X")
        ]
        result = plan_schema_operations(
            candidates, repo, taxonomy_id=house["taxonomy"], source_id=SOURCE, page_starts=[]
        )
        assert [o.draft.fields["identifier"] for o in result.operations] == [
            "heating_system_2",
            "heating_system_3",
            "class_3d_printer",
            "class_x",
        ]
