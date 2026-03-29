"""
Reference source enrichment layer (Layer 3).

Enriches extracted entities by resolving them against external reference
knowledge sources.
"""
import logging
from types import MappingProxyType

from domain.extraction.entities import ExtractedEntity
from domain.extraction.ports import ReferenceSource
from domain.extraction.value_objects import LayerInput, LayerOutput

_logger = logging.getLogger(__name__)


def execute(input: LayerInput, sources: list[ReferenceSource]) -> LayerOutput:
    """
    Enrich entities using external reference sources (Layer 3).

    Searches reference sources (ConceptNet, DBpedia, Wikidata, schema.org) for
    each entity found in prior layers to add URIs, descriptions, and metadata
    from external knowledge bases.

    Important: This layer creates enriched copies of entities from prior layers.
    Each enriched entity has:
    - The SAME ID as the original (for dedup to recognize them as the same entity)
    - Added URI and description from reference sources
    - Metadata tracking which source provided enrichment
    - All original properties plus enrichment properties

    The deduplication layer (in ExtractionService._deduplicate) is responsible
    for merging these enriched copies back with the originals, ensuring no
    enrichment data is lost.

    Args:
        input: LayerInput containing text and prior extraction context
        sources: List of ReferenceSource ports to query

    Returns:
        LayerOutput containing enriched entity copies (same IDs as prior entities)
    """
    entities: list[ExtractedEntity] = []

    if not input.text or not input.text.strip():
        return LayerOutput(entities=tuple(entities), metadata=MappingProxyType({"reason": "empty_text"}))

    if not input.existing_entities:
        return LayerOutput(
            entities=tuple(entities),
            metadata=MappingProxyType({"reason": "no_prior_entities", "enriched_count": 0}),
        )

    # Filter to available sources
    available_sources = [s for s in sources if s.is_available()]

    if not available_sources:
        return LayerOutput(
            entities=tuple(),
            metadata=MappingProxyType({
                "reason": "no_available_reference_sources",
                "prior_entities": len(input.existing_entities),
                "enriched_count": 0,
            }),
        )

    # For each entity from prior layers, attempt to enrich with reference data
    enrichment_count = 0
    enriched_ids = set()

    for prior_entity in input.existing_entities:
        if prior_entity.id in enriched_ids:
            continue

        for source in available_sources:
            try:
                results = source.search(prior_entity.label, limit=5)
            except Exception as e:
                _logger.warning(
                    f"Source {source.source_name} failed during search for '{prior_entity.label}': {e}"
                )
                continue

            if results:
                # Use the top result to create an enriched entity
                top_result = results[0]

                # Create enriched entity with SAME ID as the prior entity
                # This ensures deduplication can recognize them as the same concept
                enriched_entity = ExtractedEntity(
                    id=prior_entity.id,
                    label=prior_entity.label,
                    entity_type=prior_entity.entity_type,
                    source_layer=3,
                    confidence=prior_entity.confidence,
                    uri=top_result.uri or prior_entity.uri,
                    description=top_result.description or prior_entity.description,
                    matched_class_id=prior_entity.matched_class_id,
                    properties={
                        **(prior_entity.properties or {}),
                        "reference_source": source.source_name,
                        "reference_label": top_result.label,
                    },
                )
                entities.append(enriched_entity)
                enriched_ids.add(prior_entity.id)
                enrichment_count += 1
                break  # Move to next entity after first source match

    return LayerOutput(
        entities=tuple(entities),
        metadata=MappingProxyType({
            "prior_entities": len(input.existing_entities),
            "enriched_count": enrichment_count,
            "sources_checked": len(available_sources),
            "sources_available": [s.source_name for s in available_sources],
        }),
    )
