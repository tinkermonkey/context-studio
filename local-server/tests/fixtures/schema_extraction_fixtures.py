"""
Fixtures for Schema Extraction pipeline testing.

Includes both hand-authored fixtures for controlled testing and corpus-derived fixtures
that validate against real-world terminology with multi-sense disambiguation.
"""

import json
from pathlib import Path


def _load_corpus_fixture(fixture_name: str) -> str:
    """Load a corpus-derived fixture from the fixtures directory."""
    fixture_path = (
        Path(__file__).parent.parent
        / "integration"
        / "fixtures"
        / "pipelines"
        / "schema_extraction"
        / f"{fixture_name}.txt"
    )
    with open(fixture_path, "r") as f:
        return f.read()


def get_microservices_text() -> str:
    """
    Fixture: Microservices architecture glossary text.

    Contains multi-sense terms (e.g., "service" as both a standalone concept
    and as part of "microservice"), technical relationships, and property definitions.
    """
    return """
A Microservice is a small, independent service that handles a specific business capability.
Microservices work together in a distributed system to build larger applications.

Each Microservice should have a single responsibility and be deployed independently.
Services communicate with each other through well-defined APIs.

A Message Queue is a mechanism for inter-service communication in asynchronous patterns.
Message Queues decouple Services from each other, improving system resilience.

An API Gateway is a server that acts as an intermediary between clients and Services.
The API Gateway routes requests to the appropriate Microservice for processing.

Service Discovery allows Services to find and communicate with other Services dynamically.
Service Registry maintains a catalog of available Services and their locations.
"""


def get_database_text() -> str:
    """
    Fixture: Database and persistence concepts.

    Contains relationships between entities (e.g., Database contains Table).
    """
    return """
A Database is a structured collection of data organized in Tables.
Tables store data in rows and columns, with each column having a specific data type.

A Primary Key is a column or set of columns that uniquely identifies each row in a Table.
A Foreign Key is a column that references a Primary Key in another Table.

An Index is a data structure that improves the speed of data retrieval from a Table.
A Query is a request to retrieve or modify data from a Database.

A Transaction is a sequence of operations on a Database that is atomic and consistent.
Transactions ensure that a Database moves from one consistent state to another.
"""


def get_semantic_web_text() -> str:
    """
    Fixture: Semantic Web and RDF concepts.

    Contains technical terms and relationships relevant to ontology extraction.
    """
    return """
A Semantic Web enables machines to understand the meaning of data.
The Semantic Web uses ontologies to represent knowledge formally.

An Ontology is a formal representation of knowledge within a domain.
An Ontology defines classes, properties, and relationships between concepts.

RDF (Resource Description Framework) is a standard for representing data as triples.
An RDF Triple consists of a subject, predicate, and object.

A Resource is an entity or concept in the Semantic Web.
A Property describes a characteristic or relationship of a Resource.

Semantic Metadata enriches data with explicit meaning and structure.
Semantic Annotation connects data elements to formal ontologies.
"""


def get_fixtures() -> dict[str, str]:
    """
    Return all test fixtures as a dictionary.

    Includes hand-authored fixtures and corpus-derived fixtures.

    Returns:
        Dict mapping fixture name to text content
    """
    fixtures = {
        "microservices": get_microservices_text(),
        "database": get_database_text(),
        "semantic_web": get_semantic_web_text(),
    }

    # Add corpus-derived fixtures
    try:
        fixtures["consensus_distributed"] = _load_corpus_fixture(
            "fixture_consensus_distributed"
        )
        fixtures["microservices_api"] = _load_corpus_fixture(
            "fixture_microservices_api"
        )
        fixtures["service_multisense"] = _load_corpus_fixture(
            "fixture_service_multisense"
        )
    except FileNotFoundError:
        # If corpus fixtures don't exist yet, continue with just hand-authored ones
        pass

    return fixtures
