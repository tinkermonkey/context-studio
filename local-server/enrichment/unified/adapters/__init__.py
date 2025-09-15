"""Unified reference source adapters"""

from .base import ReferenceAdapter
from .conceptnet import ConceptNetAdapter
from .dbpedia import DBpediaAdapter
from .wikidata import WikidataAdapter
from .schema_org import SchemaOrgAdapter
from .wordnet import WordNetAdapter

from ..models import ReferenceSource

def get_adapter(source_type: ReferenceSource) -> ReferenceAdapter:
    """Factory function to get appropriate adapter for source type"""
    adapter_map = {
        ReferenceSource.CONCEPTNET: ConceptNetAdapter,
        ReferenceSource.DBPEDIA: DBpediaAdapter,
        ReferenceSource.WIKIDATA: WikidataAdapter,
        ReferenceSource.SCHEMA_ORG: SchemaOrgAdapter,
        ReferenceSource.WORDNET: WordNetAdapter,
    }

    if source_type not in adapter_map:
        raise ValueError(f"No adapter available for source type: {source_type}")

    return adapter_map[source_type](source_type)

__all__ = [
    "ReferenceAdapter",
    "ConceptNetAdapter",
    "DBpediaAdapter",
    "WikidataAdapter",
    "SchemaOrgAdapter",
    "WordNetAdapter",
    "get_adapter",
]