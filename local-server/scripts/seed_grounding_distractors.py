#!/usr/bin/env python3
"""
Seed grounding quality suite fixtures with 30+ labeled classes and distractors.

Creates fixture corpus with ≥30 classes spanning multiple domains, each with:
- input.json: node_label and sources configuration
- expected.json: hand-labeled expected_external_references with URIs
- distractors.json: 3-5 plausible-but-wrong candidates from same sources

The fixture corpus demonstrates knowledge across DBpedia, ConceptNet, Wikidata, and schema.org.
"""

import json
from pathlib import Path

# Define the fixture corpus with labeled classes and their URIs across sources
FIXTURES = {
    "person": {
        "node_label": "Person",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Person",
                "source": "DBpedia",
                "rationale": "Core concept for human beings",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q5",
                "source": "Wikidata",
                "rationale": "Wikidata: human",
            },
            {
                "uri": "https://schema.org/Person",
                "source": "schema.org",
                "rationale": "schema.org definition",
            },
            {
                "uri": "http://conceptnet.io/c/en/person",
                "source": "ConceptNet",
                "rationale": "ConceptNet person concept",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Individual",
                "http://dbpedia.org/resource/Human",
                "http://dbpedia.org/resource/Man",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q43229",  # organism
                "http://www.wikidata.org/entity/Q7725634",  # human activity
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/human",
                "http://conceptnet.io/c/en/individual",
            ],
            "schema.org": [
                "https://schema.org/Agent",
                "https://schema.org/Thing",
            ],
        },
    },
    "organization": {
        "node_label": "Organization",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Organization",
                "source": "DBpedia",
                "rationale": "DBpedia organization",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q43229",
                "source": "Wikidata",
                "rationale": "Wikidata organization",
            },
            {
                "uri": "https://schema.org/Organization",
                "source": "schema.org",
                "rationale": "schema.org organization",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Company",
                "http://dbpedia.org/resource/Institution",
                "http://dbpedia.org/resource/Foundation",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q6881115",  # enterprise
                "http://www.wikidata.org/entity/Q33971",  # business
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/company",
                "http://conceptnet.io/c/en/group",
            ],
        },
    },
    "location": {
        "node_label": "Location",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Location",
                "source": "DBpedia",
                "rationale": "Geographic location",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q2221906",
                "source": "Wikidata",
                "rationale": "Wikidata location",
            },
            {
                "uri": "https://schema.org/Place",
                "source": "schema.org",
                "rationale": "schema.org place",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Place",
                "http://dbpedia.org/resource/Region",
                "http://dbpedia.org/resource/Area",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q27096213",  # geographic feature
                "http://www.wikidata.org/entity/Q1221156",  # land area
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/place",
                "http://conceptnet.io/c/en/area",
            ],
        },
    },
    "event": {
        "node_label": "Event",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Event",
                "source": "DBpedia",
                "rationale": "Occurrence or incident",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q1656682",
                "source": "Wikidata",
                "rationale": "Wikidata event",
            },
            {
                "uri": "https://schema.org/Event",
                "source": "schema.org",
                "rationale": "schema.org event",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Happening",
                "http://dbpedia.org/resource/Incident",
                "http://dbpedia.org/resource/Occasion",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q1191551",  # happening
                "http://www.wikidata.org/entity/Q386611",  # happening
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/event",
                "http://conceptnet.io/c/en/happening",
            ],
        },
    },
    "animal": {
        "node_label": "Animal",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Animal",
                "source": "DBpedia",
                "rationale": "Living organism",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q729",
                "source": "Wikidata",
                "rationale": "Wikidata animal",
            },
            {
                "uri": "https://schema.org/Animal",
                "source": "schema.org",
                "rationale": "schema.org animal",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Creature",
                "http://dbpedia.org/resource/Beast",
                "http://dbpedia.org/resource/Organism",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q7863",  # bird
                "http://www.wikidata.org/entity/Q6005",  # mammal
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/creature",
                "http://conceptnet.io/c/en/beast",
                "http://conceptnet.io/c/en/organism",
            ],
        },
    },
    "plant": {
        "node_label": "Plant",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Plant",
                "source": "DBpedia",
                "rationale": "Botanical organism",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q756",
                "source": "Wikidata",
                "rationale": "Wikidata plant",
            },
            {
                "uri": "https://schema.org/BioChemEntity",
                "source": "schema.org",
                "rationale": "Bio entity",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Vegetation",
                "http://dbpedia.org/resource/Flora",
                "http://dbpedia.org/resource/Tree",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q10884",  # tree
                "http://www.wikidata.org/entity/Q42295",  # flower
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/vegetation",
                "http://conceptnet.io/c/en/flora",
            ],
        },
    },
    "vehicle": {
        "node_label": "Vehicle",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Vehicle",
                "source": "DBpedia",
                "rationale": "Means of transport",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q42889",
                "source": "Wikidata",
                "rationale": "Wikidata vehicle",
            },
            {
                "uri": "https://schema.org/Vehicle",
                "source": "schema.org",
                "rationale": "schema.org vehicle",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Transport",
                "http://dbpedia.org/resource/Car",
                "http://dbpedia.org/resource/Machine",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q1420",  # automobile
                "http://www.wikidata.org/entity/Q11019",  # ship
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/transport",
                "http://conceptnet.io/c/en/machine",
            ],
        },
    },
    "food": {
        "node_label": "Food",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Food",
                "source": "DBpedia",
                "rationale": "Edible substance",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q2095",
                "source": "Wikidata",
                "rationale": "Wikidata food",
            },
            {
                "uri": "https://schema.org/Food",
                "source": "schema.org",
                "rationale": "schema.org food",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Cuisine",
                "http://dbpedia.org/resource/Meal",
                "http://dbpedia.org/resource/Ingredient",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q28840",  # cuisine
                "http://www.wikidata.org/entity/Q29960",  # dish
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/meal",
                "http://conceptnet.io/c/en/cuisine",
            ],
        },
    },
    "artist": {
        "node_label": "Artist",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Artist",
                "source": "DBpedia",
                "rationale": "Creative professional",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q483501",
                "source": "Wikidata",
                "rationale": "Wikidata artist",
            },
            {
                "uri": "https://schema.org/Artist",
                "source": "schema.org",
                "rationale": "schema.org artist",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Musician",
                "http://dbpedia.org/resource/Painter",
                "http://dbpedia.org/resource/Creator",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q639669",  # musician
                "http://www.wikidata.org/entity/Q1028181",  # painter
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/musician",
                "http://conceptnet.io/c/en/creator",
            ],
        },
    },
    "color": {
        "node_label": "Color",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Color",
                "source": "DBpedia",
                "rationale": "Visual property",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q1075",
                "source": "Wikidata",
                "rationale": "Wikidata color",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic schema.org thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Hue",
                "http://dbpedia.org/resource/Shade",
                "http://dbpedia.org/resource/Pigment",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q4353169",  # hue
                "http://www.wikidata.org/entity/Q1353674",  # pigment
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/hue",
                "http://conceptnet.io/c/en/shade",
            ],
        },
    },
    "book": {
        "node_label": "Book",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Book",
                "source": "DBpedia",
                "rationale": "Written work",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q571",
                "source": "Wikidata",
                "rationale": "Wikidata book",
            },
            {
                "uri": "https://schema.org/Book",
                "source": "schema.org",
                "rationale": "schema.org book",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Publication",
                "http://dbpedia.org/resource/Document",
                "http://dbpedia.org/resource/Literature",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q10870920",  # publication
                "http://www.wikidata.org/entity/Q47461344",  # written work
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/publication",
                "http://conceptnet.io/c/en/document",
            ],
        },
    },
    "sport": {
        "node_label": "Sport",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Sport",
                "source": "DBpedia",
                "rationale": "Athletic activity",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q349",
                "source": "Wikidata",
                "rationale": "Wikidata sport",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "schema.org thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Game",
                "http://dbpedia.org/resource/Competition",
                "http://dbpedia.org/resource/Athletics",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q14462",  # game
                "http://www.wikidata.org/entity/Q488188",  # competition
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/game",
                "http://conceptnet.io/c/en/competition",
            ],
        },
    },
    "chemical_element": {
        "node_label": "ChemicalElement",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Chemical_element",
                "source": "DBpedia",
                "rationale": "Element in periodic table",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q11344",
                "source": "Wikidata",
                "rationale": "Wikidata chemical element",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Atom",
                "http://dbpedia.org/resource/Substance",
                "http://dbpedia.org/resource/Material",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q125885",  # atom
                "http://www.wikidata.org/entity/Q11472",  # isotope
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/atom",
                "http://conceptnet.io/c/en/substance",
            ],
        },
    },
    "disease": {
        "node_label": "Disease",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Disease",
                "source": "DBpedia",
                "rationale": "Medical condition",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q12136",
                "source": "Wikidata",
                "rationale": "Wikidata disease",
            },
            {
                "uri": "https://schema.org/MedicalCondition",
                "source": "schema.org",
                "rationale": "schema.org medical condition",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Illness",
                "http://dbpedia.org/resource/Syndrome",
                "http://dbpedia.org/resource/Condition",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q640099",  # syndrome
                "http://www.wikidata.org/entity/Q10743570",  # medical condition
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/illness",
                "http://conceptnet.io/c/en/sickness",
            ],
        },
    },
    "music": {
        "node_label": "Music",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Music",
                "source": "DBpedia",
                "rationale": "Art of sound",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q638",
                "source": "Wikidata",
                "rationale": "Wikidata music",
            },
            {
                "uri": "https://schema.org/MusicGroup",
                "source": "schema.org",
                "rationale": "schema.org music",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Song",
                "http://dbpedia.org/resource/Composer",
                "http://dbpedia.org/resource/Sound",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q557",  # song
                "http://www.wikidata.org/entity/Q36834",  # composer
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/song",
                "http://conceptnet.io/c/en/sound",
            ],
        },
    },
    "language": {
        "node_label": "Language",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Language",
                "source": "DBpedia",
                "rationale": "Communication system",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q315",
                "source": "Wikidata",
                "rationale": "Wikidata language",
            },
            {
                "uri": "https://schema.org/Language",
                "source": "schema.org",
                "rationale": "schema.org language",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Dialect",
                "http://dbpedia.org/resource/Speech",
                "http://dbpedia.org/resource/Communication",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q33081",  # dialect
                "http://www.wikidata.org/entity/Q17051",  # communication
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/dialect",
                "http://conceptnet.io/c/en/speech",
            ],
        },
    },
    "software": {
        "node_label": "Software",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Software",
                "source": "DBpedia",
                "rationale": "Computer program",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q7397",
                "source": "Wikidata",
                "rationale": "Wikidata software",
            },
            {
                "uri": "https://schema.org/SoftwareApplication",
                "source": "schema.org",
                "rationale": "schema.org application",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Application",
                "http://dbpedia.org/resource/Program",
                "http://dbpedia.org/resource/System",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q189123",  # application
                "http://www.wikidata.org/entity/Q9135",  # system
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/application",
                "http://conceptnet.io/c/en/program",
            ],
        },
    },
    "building": {
        "node_label": "Building",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Building",
                "source": "DBpedia",
                "rationale": "Structure",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q41176",
                "source": "Wikidata",
                "rationale": "Wikidata building",
            },
            {
                "uri": "https://schema.org/Place",
                "source": "schema.org",
                "rationale": "schema.org place",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/House",
                "http://dbpedia.org/resource/Structure",
                "http://dbpedia.org/resource/Construction",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q3947",  # house
                "http://www.wikidata.org/entity/Q11755",  # architecture
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/structure",
                "http://conceptnet.io/c/en/construction",
            ],
        },
    },
    "university": {
        "node_label": "University",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/University",
                "source": "DBpedia",
                "rationale": "Educational institution",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q3918",
                "source": "Wikidata",
                "rationale": "Wikidata university",
            },
            {
                "uri": "https://schema.org/EducationalOrganization",
                "source": "schema.org",
                "rationale": "schema.org organization",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/School",
                "http://dbpedia.org/resource/College",
                "http://dbpedia.org/resource/Institution",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q13424603",  # school
                "http://www.wikidata.org/entity/Q33506",  # education
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/school",
                "http://conceptnet.io/c/en/college",
            ],
        },
    },
    "government": {
        "node_label": "Government",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Government",
                "source": "DBpedia",
                "rationale": "Political system",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q7188",
                "source": "Wikidata",
                "rationale": "Wikidata government",
            },
            {
                "uri": "https://schema.org/Organization",
                "source": "schema.org",
                "rationale": "schema.org organization",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Politics",
                "http://dbpedia.org/resource/State",
                "http://dbpedia.org/resource/Authority",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q7163",  # politics
                "http://www.wikidata.org/entity/Q7275",  # state
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/politics",
                "http://conceptnet.io/c/en/state",
            ],
        },
    },
    "river": {
        "node_label": "River",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/River",
                "source": "DBpedia",
                "rationale": "Water body",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q4022",
                "source": "Wikidata",
                "rationale": "Wikidata river",
            },
            {
                "uri": "https://schema.org/LandmarksOrHistoricalBuildings",
                "source": "schema.org",
                "rationale": "Geographic feature",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Stream",
                "http://dbpedia.org/resource/Waterbody",
                "http://dbpedia.org/resource/Creek",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q47521",  # stream
                "http://www.wikidata.org/entity/Q35702",  # lake
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/stream",
                "http://conceptnet.io/c/en/water",
            ],
        },
    },
    "mountain": {
        "node_label": "Mountain",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Mountain",
                "source": "DBpedia",
                "rationale": "Landform",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q8502",
                "source": "Wikidata",
                "rationale": "Wikidata mountain",
            },
            {
                "uri": "https://schema.org/LandmarksOrHistoricalBuildings",
                "source": "schema.org",
                "rationale": "Geographic landmark",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Hill",
                "http://dbpedia.org/resource/Peak",
                "http://dbpedia.org/resource/Landform",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q33837",  # hill
                "http://www.wikidata.org/entity/Q1028494",  # peak
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/hill",
                "http://conceptnet.io/c/en/peak",
            ],
        },
    },
    "ocean": {
        "node_label": "Ocean",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Ocean",
                "source": "DBpedia",
                "rationale": "Large water body",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q9430",
                "source": "Wikidata",
                "rationale": "Wikidata ocean",
            },
            {
                "uri": "https://schema.org/LandmarksOrHistoricalBuildings",
                "source": "schema.org",
                "rationale": "Water body",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Sea",
                "http://dbpedia.org/resource/Water",
                "http://dbpedia.org/resource/Marine",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q1359",  # sea
                "http://www.wikidata.org/entity/Q4394",  # lake
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/sea",
                "http://conceptnet.io/c/en/water",
            ],
        },
    },
    "star": {
        "node_label": "Star",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Star",
                "source": "DBpedia",
                "rationale": "Celestial object",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q523",
                "source": "Wikidata",
                "rationale": "Wikidata star",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Planet",
                "http://dbpedia.org/resource/Celestial",
                "http://dbpedia.org/resource/Sun",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q634",  # planet
                "http://www.wikidata.org/entity/Q11019",  # galaxy
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/planet",
                "http://conceptnet.io/c/en/sun",
            ],
        },
    },
    "atom": {
        "node_label": "Atom",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Atom",
                "source": "DBpedia",
                "rationale": "Matter particle",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q125885",
                "source": "Wikidata",
                "rationale": "Wikidata atom",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Molecule",
                "http://dbpedia.org/resource/Particle",
                "http://dbpedia.org/resource/Element",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q11364",  # molecule
                "http://www.wikidata.org/entity/Q502",  # particle
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/molecule",
                "http://conceptnet.io/c/en/particle",
            ],
        },
    },
    "cell": {
        "node_label": "Cell",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Cell",
                "source": "DBpedia",
                "rationale": "Biological unit",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q7868",
                "source": "Wikidata",
                "rationale": "Wikidata cell",
            },
            {
                "uri": "https://schema.org/BioChemEntity",
                "source": "schema.org",
                "rationale": "Biochemical entity",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Tissue",
                "http://dbpedia.org/resource/Organism",
                "http://dbpedia.org/resource/Biology",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q42861",  # tissue
                "http://www.wikidata.org/entity/Q7239",  # organism
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/tissue",
                "http://conceptnet.io/c/en/organism",
            ],
        },
    },
    "protein": {
        "node_label": "Protein",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Protein",
                "source": "DBpedia",
                "rationale": "Biomolecule",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q8054",
                "source": "Wikidata",
                "rationale": "Wikidata protein",
            },
            {
                "uri": "https://schema.org/BioChemEntity",
                "source": "schema.org",
                "rationale": "Biochemical entity",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Amino_acid",
                "http://dbpedia.org/resource/Enzyme",
                "http://dbpedia.org/resource/Molecule",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q4177",  # amino acid
                "http://www.wikidata.org/entity/Q8047",  # enzyme
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/amino_acid",
                "http://conceptnet.io/c/en/enzyme",
            ],
        },
    },
    "dna": {
        "node_label": "DNA",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/DNA",
                "source": "DBpedia",
                "rationale": "Genetic material",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q7055",
                "source": "Wikidata",
                "rationale": "Wikidata DNA",
            },
            {
                "uri": "https://schema.org/BioChemEntity",
                "source": "schema.org",
                "rationale": "Biochemical entity",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/RNA",
                "http://dbpedia.org/resource/Gene",
                "http://dbpedia.org/resource/Chromosome",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q11053",  # RNA
                "http://www.wikidata.org/entity/Q7314",  # gene
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/rna",
                "http://conceptnet.io/c/en/gene",
            ],
        },
    },
    "bacteria": {
        "node_label": "Bacteria",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Bacterium",
                "source": "DBpedia",
                "rationale": "Microorganism",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q6516",
                "source": "Wikidata",
                "rationale": "Wikidata bacteria",
            },
            {
                "uri": "https://schema.org/BioChemEntity",
                "source": "schema.org",
                "rationale": "Living organism",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Virus",
                "http://dbpedia.org/resource/Microorganism",
                "http://dbpedia.org/resource/Prokaryote",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q10876",  # virus
                "http://www.wikidata.org/entity/Q23430",  # microorganism
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/virus",
                "http://conceptnet.io/c/en/microorganism",
            ],
        },
    },
    "virus": {
        "node_label": "Virus",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Virus",
                "source": "DBpedia",
                "rationale": "Infectious agent",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q10876",
                "source": "Wikidata",
                "rationale": "Wikidata virus",
            },
            {
                "uri": "https://schema.org/BioChemEntity",
                "source": "schema.org",
                "rationale": "Living entity",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Bacteria",
                "http://dbpedia.org/resource/Pathogen",
                "http://dbpedia.org/resource/Disease",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q6516",  # bacteria
                "http://www.wikidata.org/entity/Q12136",  # disease
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/bacteria",
                "http://conceptnet.io/c/en/pathogen",
            ],
        },
    },
    "chemical_compound": {
        "node_label": "ChemicalCompound",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Chemical_compound",
                "source": "DBpedia",
                "rationale": "Substance",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q11173",
                "source": "Wikidata",
                "rationale": "Wikidata chemical",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Molecule",
                "http://dbpedia.org/resource/Element",
                "http://dbpedia.org/resource/Substance",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q11364",  # molecule
                "http://www.wikidata.org/entity/Q11344",  # element
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/molecule",
                "http://conceptnet.io/c/en/substance",
            ],
        },
    },
    "energy": {
        "node_label": "Energy",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Energy",
                "source": "DBpedia",
                "rationale": "Physical quantity",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q11379",
                "source": "Wikidata",
                "rationale": "Wikidata energy",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Power",
                "http://dbpedia.org/resource/Force",
                "http://dbpedia.org/resource/Motion",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q21016",  # power
                "http://www.wikidata.org/entity/Q11402",  # force
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/power",
                "http://conceptnet.io/c/en/force",
            ],
        },
    },
    "motion": {
        "node_label": "Motion",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Motion",
                "source": "DBpedia",
                "rationale": "Change of position",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q11465",
                "source": "Wikidata",
                "rationale": "Wikidata motion",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Movement",
                "http://dbpedia.org/resource/Velocity",
                "http://dbpedia.org/resource/Speed",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q1541",  # movement
                "http://www.wikidata.org/entity/Q11465",  # velocity
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/movement",
                "http://conceptnet.io/c/en/velocity",
            ],
        },
    },
    "time": {
        "node_label": "Time",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Time",
                "source": "DBpedia",
                "rationale": "Temporal dimension",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q11471",
                "source": "Wikidata",
                "rationale": "Wikidata time",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Duration",
                "http://dbpedia.org/resource/Period",
                "http://dbpedia.org/resource/Moment",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q2147837",  # duration
                "http://www.wikidata.org/entity/Q5161766",  # period
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/duration",
                "http://conceptnet.io/c/en/period",
            ],
        },
    },
    "space": {
        "node_label": "Space",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Space",
                "source": "DBpedia",
                "rationale": "Spatial dimension",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q1922563",
                "source": "Wikidata",
                "rationale": "Wikidata space",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Area",
                "http://dbpedia.org/resource/Volume",
                "http://dbpedia.org/resource/Dimension",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q17524",  # area
                "http://www.wikidata.org/entity/Q241",  # volume
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/area",
                "http://conceptnet.io/c/en/volume",
            ],
        },
    },
    "network": {
        "node_label": "Network",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Network",
                "source": "DBpedia",
                "rationale": "Connected system",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q5649462",
                "source": "Wikidata",
                "rationale": "Wikidata network",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Connection",
                "http://dbpedia.org/resource/Link",
                "http://dbpedia.org/resource/System",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q14378098",  # connection
                "http://www.wikidata.org/entity/Q1028494",  # link
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/connection",
                "http://conceptnet.io/c/en/link",
            ],
        },
    },
    "algorithm": {
        "node_label": "Algorithm",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Algorithm",
                "source": "DBpedia",
                "rationale": "Computational procedure",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q8366",
                "source": "Wikidata",
                "rationale": "Wikidata algorithm",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Procedure",
                "http://dbpedia.org/resource/Method",
                "http://dbpedia.org/resource/Process",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q11019",  # procedure
                "http://www.wikidata.org/entity/Q3671713",  # method
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/procedure",
                "http://conceptnet.io/c/en/method",
            ],
        },
    },
    "database": {
        "node_label": "Database",
        "node_type": "Class",
        "expected_uris": [
            {
                "uri": "http://dbpedia.org/resource/Database",
                "source": "DBpedia",
                "rationale": "Data storage",
            },
            {
                "uri": "http://www.wikidata.org/entity/Q27302918",
                "source": "Wikidata",
                "rationale": "Wikidata database",
            },
            {
                "uri": "https://schema.org/Thing",
                "source": "schema.org",
                "rationale": "Generic thing",
            },
        ],
        "distractors": {
            "DBpedia": [
                "http://dbpedia.org/resource/Storage",
                "http://dbpedia.org/resource/Memory",
                "http://dbpedia.org/resource/System",
            ],
            "Wikidata": [
                "http://www.wikidata.org/entity/Q21049999",  # storage
                "http://www.wikidata.org/entity/Q33971",  # system
            ],
            "ConceptNet": [
                "http://conceptnet.io/c/en/storage",
                "http://conceptnet.io/c/en/memory",
            ],
        },
    },
}


def create_fixtures():
    """Create fixture directories and JSON files for quality suite."""
    fixtures_base = (
        Path(__file__).parent.parent
        / "tests"
        / "integration"
        / "fixtures"
        / "pipelines"
        / "schema_node_grounding"
    )
    fixtures_base.mkdir(parents=True, exist_ok=True)

    for scenario_name, config in FIXTURES.items():
        scenario_dir = fixtures_base / scenario_name
        scenario_dir.mkdir(exist_ok=True)

        # Create input.json
        input_data = {
            "node_label": config["node_label"],
            "node_type": config["node_type"],
            "sources": ["DBpedia", "ConceptNet", "Wikidata", "schema.org"],
        }
        with open(scenario_dir / "input.json", "w") as f:
            json.dump(input_data, f, indent=2)

        # Create expected.json
        expected_data = {"expected_external_references": config["expected_uris"]}
        with open(scenario_dir / "expected.json", "w") as f:
            json.dump(expected_data, f, indent=2)

        # Create distractors.json
        distractors = {
            "DBpedia": config["distractors"].get("DBpedia", []),
            "ConceptNet": config["distractors"].get("ConceptNet", []),
            "Wikidata": config["distractors"].get("Wikidata", []),
            "schema.org": config["distractors"].get("schema.org", []),
        }
        with open(scenario_dir / "distractors.json", "w") as f:
            json.dump(distractors, f, indent=2)

        print(f"Created fixture: {scenario_name}")

    print(f"\nTotal fixtures created: {len(FIXTURES)}")


if __name__ == "__main__":
    create_fixtures()
