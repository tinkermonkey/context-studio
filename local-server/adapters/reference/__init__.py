"""
Reference data service adapters for Context Studio.

This package contains adapters that implement the ReferenceSource port
defined in domain/extraction/ports.py.

The ReferenceSource port defines:
- lookup(concept: str, ontology: str) -> ReferenceResult: Look up concept in external ontology
- search(query: str, ontology: str) -> Sequence[ReferenceResult]: Search external ontology

Supported reference sources:
- ConceptNet: Common-sense knowledge graph
- Wikidata: Collaborative knowledge base
- DBpedia: Linked data from Wikipedia
- UMLS: Unified Medical Language System (biomedical domain)
- WordNet: Lexical database for English

Per rearchitecture/architecture_design.md §5.6, the current reference_api/
and reference_db/ directories contain the implementations. This adapter layer
wraps those implementations to conform to the domain port contract.

ReferenceResult includes:
- source: str (conceptnet / wikidata / dbpedia / umls / wordnet)
- uri: str (external URI or IRI)
- label: str (preferred label)
- definition: str (optional description)
- aliases: Sequence[str] (alternative names)
- relations: Sequence[ReferenceRelation] (links to related concepts)
- confidence: float (0.0-1.0, relevance score)
- metadata: dict (source-specific additional data)
"""
