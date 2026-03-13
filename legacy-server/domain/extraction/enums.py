"""
Domain value enums for the extraction bounded context.

Enums represent domain concepts in the extraction bounded context.
They are immutable and framework-free, depending only on Python stdlib.
"""

from enum import Enum


class EntityType(str, Enum):
    """
    Enumeration of extracted entity types.

    Attributes:
        PERSON: A person entity
        ORGANIZATION: An organization entity
        LOCATION: A geographic location entity
        CONCEPT: A conceptual/abstract entity
        UNKNOWN: Unknown or other entity type
    """

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    CONCEPT = "concept"
    UNKNOWN = "unknown"


class LayerName(str, Enum):
    """
    Enumeration of extraction layer names.

    Each layer represents a different extraction technique or processing step.

    Attributes:
        KG: Knowledge Graph layer (entity and relationship extraction)
        NLP: NLP layer (spaCy-based processing)
        LLM: LLM layer (language model-based extraction)
        WEB: Web layer (web search and external source integration)
    """

    KG = "kg"
    NLP = "nlp"
    LLM = "llm"
    WEB = "web"
