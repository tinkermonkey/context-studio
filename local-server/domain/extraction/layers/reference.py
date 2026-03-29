"""
Reference source enrichment layer (Layer 3).

Enriches extracted entities by resolving them against external reference
knowledge sources.
"""
from domain.extraction.entities import ExtractedEntity
from domain.extraction.ports import ReferenceSource
from domain.extraction.value_objects import LayerInput, LayerOutput
from utils.logger import get_logger

logger = get_logger(__name__)


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
        return LayerOutput(entities=entities, metadata={"reason": "empty_text"})

    if not input.existing_entities:
        return LayerOutput(
            entities=entities,
            metadata={"reason": "no_prior_entities", "enriched_count": 0},
        )

    # Filter to available sources
    available_sources = [s for s in sources if s.is_available()]

    if not available_sources:
        return LayerOutput(
            entities=[],
            metadata={
                "reason": "no_available_reference_sources",
                "prior_entities": len(input.existing_entities),
                "enriched_count": 0,
            },
        )

    # For each entity from prior layers, attempt to enrich with reference data
    enrichment_count = 0
    enriched_ids = set()

    for prior_entity in input.existing_entities:
        # Skip if we already enriched this entity ID in this pass
        if prior_entity.id in enriched_ids:
            continue

        # Search for this entity in available reference sources
        # We try sources in order and use the first match
        for source in available_sources:
            try:
                results = source.search(prior_entity.label, limit=5)
            except Exception as e:
                logger.warning(
                    f"Source {source.source_name} failed during search for '{prior_entity.label}': {e}"
                )
                continue

            if results:
                # Use the top result to create an enriched entity
                top_result = results[0]

                # Create enriched entity with SAME ID as the prior entity
                # This ensures deduplication can recognize them as the same concept
                enriched_entity = ExtractedEntity(
                    id=prior_entity.id,  # SAME ID—critical for dedup to merge them
                    label=prior_entity.label,  # Keep original label
                    entity_type=prior_entity.entity_type,  # Keep original type
                    source_layer=prior_entity.source_layer,  # Keep original layer for priority
                    confidence=prior_entity.confidence,  # Keep original confidence
                    uri=top_result.uri or prior_entity.uri,  # Prefer reference URI if available
                    description=top_result.description or prior_entity.description,  # Add reference description
                    matched_class_id=prior_entity.matched_class_id,  # Keep original class match
                    properties={
                        **(prior_entity.properties or {}),  # Start with original properties
                        "reference_source": source.source_name,  # Track which source enriched this
                        "reference_label": top_result.label,  # Keep reference's label for comparison
                    },
                )
                entities.append(enriched_entity)
                enriched_ids.add(prior_entity.id)
                enrichment_count += 1
                break  # Move to next entity after first source match

    return LayerOutput(
        entities=entities,
        metadata={
            "prior_entities": len(input.existing_entities),
            "enriched_count": enrichment_count,
            "sources_checked": len(available_sources),
            "sources_available": [s.source_name for s in available_sources],
        },
    )
