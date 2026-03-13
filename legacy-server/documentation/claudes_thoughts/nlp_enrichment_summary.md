# NLP Enrichment API: Endpoints and Data Model Summary

## Executive Summary

This document addresses points 1 and 2 from the feedback on the NLP Enrichment API requirements:
1. **Suggested API endpoints** with comprehensive request/response specifications
2. **Standardized data model** for normalizing data from all reference sources

## Key API Endpoints

### Primary Enrichment
- `POST /api/nlp_analysis/enrich` - Main text enrichment endpoint
- `POST /api/nlp_analysis/enrich/batch` - Batch processing for multiple texts

### Entity Management
- `GET /api/nlp_analysis/enrich/entity/{entity_id}` - Retrieve specific entity data
- `POST /api/nlp_analysis/enrich/entity/resolve` - Cross-source entity resolution

### Relationship Discovery
- `GET /api/nlp_analysis/enrich/relations` - Browse available predicates
- `POST /api/nlp_analysis/enrich/relations/find` - Find relations between entities

### Source Management
- `GET /api/nlp_analysis/enrich/sources` - List available sources and status
- `POST /api/nlp_analysis/enrich/sources/{source}/query` - Direct source queries

### Cache and Monitoring
- `GET /api/nlp_analysis/enrich/cache/stats` - Cache performance metrics
- `DELETE /api/nlp_analysis/enrich/cache/{entity_id}` - Cache management

## Standardized Data Model Highlights

### Core Entity Model
```python
class Entity(BaseModel):
    id: str                           # Unique identifier
    name: str                         # Primary name
    type: EntityType                  # Person, Organization, Place, etc.
    aliases: List[str]                # Alternative names
    description: str                  # Entity description
    confidence: float                 # 0.0-1.0 confidence score
    properties: List[Property]        # All properties from sources
    source_ids: Dict[str, str]        # Source-specific IDs
    sources: List[SourceInfo]         # Provenance tracking
```

### Unified Relationship Model
```python
class Relation(BaseModel):
    id: str                          # Unique relation ID
    subject_entity_id: str           # Subject entity
    predicate: Predicate             # Relationship type
    object_entity_id: str            # Object entity
    confidence: float                # Relation confidence
    source: SourceInfo               # Source provenance
    temporal_context: Dict           # Time-bound relations
```

### Response Format
```python
class StandardizedEnrichmentResponse(BaseModel):
    original_text: str               # Input text
    entities: Dict[str, Entity]      # All found entities
    relations: List[Relation]        # Entity relationships
    source_stats: Dict               # Per-source statistics
    processing_time_ms: int          # Performance metrics
    warnings: List[str]              # Processing warnings
    errors: List[str]                # Processing errors
```

## Source-Specific Normalization

### DBpedia
- Maps RDF triples to standardized entities and relations
- Converts DBpedia ontology types to standard EntityType enum
- Preserves URIs and handles multilingual labels

### ConceptNet
- Maps edges to standardized relations
- Converts concept nodes to entities
- Handles weighted relationships and confidence scores

### Wikidata
- Maps SPARQL results to entities and relations
- Converts Wikidata properties to standardized predicates
- Handles qualifiers and references

### Schema.org
- Maps local schema entities to standardized format
- Preserves inheritance hierarchy
- Converts schema properties to relations

## Key Design Principles

### 1. **Provenance Tracking**
Every piece of data includes source information, retrieval timestamp, and confidence scores.

### 2. **Confidence Management**
All entities and relations have numerical confidence scores (0.0-1.0) and categorical levels (low, medium, high, very_high).

### 3. **Entity Resolution**
Cross-source entity resolution using name similarity, type matching, alias comparison, and cross-reference validation.

### 4. **Flexible Configuration**
Configurable source selection, confidence thresholds, relation depth, and caching policies.

### 5. **Performance Optimization**
Multi-level caching (proxy cache, result cache, database cache) with intelligent cache invalidation.

### 6. **Error Resilience**
Graceful handling of partial failures, source timeouts, and data quality issues.

## Integration Benefits

### Leverages Existing Infrastructure
- Uses current proxy manager for caching
- Extends existing database models
- Follows established API patterns
- Integrates with current NLP pipeline

### Extensible Architecture
- Plugin-based source mappers
- Configurable entity resolution
- Flexible confidence scoring
- Modular relationship discovery

### Production Ready
- Comprehensive error handling
- Performance monitoring
- Cache management
- Security considerations

## Next Steps

1. **Detailed Implementation Planning**: Break down into implementable tasks
2. **Database Migration**: Create migration scripts for new tables
3. **Source Mapper Development**: Implement each source-specific mapper
4. **Entity Resolution Algorithms**: Develop similarity matching and deduplication
5. **API Testing**: Comprehensive test suite for all endpoints
6. **Performance Optimization**: Benchmark and optimize for production workloads

This design provides a solid foundation for building a robust, scalable NLP enrichment API that can effectively normalize and integrate data from multiple reference sources while maintaining high performance and data quality standards.
