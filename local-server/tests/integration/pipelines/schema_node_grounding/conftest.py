"""
Fixtures and configuration for schema node grounding quality tests.

Provides mocked reference sources that return predetermined candidates,
enabling tests to run deterministically without network access.
"""

import pytest
from unittest.mock import AsyncMock
from domain.pipelines.schema_node_grounding.scoring import GroundingCandidate


class MockReferenceSource:
    """Mock reference source returning predetermined candidates."""

    def __init__(self, source_name: str, candidates_by_label: dict[str, list[dict]]):
        self.source_name = source_name
        self.candidates_by_label = candidates_by_label

    async def search_async(self, label: str, limit: int = 10):
        """Return mocked candidates."""
        candidates = self.candidates_by_label.get(label.lower(), [])
        return [
            GroundingCandidate(
                uri=c["uri"],
                label=c["label"],
                description=c.get("description"),
                source=self.source_name,
                source_score=c.get("score", 0.8),
            )
            for c in candidates[:limit]
        ]

    def search(self, label: str, limit: int = 10):
        """Synchronous wrapper for mocked candidates."""
        candidates = self.candidates_by_label.get(label.lower(), [])
        return [
            GroundingCandidate(
                uri=c["uri"],
                label=c["label"],
                description=c.get("description"),
                source=self.source_name,
                source_score=c.get("score", 0.8),
            )
            for c in candidates[:limit]
        ]

    def is_available(self):
        """Mock is_available always returns True."""
        return True


# Predefined candidate responses for common test labels
DBPEDIA_CANDIDATES = {
    "person": [
        {
            "uri": "http://dbpedia.org/resource/Person",
            "label": "Person",
            "description": "A human being",
            "score": 0.95,
        },
        {
            "uri": "http://dbpedia.org/resource/Individual",
            "label": "Individual",
            "description": "A single thing",
            "score": 0.70,
        },
        {
            "uri": "http://dbpedia.org/resource/Human",
            "label": "Human",
            "description": "Homo sapiens",
            "score": 0.85,
        },
    ],
    "organization": [
        {
            "uri": "http://dbpedia.org/resource/Organization",
            "label": "Organization",
            "description": "A social entity",
            "score": 0.92,
        },
        {
            "uri": "http://dbpedia.org/resource/Company",
            "label": "Company",
            "description": "A business entity",
            "score": 0.65,
        },
    ],
}

CONCEPTNET_CANDIDATES = {
    "person": [
        {
            "uri": "http://conceptnet.io/c/en/person",
            "label": "person",
            "description": "A human being",
            "score": 0.85,
        },
        {
            "uri": "http://conceptnet.io/c/en/human",
            "label": "human",
            "description": "Homo sapiens",
            "score": 0.75,
        },
    ],
    "organization": [
        {
            "uri": "http://conceptnet.io/c/en/organization",
            "label": "organization",
            "description": "A social group",
            "score": 0.80,
        },
    ],
}

WIKIDATA_CANDIDATES = {
    "person": [
        {
            "uri": "http://www.wikidata.org/entity/Q5",
            "label": "human",
            "description": "Homo sapiens",
            "score": 0.90,
        },
        {
            "uri": "http://www.wikidata.org/entity/Q43229",
            "label": "organism",
            "description": "Living thing",
            "score": 0.60,
        },
    ],
    "organization": [
        {
            "uri": "http://www.wikidata.org/entity/Q43229",
            "label": "organization",
            "description": "Organized group",
            "score": 0.88,
        },
    ],
}

SCHEMA_ORG_CANDIDATES = {
    "person": [
        {
            "uri": "https://schema.org/Person",
            "label": "Person",
            "description": "A person (alive, dead, undead, or fictional).",
            "score": 0.95,
        },
    ],
    "organization": [
        {
            "uri": "https://schema.org/Organization",
            "label": "Organization",
            "description": "An organization such as a school, NGO, corporation",
            "score": 0.93,
        },
    ],
}


@pytest.fixture
def mock_dbpedia_source():
    """Fixture providing a mocked DBpedia source."""
    return MockReferenceSource("DBpedia", DBPEDIA_CANDIDATES)


@pytest.fixture
def mock_conceptnet_source():
    """Fixture providing a mocked ConceptNet source."""
    return MockReferenceSource("ConceptNet", CONCEPTNET_CANDIDATES)


@pytest.fixture
def mock_wikidata_source():
    """Fixture providing a mocked Wikidata source."""
    return MockReferenceSource("Wikidata", WIKIDATA_CANDIDATES)


@pytest.fixture
def mock_schema_org_source():
    """Fixture providing a mocked schema.org source."""
    return MockReferenceSource("schema.org", SCHEMA_ORG_CANDIDATES)


@pytest.fixture
def mock_grounding_adapter(
    mock_dbpedia_source, mock_conceptnet_source, mock_wikidata_source, mock_schema_org_source
):
    """Fixture providing a GroundingAdapter with mocked sources."""
    from adapters.reference.grounding.adapter import GroundingAdapter

    return GroundingAdapter(
        dbpedia=mock_dbpedia_source,
        conceptnet=mock_conceptnet_source,
        wikidata=mock_wikidata_source,
        schema_org=mock_schema_org_source,
    )
