"""
Knowledge Graph context extraction layer (Layer 0).

Extracts entities and relationships from the existing knowledge graph
to provide context for subsequent extraction layers.
"""
from domain.ontology.entities import Class, Individual, Taxonomy, ConceptScheme
from domain.extraction.entities import ExtractedEntity
from domain.extraction.value_objects import LayerOutput


def execute(text: str, ontology_repo, embedding_service) -> LayerOutput:
    """
    Extract entity mentions from existing knowledge graph.

    This layer searches the ontology repository for classes and individuals
    that are relevant to the input text, using semantic similarity to find
    matches.

    Args:
        text: The source text to extract from
        ontology_repo: OntologyRepository port for querying existing entities
        embedding_service: EmbeddingService port for semantic similarity

    Returns:
        LayerOutput containing entities found in the knowledge graph
    """
    entities: list[ExtractedEntity] = []

    if not text or not text.strip():
        return LayerOutput(entities=entities, metadata={"reason": "empty_text"})

    # Get embedding for the input text
    text_embedding = embedding_service.embed(text.strip())

    # Retrieve all entities from the ontology
    all_entities_result = ontology_repo.get_all_entities_and_relationships()

    if not all_entities_result or not all_entities_result[0]:
        return LayerOutput(
            entities=entities,
            metadata={
                "reason": "no_entities_in_repo",
                "matches_found": 0,
                "threshold": 0.7,
                "entities_checked": 0,
            }
        )

    all_entities, _ = all_entities_result

    # Search for semantically similar entities
    matches_found = 0
    for entity in all_entities:
        # Only consider Class and Individual entities with embeddings
        if not isinstance(entity, (Class, Individual)):
            continue

        if not entity.embedding:
            continue

        # Compute similarity
        similarity = embedding_service.similarity(text_embedding, entity.embedding)

        # Use similarity threshold of 0.7 for KG context
        if similarity >= 0.7:
            # Derive entity type from the entity class
            entity_type = entity.__class__.__name__
            # Extract URI from external references if available
            entity_uri = None
            if entity.external_references:
                entity_uri = entity.external_references[0].uri

            extracted = ExtractedEntity(
                label=entity.title,
                entity_type=entity_type,
                source_layer=0,
                confidence=float(similarity),
                uri=entity_uri,
                description=entity.description,
                properties={"kg_entity_id": entity.id},
            )
            entities.append(extracted)
            matches_found += 1

    return LayerOutput(
        entities=entities,
        metadata={
            "matches_found": matches_found,
            "threshold": 0.7,
            "entities_checked": len(all_entities),
        },
    )
