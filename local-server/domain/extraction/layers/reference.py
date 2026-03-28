"""
Reference source enrichment layer (Layer 3).

Enriches extracted entities by resolving them against external reference
knowledge sources.
"""
from domain.extraction.entities import ExtractedEntity
from domain.extraction.ports import ReferenceSource
from domain.extraction.value_objects import LayerInput, LayerOutput


def execute(input: LayerInput, sources: list[ReferenceSource]) -> LayerOutput:
    """
    Enrich entities using external reference sources.

    Searches reference sources (ConceptNet, DBpedia, etc.) for each entity
    found in prior layers to add URIs and additional metadata.

    Args:
        input: LayerInput containing text and prior extraction context
        sources: List of ReferenceSource ports to query

    Returns:
        LayerOutput containing enriched entity data
    """
    entities: list[ExtractedEntity] = []

    if not input.text or not input.text.strip():
        return LayerOutput(entities=entities, metadata={"reason": "empty_text"})

    if not input.existing_entities:
        return LayerOutput(entities=entities, metadata={"reason": "no_prior_entities"})

    # Filter to available sources
    available_sources = [s for s in sources if s.is_available()]

    if not available_sources:
        return LayerOutput(
            entities=[],
            metadata={"reason": "no_available_reference_sources"},
        )

    # For each entity from prior layers, enrich with reference data
    enrichment_count = 0

    for prior_entity in input.existing_entities:
        # Search for this entity in reference sources
        for source in available_sources:
            results = source.search(prior_entity.label, limit=5)

            if results:
                # Use the top result to enrich the entity
                top_result = results[0]

                # Merge reference data into the prior entity's properties
                # without changing source_layer (keep original)
                enriched_entity = ExtractedEntity(
                    id=prior_entity.id,
                    label=prior_entity.label,
                    entity_type=prior_entity.entity_type,
                    source_layer=prior_entity.source_layer,  # Keep original layer
                    confidence=prior_entity.confidence,
                    uri=top_result.uri or prior_entity.uri,  # Prefer reference URI if available
                    description=top_result.description or prior_entity.description,
                    properties={
                        **(prior_entity.properties or {}),
                        "reference_source": source.source_name,
                        "reference_label": top_result.label,
                    },
                )
                entities.append(enriched_entity)
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
