"""
Unit tests for the pre-review stage's seeded errors: building them from gold
and scoring a stage on them. Fake stages only; no model call.
"""

import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.extraction.entities import (
    PreReviewAnswer,
    PreReviewPart,
    PreReviewQuestion,
    PreReviewVerdict,
)
from tests.integration.pipelines._harness.benchmark import (
    Gold,
    GoldIndividual,
    Passage,
    load_gold,
    load_schema_bundle,
)
from tests.integration.pipelines._harness.pre_review_seeded import (
    CONTROL,
    MERGE,
    RETYPE_REALISTIC,
    RETYPE_SAME_LAYER,
    SPLIT_TRAP,
    ClassCatalog,
    build_seeded,
    gate,
    recorded_mistypes,
    score_seeded,
    wilson,
)

TEXT = (
    "Use a Torx driver and a Phillips screwdriver to remove the panel.\n\n"
    "The ice maker is fed by the water line.\n\n"
    "Newcomers and Junior Contributors edit first."
)


def _individual(key, title, class_ref, acceptable=()):
    start = TEXT.lower().index(title.lower())
    end = start + len(title)
    return GoldIndividual(
        key=key,
        title=title,
        class_ref=class_ref,
        tier="core",
        acceptable=frozenset(acceptable),
        evidence=(Passage(start, end, TEXT[start:end]),),
    )


GOLD = Gold(
    document_id="toy",
    individuals=(
        _individual("torx", "Torx driver", "tech.tool"),
        _individual("phillips", "Phillips screwdriver", "tech.tool"),
        _individual("ice", "Ice maker", "tech.appliance", acceptable=("tech.device",)),
        _individual("line", "Water line", "tech.supply"),
        _individual("newcomers", "Newcomers and Junior Contributors", "biz.role"),
    ),
    relationships=(),
    excluded=frozenset(),
    source_text=TEXT,
)

CATALOG = ClassCatalog(
    refs=("biz.actor", "biz.role", "tech.appliance", "tech.device", "tech.supply", "tech.tool"),
    confusable={
        "tech.tool": frozenset({"tech.supply"}),
        "tech.supply": frozenset({"tech.tool"}),
        "tech.appliance": frozenset({"tech.device", "tech.tool"}),
        "biz.role": frozenset({"biz.actor"}),
    },
)


def _seeded(take=1, **counts):
    sizes = {"merges": 1, "realistic": 1, "same_layer": 1, **counts}
    return build_seeded(GOLD, CATALOG, take, **sizes)


def _index(document, stratum):
    return next(i for i, seed in document.seeds.items() if seed.stratum == stratum)


def test_a_merge_joins_two_individuals_of_one_class_in_one_paragraph():
    document = _seeded()
    merged = document.items[_index(document, MERGE)]
    assert merged.title in (
        "Torx driver and Phillips screwdriver",
        "Torx driver, Phillips screwdriver",
    )
    assert merged.class_ref == "tech.tool"
    assert merged.witness
    assert document.seeds[_index(document, MERGE)].gold_keys == ("torx", "phillips")


def test_a_retype_plants_a_class_gold_does_not_accept():
    document = _seeded()
    for stratum in (RETYPE_REALISTIC, RETYPE_SAME_LAYER):
        seed = document.seeds[_index(document, stratum)]
        individual = next(g for g in GOLD.individuals if g.key == seed.gold_keys[0])
        assert not individual.accepts(seed.planted_class)
        assert document.items[_index(document, stratum)].class_ref == seed.planted_class


def test_a_list_shaped_gold_title_is_a_split_trap_and_never_merged():
    document = _seeded(merges=5, realistic=0, same_layer=0)
    trap = document.items[_index(document, SPLIT_TRAP)]
    assert trap.title == "Newcomers and Junior Contributors"
    assert all(
        "Newcomers" not in document.items[i].title
        for i, s in document.seeds.items()
        if s.stratum == MERGE
    )


def test_the_same_take_plants_the_same_seeds():
    assert _seeded(take=2) == _seeded(take=2)


def test_fewer_seeds_are_planted_when_gold_has_too_few_candidates():
    counts = _seeded(merges=8, realistic=6, same_layer=6).stratum_counts()
    assert counts[MERGE] == 1
    assert sum(counts.values()) == len(_seeded(merges=8, realistic=6, same_layer=6).items)


def _retype(item, class_ref):
    return PreReviewVerdict(
        PreReviewAnswer.RETYPE,
        PreReviewQuestion.RETYPE,
        "r",
        item.title,
        item.class_ref,
        class_ref=class_ref,
    )


def _split(item, *titles):
    parts = tuple(PreReviewPart(title, item.class_ref) for title in titles)
    return PreReviewVerdict(
        PreReviewAnswer.SPLIT, PreReviewQuestion.SPLIT, "s", item.title, item.class_ref, parts=parts
    )


def test_a_stage_that_keeps_everything_misses_every_seed_and_harms_nothing():
    document = _seeded()
    score = score_seeded(document, GOLD, {})
    assert score.strata[MERGE].missed == 1
    assert score.strata[RETYPE_REALISTIC].missed == 1
    assert score.control_harms() == (
        0,
        score.strata[CONTROL].items + score.strata[SPLIT_TRAP].items,
    )
    assert score.precision() is None


def test_putting_seeds_right_is_counted_as_fixes():
    document = _seeded()
    merge = _index(document, MERGE)
    realistic = _index(document, RETYPE_REALISTIC)
    key = document.seeds[realistic].gold_keys[0]
    gold_class = next(g.class_ref for g in GOLD.individuals if g.key == key)
    verdicts = {
        merge: _split(document.items[merge], "Torx drivers", "Phillips screwdriver"),
        realistic: _retype(document.items[realistic], gold_class),
    }
    score = score_seeded(document, GOLD, verdicts)
    assert score.strata[MERGE].fixed == 1
    assert score.strata[RETYPE_REALISTIC].fixed == 1
    assert score.recovery(MERGE) == 1.0
    assert score.precision() == 1.0


def test_a_split_whose_parts_miss_a_gold_name_is_changed_wrongly():
    document = _seeded()
    merge = _index(document, MERGE)
    score = score_seeded(
        document, GOLD, {merge: _split(document.items[merge], "Torx driver", "Panel")}
    )
    assert score.strata[MERGE].changed_wrongly == 1
    assert score.strata[MERGE].fixed == 0


def test_changing_a_correct_item_is_a_harm_unless_gold_accepts_it():
    document = _seeded(merges=0, realistic=0, same_layer=0)
    by_title = {item.title: item for item in document.items}
    verdicts = {
        by_title["Ice maker"].index: _retype(by_title["Ice maker"], "tech.device"),  # acceptable
        by_title["Water line"].index: _retype(by_title["Water line"], "tech.tool"),  # not
        by_title["Newcomers and Junior Contributors"].index: _split(
            by_title["Newcomers and Junior Contributors"], "Newcomers", "Junior Contributors"
        ),
    }
    score = score_seeded(document, GOLD, verdicts)
    assert score.strata[CONTROL].neutral == 1
    assert score.strata[CONTROL].harmed_by == {"split": 0, "retype": 1}
    assert score.strata[SPLIT_TRAP].harmed_by == {"split": 1, "retype": 0}
    assert score.control_harms("split") == (1, 5)
    assert score.precision() == 0.0


def test_unsure_is_counted_and_changes_nothing():
    document = _seeded()
    realistic = _index(document, RETYPE_REALISTIC)
    item = document.items[realistic]
    unsure = PreReviewVerdict(
        PreReviewAnswer.UNSURE, None, "Tool or supply?", item.title, item.class_ref
    )
    score = score_seeded(document, GOLD, {realistic: unsure})
    assert score.strata[RETYPE_REALISTIC].unsure == 1
    assert score.strata[RETYPE_REALISTIC].missed == 1


def test_the_wilson_interval():
    assert wilson(0, 0) == (0.0, 1.0)
    low, high = wilson(0, 441)
    assert low == 0.0 and high == pytest.approx(0.0086, abs=0.0005)
    low, high = wilson(50, 100)
    assert low == pytest.approx(0.404, abs=0.001) and high == pytest.approx(0.596, abs=0.001)


def test_the_gate_needs_recovery_and_few_harms():
    document = _seeded(merges=0, realistic=0, same_layer=0)
    score = score_seeded(document, GOLD, {})
    assert [g.passed for g in gate(score)] == [False, False]
    retype_gate, split_gate = gate(score)
    assert retype_gate.question == "retype" and split_gate.question == "split"
    assert retype_gate.needed == 0.5 and split_gate.needed == 0.6


def test_recorded_mistypes_are_the_classes_gold_does_not_accept():
    found = recorded_mistypes(
        GOLD, [("Torx drivers", "tech.supply"), ("Ice maker", "tech.device"), ("Panel", "x")]
    )
    assert found == {"torx": {"tech.supply"}}


def test_the_real_benchmark_seeds_every_stratum():
    """The dev gold and the DR schema give every stratum for every take (no model call)."""
    catalog = ClassCatalog.from_bundle(load_schema_bundle())
    assert catalog.confusable["application.applicationfunction"]
    for document_id in ("edit_check", "gitlab_architecture"):
        gold = load_gold(document_id)
        for take in (1, 2, 3):
            counts = build_seeded(gold, catalog, take).stratum_counts()
            assert counts[MERGE] >= 1
            assert counts[RETYPE_REALISTIC] == 6
            assert counts[RETYPE_SAME_LAYER] == 6
            assert counts[CONTROL] > 0
