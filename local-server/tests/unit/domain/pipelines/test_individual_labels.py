"""
Unit tests (#1575): individual labels that name the same thing merge.

Diagram letters ("(A)"), plurals, apostrophes and corporate suffixes no longer
split one individual into several, across chunks or within a proposal; the
merged individual shows its plainest capitalized label. A one-word mention that
is the head word of exactly one other mention of the same classes folds into
it. A new individual whose label, without a leading brand, is an existing
individual's offers it as a near match.

Merging must not go too far: the same name with different diagram letters
("Screw (B)", "Screw (D)") is different parts, plural-only nouns ("Safety
Glasses") are not plurals, and a two-word name is not its head noun ("Hand
Shower" is not "Shower"), and a name with a corporate suffix typed with another
class than the name without one is another thing ("Wikimedia Enterprise" the
product, "Wikimedia Enterprise LLC" the business).
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.extraction.chunking import Chunk
from domain.pipelines.individual_extraction.chunk_merge import merge_chunk_triples
from domain.pipelines.individual_extraction.labels import (
    LabelKeys,
    individual_key,
    preferred_label,
    surface_label,
    without_corporate_mark,
    without_leading_word,
)
from tests.unit.domain.pipelines.test_source_proposals import (  # noqa: F401 - fixtures
    house,
    ontology,
    passage,
    plan,
    proposals,
    publisher,
    relation,
    repo,
    reverter,
    typing,
)


class TestIndividualKey:
    @pytest.mark.parametrize(
        "labels",
        [
            ["Moen", "Moen Incorporated", "Moen Inc.", "Moen, Inc.", "MOEN Corp.", "Moen LLC"],
            ["Painter's Tape", "painters tape", "Painter’s  Tape"],
            ["Adhesive Disk", "adhesive disk (A)", "Adhesive Disks"],
            ["Screw", "screws (D)", "screw ( D )"],
            ["Wall Anchor", "wall anchors (C)"],
            ["Battery", "batteries"],
            ["Box", "boxes"],
            ["Acme Ltd.", "Acme Co.", "Acme & Co."],
        ],
    )
    def test_forms_of_one_name_share_a_key(self, labels):
        assert len({individual_key(label) for label in labels}) == 1

    @pytest.mark.parametrize(
        "one, other",
        [
            ("Glass", "Glas"),  # "ss" is not a plural
            ("Status", "Statu"),  # nor "us"
            ("AWS", "AW"),  # acronyms are left alone
            ("Inc.", ""),  # a suffix alone is the name
            ("Hand Shower Dock", "Dock"),  # head nouns are not keys
            ("Python (programming language)", "Python"),  # only one-letter callouts go
            ("Safety Glasses", "Safety Glass"),  # plural-only nouns stay as they are
            ("Pliers", "Plier"),
        ],
    )
    def test_different_names_keep_different_keys(self, one, other):
        assert individual_key(one) != individual_key(other)

    def test_surface_label_drops_only_a_trailing_diagram_letter(self):
        assert surface_label("  adhesive   disk (A) ") == "adhesive disk"
        assert surface_label("(A)") == "(A)"
        assert surface_label("Plan (A) review") == "Plan (A) review"

    @pytest.mark.parametrize(
        "labels, shown",
        [
            (["Moen Incorporated", "Moen Inc.", "Moen"], "Moen"),
            (["painters tape", "Painter's Tape"], "Painter's Tape"),
            (["adhesive disk (A)", "Adhesive Disk"], "Adhesive Disk"),
            (["screws (D)", "Screw"], "Screw"),
            (["adhesive disk (A)"], "adhesive disk"),
            (["anchors (C)"], "anchors"),
        ],
    )
    def test_the_preferred_label_is_the_plain_capitalized_form(self, labels, shown):
        assert preferred_label(labels) == shown

    @pytest.mark.parametrize(
        "key, shorter",
        [
            ("moen handheld shower", "handheld shower"),
            ("hand shower", None),  # a two-word name is not its head noun
            ("wall anchor", None),
            ("hex screw (b)", None),  # a kept diagram letter is not a word
            ("shower", None),
        ],
    )
    def test_only_a_key_of_three_words_or_more_drops_its_leading_word(self, key, shorter):
        assert without_leading_word(key) == shorter


class TestLabelKeys:
    def test_one_diagram_letter_is_a_callout_that_drops(self):
        keys = LabelKeys(["Screw", "screws (D)", "Adhesive Disk", "adhesive disk (A)"])
        assert keys.key("Screw") == keys.key("screws (D)")
        assert keys.key("Adhesive Disk") == keys.key("adhesive disk (A)")
        assert keys.preferred_label(["screws (D)", "Screw"]) == "Screw"

    def test_one_name_with_different_letters_is_different_parts(self):
        keys = LabelKeys(
            ["Screw (B)", "screws (D)", "Screw (d)", "Screw", "Washer (B)", "Washer (G)"]
        )
        assert keys.key("Screw (B)") != keys.key("screws (D)")
        assert keys.key("screws (D)") == keys.key("Screw (d)")
        assert keys.key("Washer (B)") != keys.key("Washer (G)")
        # Without a letter the name is neither part
        assert keys.key("Screw") not in {keys.key("Screw (B)"), keys.key("Screw (D)")}

    def test_a_kept_letter_is_shown(self):
        keys = LabelKeys(["Screw (B)", "screws (D)", "Screw (D)"])
        assert keys.preferred_label(["screws (D)", "Screw (D)"]) == "Screw (D)"
        assert keys.preferred_label(["Screw (B)"]) == "Screw (B)"

    @pytest.mark.parametrize(
        "typed",
        [
            [],  # no classes known
            [("Moen", "business"), ("Moen Inc.", "business"), ("Moen Incorporated", "business")],
            [("Moen", "business"), ("Moen Inc.", "business"), ("Moen Inc.", "brand")],
            [("Moen Inc.", "business")],  # the name without a suffix is not typed
            [("Moen", "product")],  # nor the name with one
        ],
    )
    def test_a_corporate_suffix_is_a_variant_unless_typed_with_another_class(self, typed):
        keys = LabelKeys(["Moen", "Moen Inc.", "Moen Incorporated"], typed=typed)
        assert keys.key("Moen") == keys.key("Moen Inc.") == keys.key("Moen Incorporated")

    def test_a_corporate_suffix_typed_with_another_class_is_another_thing(self):
        labels = ["Wikimedia Enterprise", "Wikimedia Enterprise LLC", "Wikimedia Enterprise, Inc."]
        keys = LabelKeys(
            [*labels, "Moen", "Moen Inc."],
            typed=[
                ("Wikimedia Enterprise", "product"),
                ("Wikimedia Enterprise LLC", "business"),
                ("Moen", "business"),
                ("Moen Inc.", "business"),
            ],
        )
        assert keys.key("Wikimedia Enterprise") != keys.key("Wikimedia Enterprise LLC")
        assert keys.key("wikimedia enterprises") == keys.key("Wikimedia Enterprise")
        # Any suffix names the business
        assert keys.key("Wikimedia Enterprise, Inc.") == keys.key("Wikimedia Enterprise LLC")
        assert keys.preferred_label(labels[1:]) == "Wikimedia Enterprise LLC"
        assert keys.preferred_label(labels[:1]) == "Wikimedia Enterprise"
        assert keys.key("Moen") == keys.key("Moen Inc.")
        assert without_corporate_mark(keys.key("Wikimedia Enterprise LLC")) == keys.key(
            "Wikimedia Enterprise"
        )


def _typing(label, class_label="Part", quote=None, start=None):
    return {
        "subject": {"kind": "individual", "id": "", "label": label},
        "predicate": {"property_definition_id": "", "label": "is_a"},
        "object": {"kind": "class", "id": "", "label": class_label},
        "confidence": 0.8,
        "provenance": {
            "quote": quote,
            "start": start,
            "end": start + len(quote) if quote and start is not None else None,
        },
    }


def _relation(subject, obj, quote, start):
    return {
        "subject": {"kind": "individual", "id": "", "label": subject},
        "predicate": {"property_definition_id": "", "label": "fastens"},
        "object": {"kind": "individual", "id": "", "label": obj},
        "confidence": 0.7,
        "provenance": {"quote": quote, "start": start, "end": start + len(quote)},
    }


class TestChunkMerge:
    def test_diagram_letters_plurals_and_suffixes_merge_across_chunks(self):
        first = Chunk(index=0, start=0, end=100)
        second = Chunk(index=1, start=100, end=200)
        merged = merge_chunk_triples(
            [
                (
                    first,
                    [
                        _typing("adhesive disk (A)", quote="disk", start=1),
                        _typing("screws (D)", quote="screws", start=10),
                        _typing("Moen Incorporated", "Business", quote="Moen", start=20),
                    ],
                ),
                (
                    second,
                    [
                        _typing("Adhesive Disk", quote="Disk", start=1),
                        _typing("Screw", quote="Screw", start=10),
                        _typing("Moen Inc.", "Business", quote="Moen", start=20),
                        _typing("Moen", "Business", quote="Moen", start=40),
                    ],
                ),
            ]
        )
        assert [(t["subject"]["label"], len(t["passages"])) for t in merged] == [
            ("Adhesive Disk", 2),
            ("Screw", 2),
            ("Moen", 3),
        ]

    def test_relationships_take_the_merged_labels(self):
        chunk = Chunk(index=0, start=0, end=100)
        merged = merge_chunk_triples(
            [
                (chunk, [_typing("Screw"), _relation("screws (D)", "wall anchors (C)", "s", 0)]),
                (chunk, [_typing("Wall Anchor"), _relation("Screw", "Wall Anchor", "S", 50)]),
            ]
        )
        relations = [t for t in merged if t["predicate"]["label"] == "fastens"]
        assert [(t["subject"]["label"], t["object"]["label"]) for t in relations] == [
            ("Screw", "Wall Anchor")
        ]
        assert len(relations[0]["passages"]) == 2

    def test_one_name_with_different_letters_stays_different_parts(self):
        first = Chunk(index=0, start=0, end=100)
        second = Chunk(index=1, start=100, end=200)
        merged = merge_chunk_triples(
            [
                (
                    first,
                    [
                        _typing("Screw (B)", quote="Screw", start=1),
                        _typing("Screw (D)", quote="Screw", start=10),
                        _relation("Screw (B)", "Washer (B)", "B", 20),
                    ],
                ),
                (
                    second,
                    [
                        _typing("screws (D)", quote="screws", start=1),
                        _typing("Screw", quote="Screw", start=10),
                        _relation("Screw (D)", "Washer (G)", "D", 20),
                    ],
                ),
            ]
        )
        assert [(t["subject"]["label"], len(t["passages"])) for t in merged[:2]] == [
            ("Screw (B)", 1),
            ("Screw (D)", 2),
        ]
        assert merged[3]["subject"]["label"] == "Screw"
        relations = [t for t in merged if t["predicate"]["label"] == "fastens"]
        assert [(t["subject"]["label"], t["object"]["label"]) for t in relations] == [
            ("Screw (B)", "Washer (B)"),
            ("Screw (D)", "Washer (G)"),
        ]

    def test_a_corporate_suffix_typed_with_another_class_stays_another_individual(self):
        first = Chunk(index=0, start=0, end=100)
        second = Chunk(index=1, start=100, end=200)
        merged = merge_chunk_triples(
            [
                (
                    first,
                    [
                        _typing("Wikimedia Enterprise", "Product", quote="Enterprise", start=1),
                        _typing("Wikimedia Enterprise LLC", "Business", quote="LLC", start=30),
                    ],
                ),
                (
                    second,
                    [
                        _typing("Wikimedia Enterprise", "Product", quote="Enterprise", start=5),
                        _relation("Wikimedia Enterprise, LLC", "Wikimedia Enterprise", "runs", 40),
                    ],
                ),
            ]
        )
        assert [
            (t["subject"]["label"], t["object"]["label"], [p["start"] for p in t["passages"]])
            for t in merged
        ] == [
            ("Wikimedia Enterprise", "Product", [1, 105]),
            ("Wikimedia Enterprise LLC", "Business", [30]),
            ("Wikimedia Enterprise LLC", "Wikimedia Enterprise", [140]),
        ]

    def test_a_recognized_individual_keeps_its_title_and_lends_it(self):
        chunk = Chunk(index=0, start=0, end=100)
        recognized = _typing("Moen Incorporated", "Business")
        recognized["subject"]["id"] = "moen-id"
        merged = merge_chunk_triples(
            [(chunk, [recognized]), (chunk, [_relation("Screw", "Moen", "Moen", 0)])]
        )
        assert merged[0]["subject"] == {
            "kind": "individual",
            "id": "moen-id",
            "label": "Moen Incorporated",
        }
        assert merged[1]["object"]["label"] == "Moen Incorporated"


class TestPlannedIndividuals:
    def test_forms_of_one_name_are_one_create_with_the_preferred_title(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Moen", "house_business", [passage("Moen", 1, 1)], 0.6),
                typing("Moen Incorporated", "house_business", [passage("Moen", 110, 2)], 0.9),
                typing("Moen Inc.", "house_business"),
                typing("painters tape", "house_appliance"),
                typing("Painter's Tape", "house_appliance"),
                typing("screws (D)", "house_appliance"),
                typing("Screw", "house_appliance"),
            ],
        )
        assert [o.draft.fields["title"] for o in result.operations] == [
            "Moen",
            "Painter's Tape",
            "Screw",
        ]
        moen = result.operations[0].draft
        assert moen.probability == 0.9
        assert len(moen.evidence) == 2

    def test_a_corporate_suffix_typed_with_the_same_class_is_one_create(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Moen", "house_business", [passage("Moen", 1, 1)]),
                typing("Moen Inc.", "house_business", [passage("Moen Inc.", 110, 2)]),
                typing("Moen Incorporated", "house_business", [passage("Moen", 150, 2)]),
                # Typed with another class too, the forms still share one
                typing("Moen Inc.", "house_appliance"),
            ],
        )
        [create] = result.operations
        assert create.draft.fields == {
            "title": "Moen",
            "class_ids": [house["business"], house["appliance"]],
        }
        assert [e["start"] for e in create.draft.evidence] == [1, 110, 150]

    def test_a_corporate_suffix_typed_with_another_class_is_another_create(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Wikimedia Enterprise", "house_appliance", [passage("Enterprise", 1, 1)]),
                typing("Wikimedia Enterprise LLC", "house_business", [passage("LLC", 110, 2)]),
                typing("Wikimedia Enterprise", "house_appliance", [passage("Enterprise", 150, 2)]),
                relation("Wikimedia Enterprise", house["made_by"], "Wikimedia Enterprise, LLC"),
            ],
        )
        creates = [o.draft for o in result.operations if o.draft.kind == "individual"]
        assert [(d.fields["title"], d.fields["class_ids"]) for d in creates] == [
            ("Wikimedia Enterprise", [house["appliance"]]),
            ("Wikimedia Enterprise LLC", [house["business"]]),
        ]
        assert [[e["start"] for e in d.evidence] for d in creates] == [[1, 150], [110]]
        [relationship] = [o.draft for o in result.operations if o.draft.kind == "relationship"]
        assert relationship.fields["source_id"] == "$i1"
        assert relationship.fields["target_id"] == "$i2"
        assert result.skipped == []

    @pytest.mark.parametrize(
        "class_label, starts, made_by",
        [
            # The business: it folds into the name with the suffix
            ("house_business", [[1], [110, 150]], ["$i2"]),
            # The product, which nothing is made by
            ("house_appliance", [[1, 150], [110]], []),
        ],
    )
    def test_a_head_word_mention_folds_into_the_form_of_its_class(
        self, repo, house, class_label, starts, made_by
    ):
        result = plan(
            repo,
            house,
            [
                typing("Wikimedia Enterprise", "house_appliance", [passage("Enterprise", 1, 1)]),
                typing("Wikimedia Enterprise LLC", "house_business", [passage("LLC", 110, 2)]),
                typing("Enterprise", class_label, [passage("Enterprise", 150, 2)]),
                typing("Kitchen sink", "house_appliance"),
                relation("Kitchen sink", house["made_by"], "Enterprise"),
            ],
        )
        creates = [o.draft for o in result.operations if o.draft.kind == "individual"]
        assert [d.fields["title"] for d in creates] == [
            "Wikimedia Enterprise",
            "Wikimedia Enterprise LLC",
            "Kitchen sink",
        ]
        assert [[e["start"] for e in d.evidence] for d in creates[:2]] == starts
        # A relationship end named by the head word is the mention it folded into
        targets = [
            o.draft.fields["target_id"] for o in result.operations if o.draft.kind == "relationship"
        ]
        assert targets == made_by

    def test_relationships_resolve_any_form_of_the_name(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Hand Shower (E)", "house_appliance"),
                typing("Moen Inc.", "house_business"),
                relation("hand showers", house["made_by"], "Moen"),
            ],
        )
        [relationship] = [o for o in result.operations if o.draft.kind == "relationship"]
        assert relationship.draft.fields["source_id"] == "$i1"
        assert relationship.draft.fields["target_id"] == "$i2"

    def test_a_mention_titled_like_an_existing_individual_in_any_form_is_it(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Whirlpool", "house_business"),
                typing("Whirlpool Corporation", "house_business"),
            ],
        )
        assert result.operations == []

    def test_one_name_with_different_letters_is_one_create_a_part(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Washer (B)", "house_appliance"),
                typing("washers (G)", "house_appliance"),
                typing("Washer (G)", "house_appliance"),
                typing("Washer", "house_appliance"),
                typing("Acme", "house_business"),
                relation("Washer (B)", house["made_by"], "Acme"),
                relation("washers (G)", house["made_by"], "Acme"),
            ],
        )
        creates = [o.draft for o in result.operations if o.draft.kind == "individual"]
        assert [d.fields["title"] for d in creates] == [
            "Washer (B)",
            "Washer (G)",
            "Washer",
            "Acme",
        ]
        relationships = [o.draft for o in result.operations if o.draft.kind == "relationship"]
        assert [d.fields["source_id"] for d in relationships] == ["$i1", "$i2"]

    @pytest.mark.parametrize(
        "short, long",
        [
            ("bracket", "Mounting Bracket"),
            ("dock (E)", "Hand Shower Dock"),
            ("anchors (C)", "Wall Anchor"),
        ],
    )
    def test_a_head_word_mention_folds_into_its_one_multi_word_mention(
        self, repo, house, short, long
    ):
        result = plan(
            repo,
            house,
            [
                typing(long, "house_appliance", [passage(long, 5, 1)]),
                typing(short, "house_appliance", [passage(short, 150, 2)]),
                typing("Acme", "house_business"),
                relation(short, house["made_by"], "Acme"),
            ],
        )
        creates = [o.draft for o in result.operations if o.draft.kind == "individual"]
        assert [d.fields["title"] for d in creates] == [long, "Acme"]
        assert [e["start"] for e in creates[0].evidence] == [5, 150]
        [relationship] = [o for o in result.operations if o.draft.kind == "relationship"]
        assert relationship.draft.fields["source_id"] == "$i1"

    def test_an_ambiguous_head_word_stays_its_own_create(self, repo, house):
        result = plan(
            repo,
            house,
            [
                typing("Wall Anchor", "house_appliance"),
                typing("Drywall Anchor", "house_appliance"),
                typing("anchor", "house_appliance"),
            ],
        )
        assert [o.draft.fields["title"] for o in result.operations] == [
            "Wall Anchor",
            "Drywall Anchor",
            "anchor",
        ]

    def test_a_head_word_of_another_class_stays_its_own_create(self, repo, house):
        result = plan(
            repo,
            house,
            [typing("Mounting Bracket", "house_appliance"), typing("bracket", "house_business")],
        )
        assert [o.draft.fields["title"] for o in result.operations] == [
            "Mounting Bracket",
            "bracket",
        ]

    def test_a_head_word_that_names_an_existing_individual_is_not_folded(
        self, ontology, repo, house
    ):
        dock = ontology.create_individual(house["appliance"], "Dock", dataset_id=house["home"])
        result = plan(
            repo,
            house,
            [typing("Hand Shower Dock", "house_appliance"), typing("dock", "house_appliance")],
        )
        assert [o.draft.fields["title"] for o in result.operations] == ["Hand Shower Dock"]
        assert dock.id not in [a["entity_id"] for a in result.operations[0].draft.alternatives]


class TestLabelNearMatches:
    def test_a_branded_mention_offers_the_existing_unbranded_individual(
        self, ontology, repo, house
    ):
        shower = ontology.create_individual(
            house["appliance"], "Handheld shower", dataset_id=house["home"]
        )
        result = plan(repo, house, [typing("Moen handheld showers", "house_appliance")])
        [create] = result.operations
        assert create.draft.fields["title"] == "Moen handheld showers"
        assert create.draft.alternatives == [
            {"kind": "existing", "entity_id": shower.id, "similarity": None}
        ]

    @pytest.mark.parametrize(
        "label, existing",
        [("Hand Shower", "Shower"), ("Wall Anchor", "Anchor"), ("hand showers", "Showers")],
    )
    def test_a_two_word_mention_is_not_offered_its_head_noun(
        self, ontology, repo, house, label, existing
    ):
        ontology.create_individual(house["appliance"], existing, dataset_id=house["home"])
        result = plan(repo, house, [typing(label, "house_appliance")])
        assert result.operations[0].draft.alternatives == []

    def test_existing_parts_with_different_letters_are_offered_only_their_own(
        self, ontology, repo, house
    ):
        part_b = ontology.create_individual(
            house["appliance"], "Screw (B)", dataset_id=house["home"]
        )
        ontology.create_individual(house["appliance"], "Screw (D)", dataset_id=house["home"])
        result = plan(
            repo,
            house,
            [typing("screws (B)", "house_appliance"), typing("Screw (G)", "house_appliance")],
        )
        assert [o.draft.fields["title"] for o in result.operations] == ["screws (B)", "Screw (G)"]
        assert [o.draft.alternatives for o in result.operations] == [
            [{"kind": "existing", "entity_id": part_b.id, "similarity": None}],
            [],
        ]

    def test_another_form_of_an_existing_name_is_offered(self, repo, house):
        result = plan(repo, house, [typing("Whirlpool Inc.", "house_business")])
        assert result.operations[0].draft.alternatives == [
            {"kind": "existing", "entity_id": house["whirlpool"], "similarity": None}
        ]

    def test_a_business_apart_from_its_product_is_offered_the_existing_business(self, repo, house):
        result = plan(
            repo,
            house,
            [typing("Whirlpool", "house_appliance"), typing("Whirlpool Inc.", "house_business")],
        )
        assert [(o.draft.fields["title"], o.draft.alternatives) for o in result.operations] == [
            ("Whirlpool", []),
            (
                "Whirlpool Inc.",
                [{"kind": "existing", "entity_id": house["whirlpool"], "similarity": None}],
            ),
        ]

    def test_recognition_near_matches_come_first_and_are_not_repeated(self, ontology, repo, house):
        shower = ontology.create_individual(
            house["appliance"], "Handheld shower", dataset_id=house["home"]
        )
        near = [
            {"entity_id": house["fridge"], "label": "Kitchen refrigerator", "similarity": 0.81},
            {"entity_id": shower.id, "label": "Handheld shower", "similarity": 0.8},
        ]
        result = plan(repo, house, [typing("Moen handheld shower", "house_appliance", near=near)])
        assert result.operations[0].draft.alternatives == [
            {"kind": "existing", "entity_id": house["fridge"], "similarity": 0.81},
            {"kind": "existing", "entity_id": shower.id, "similarity": 0.8},
        ]

    def test_individuals_of_other_classes_and_datasets_are_not_offered(self, ontology, repo, house):
        ontology.create_individual(house["business"], "Handheld shower", dataset_id=house["home"])
        ontology.create_individual(house["appliance"], "Handheld shower", dataset_id=house["cabin"])
        result = plan(repo, house, [typing("Moen handheld shower", "house_appliance")])
        assert result.operations[0].draft.alternatives == []
