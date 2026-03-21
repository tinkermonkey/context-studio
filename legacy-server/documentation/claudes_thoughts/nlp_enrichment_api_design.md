# NLP Enrichment API Design Specification

## API Endpoints

### 1. Text Enrichment Endpoints

#### `POST /api/nlp_analysis/enrich`
**Primary enrichment endpoint for text analysis**

```json
{
  "text": "Apple Inc. is a technology company founded by Steve Jobs in Cupertino.",
  "sources": ["dbpedia", "conceptnet", "wikidata", "schema_org"],
  "options": {
    "max_results_per_source": 10,
    "confidence_threshold": 0.7,
    "include_relations": true,
    "relation_depth": 2,
    "language": "en",
    "entity_types": ["Organization", "Person", "Place"]
  }
}
```

**Response**: StandardizedEnrichmentResponse (see data model below)

#### `POST /api/nlp_analysis/enrich/batch`
**Batch processing for multiple texts**

```json
{
  "texts": [
    {"id": "doc1", "text": "Apple Inc. is a technology company..."},
    {"id": "doc2", "text": "Microsoft Corporation develops software..."}
  ],
  "sources": ["dbpedia", "conceptnet"],
  "options": {
    "max_results_per_source": 5,
    "confidence_threshold": 0.8
  }
}
```

### 2. Entity-Specific Endpoints

#### `GET /api/nlp_analysis/enrich/entity/{entity_id}`
**Retrieve enrichment data for a specific entity**

Query Parameters:
- `sources`: Comma-separated list of sources
- `include_relations`: Boolean
- `relation_depth`: Integer (1-3)

#### `POST /api/nlp_analysis/enrich/entity/resolve`
**Resolve entity across multiple sources**

```json
{
  "entity": {
    "name": "Apple Inc.",
    "type": "Organization",
    "context": "technology company"
  },
  "sources": ["dbpedia", "wikidata"],
  "options": {
    "match_threshold": 0.8,
    "include_aliases": true
  }
}
```

### 3. Relation and Property Endpoints

#### `GET /api/nlp_analysis/enrich/relations`
**Get available relations/predicates from sources**

Query Parameters:
- `source`: Filter by source
- `domain`: Filter by domain type
- `range`: Filter by range type

#### `POST /api/nlp_analysis/enrich/relations/find`
**Find relations between entities**

```json
{
  "entity1": {
    "name": "Steve Jobs",
    "type": "Person"
  },
  "entity2": {
    "name": "Apple Inc.",
    "type": "Organization"
  },
  "sources": ["dbpedia", "conceptnet", "wikidata"]
}
```

### 4. Source-Specific Endpoints

#### `GET /api/nlp_analysis/enrich/sources`
**List available enrichment sources and their status**

#### `GET /api/nlp_analysis/enrich/sources/{source}/health`
**Check health/availability of a specific source**

#### `POST /api/nlp_analysis/enrich/sources/{source}/query`
**Direct query to a specific source (for debugging/testing)**

### 5. Cache and Management Endpoints

#### `GET /api/nlp_analysis/enrich/cache/stats`
**Get enrichment cache statistics**

#### `DELETE /api/nlp_analysis/enrich/cache/{entity_id}`
**Clear cache for specific entity**

#### `POST /api/nlp_analysis/enrich/cache/warm`
**Pre-populate cache with common entities**

## Standardized Data Model

### Core Entity Model

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from enum import Enum
from datetime import datetime

class EntityType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    PLACE = "Place"
    CONCEPT = "Concept"
    EVENT = "Event"
    WORK = "Work"
    PRODUCT = "Product"
    UNKNOWN = "Unknown"

class ConfidenceLevel(str, Enum):
    LOW = "low"          # 0.0 - 0.4
    MEDIUM = "medium"    # 0.4 - 0.7
    HIGH = "high"        # 0.7 - 0.9
    VERY_HIGH = "very_high"  # 0.9 - 1.0

class SourceInfo(BaseModel):
    """Information about the data source"""
    name: str = Field(..., description="Source name (dbpedia, conceptnet, etc.)")
    url: Optional[str] = Field(None, description="Original source URL")
    retrieved_at: datetime = Field(..., description="When data was retrieved")
    api_version: Optional[str] = Field(None, description="API version used")
    query_used: Optional[str] = Field(None, description="Query or method used")

class Property(BaseModel):
    """A property/attribute of an entity"""
    name: str = Field(..., description="Property name")
    value: Any = Field(..., description="Property value")
    type: str = Field(..., description="Property data type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    confidence_level: ConfidenceLevel = Field(..., description="Confidence category")
    source: SourceInfo = Field(..., description="Source information")
    language: str = Field(default="en", description="Language code")
    
class Entity(BaseModel):
    """Core entity representation"""
    id: str = Field(..., description="Unique entity identifier")
    name: str = Field(..., description="Primary entity name")
    type: EntityType = Field(..., description="Entity type")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    description: Optional[str] = Field(None, description="Entity description")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")
    confidence_level: ConfidenceLevel = Field(..., description="Confidence category")
    
    # Properties from all sources
    properties: List[Property] = Field(default_factory=list, description="Entity properties")
    
    # Source-specific identifiers
    source_ids: Dict[str, str] = Field(default_factory=dict, description="IDs in each source")
    
    # Provenance
    sources: List[SourceInfo] = Field(default_factory=list, description="Data sources")
    
    # Spatial/temporal context
    coordinates: Optional[Dict[str, float]] = Field(None, description="Lat/lng if applicable")
    temporal_range: Optional[Dict[str, str]] = Field(None, description="Time period if applicable")

class Predicate(BaseModel):
    """Relationship predicate between entities"""
    id: str = Field(..., description="Predicate identifier")
    name: str = Field(..., description="Human-readable predicate name")
    uri: Optional[str] = Field(None, description="URI/IRI if available")
    description: Optional[str] = Field(None, description="Predicate description")
    inverse: Optional[str] = Field(None, description="Inverse predicate name")
    domain_types: List[EntityType] = Field(default_factory=list, description="Valid subject types")
    range_types: List[EntityType] = Field(default_factory=list, description="Valid object types")
    source: SourceInfo = Field(..., description="Source information")

class Relation(BaseModel):
    """Relationship between entities"""
    id: str = Field(..., description="Unique relation identifier")
    subject_entity_id: str = Field(..., description="Subject entity ID")
    predicate: Predicate = Field(..., description="Relationship predicate")
    object_entity_id: str = Field(..., description="Object entity ID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Relation confidence")
    confidence_level: ConfidenceLevel = Field(..., description="Confidence category")
    
    # Additional relation properties
    properties: List[Property] = Field(default_factory=list, description="Relation metadata")
    source: SourceInfo = Field(..., description="Source information")
    
    # Temporal context for the relation
    temporal_context: Optional[Dict[str, str]] = Field(None, description="When relation was true")

class EnrichmentResult(BaseModel):
    """Result for a single text span or entity mention"""
    # Text context
    text_span: str = Field(..., description="Original text span")
    start_position: Optional[int] = Field(None, description="Start position in text")
    end_position: Optional[int] = Field(None, description="End position in text")
    
    # Entities found
    entities: List[Entity] = Field(default_factory=list, description="Identified entities")
    
    # Relations between entities
    relations: List[Relation] = Field(default_factory=list, description="Entity relationships")
    
    # Overall confidence for this result
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")
    confidence_level: ConfidenceLevel = Field(..., description="Confidence category")

class StandardizedEnrichmentResponse(BaseModel):
    """Complete response from enrichment API"""
    # Request context
    original_text: str = Field(..., description="Original input text")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    timestamp: datetime = Field(..., description="Processing timestamp")
    
    # Results
    results: List[EnrichmentResult] = Field(default_factory=list, description="Enrichment results")
    
    # All entities found (deduplicated)
    entities: Dict[str, Entity] = Field(default_factory=dict, description="All entities by ID")
    
    # All relations found
    relations: List[Relation] = Field(default_factory=list, description="All relations")
    
    # Source statistics
    source_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Per-source statistics")
    
    # Warnings and errors
    warnings: List[str] = Field(default_factory=list, description="Processing warnings")
    errors: List[str] = Field(default_factory=list, description="Processing errors")
    
    # Overall metadata
    total_entities: int = Field(..., description="Total entities found")
    total_relations: int = Field(..., description="Total relations found")
    sources_used: List[str] = Field(default_factory=list, description="Sources that provided data")
```

## Source-Specific Mapping Strategies

### DBpedia Mapping

```python
class DBpediaMapper:
    """Maps DBpedia RDF data to standardized model"""
    
    @staticmethod
    def map_entity(dbpedia_resource: Dict) -> Entity:
        """Map DBpedia resource to Entity"""
        return Entity(
            id=f"dbpedia:{dbpedia_resource['uri'].split('/')[-1]}",
            name=dbpedia_resource.get('rdfs:label', ''),
            type=DBpediaMapper._map_type(dbpedia_resource.get('rdf:type', [])),
            description=dbpedia_resource.get('rdfs:comment', ''),
            properties=DBpediaMapper._map_properties(dbpedia_resource),
            source_ids={"dbpedia": dbpedia_resource['uri']},
            # ... additional mapping logic
        )
    
    @staticmethod
    def _map_type(rdf_types: List[str]) -> EntityType:
        """Map DBpedia types to standard EntityType"""
        type_mapping = {
            'http://dbpedia.org/ontology/Person': EntityType.PERSON,
            'http://dbpedia.org/ontology/Organisation': EntityType.ORGANIZATION,
            'http://dbpedia.org/ontology/Place': EntityType.PLACE,
            # ... more mappings
        }
        for rdf_type in rdf_types:
            if rdf_type in type_mapping:
                return type_mapping[rdf_type]
        return EntityType.UNKNOWN
```

### ConceptNet Mapping

```python
class ConceptNetMapper:
    """Maps ConceptNet edges and concepts to standardized model"""
    
    @staticmethod
    def map_relation(edge: Dict) -> Relation:
        """Map ConceptNet edge to Relation"""
        return Relation(
            id=f"conceptnet:{edge['@id']}",
            subject_entity_id=ConceptNetMapper._concept_to_id(edge['start']),
            predicate=ConceptNetMapper._map_predicate(edge['rel']),
            object_entity_id=ConceptNetMapper._concept_to_id(edge['end']),
            confidence=edge.get('weight', 1.0),
            # ... additional mapping logic
        )
```

### Wikidata Mapping

```python
class WikidataMapper:
    """Maps Wikidata SPARQL results to standardized model"""
    
    @staticmethod
    def map_entity(wikidata_item: Dict) -> Entity:
        """Map Wikidata item to Entity"""
        return Entity(
            id=f"wikidata:{wikidata_item['item']['value'].split('/')[-1]}",
            name=wikidata_item.get('itemLabel', {}).get('value', ''),
            type=WikidataMapper._map_instance_type(wikidata_item),
            description=wikidata_item.get('itemDescription', {}).get('value', ''),
            # ... additional mapping logic
        )
```

### Schema.org Mapping

```python
class SchemaOrgMapper:
    """Maps Schema.org entities to standardized model"""
    
    @staticmethod
    def map_entity(schema_entity: Dict) -> Entity:
        """Map Schema.org entity to Entity"""
        return Entity(
            id=f"schema:{schema_entity['@type']}:{schema_entity.get('identifier', '')}",
            name=schema_entity.get('name', ''),
            type=SchemaOrgMapper._map_schema_type(schema_entity['@type']),
            properties=SchemaOrgMapper._map_schema_properties(schema_entity),
            # ... additional mapping logic
        )
```

## Entity Resolution and Deduplication

```python
class EntityResolver:
    """Resolves and deduplicates entities across sources"""
    
    def resolve_entities(self, entities: List[Entity]) -> Dict[str, Entity]:
        """Merge entities that refer to the same real-world entity"""
        resolved = {}
        entity_groups = self._group_similar_entities(entities)
        
        for group in entity_groups:
            merged_entity = self._merge_entity_group(group)
            resolved[merged_entity.id] = merged_entity
            
        return resolved
    
    def _calculate_similarity(self, entity1: Entity, entity2: Entity) -> float:
        """Calculate similarity score between entities"""
        # Name similarity (using fuzzy matching)
        name_sim = self._fuzzy_match(entity1.name, entity2.name)
        
        # Type compatibility
        type_sim = 1.0 if entity1.type == entity2.type else 0.0
        
        # Alias matching
        alias_sim = self._check_alias_overlap(entity1, entity2)
        
        # Source ID matching (same entity in different sources)
        id_sim = self._check_cross_source_ids(entity1, entity2)
        
        return (name_sim * 0.4 + type_sim * 0.2 + alias_sim * 0.2 + id_sim * 0.2)
```

## Configuration Schema

```python
class EnrichmentConfig(BaseModel):
    """Configuration for enrichment service"""
    
    # Source configuration
    enabled_sources: List[str] = Field(default=["dbpedia", "conceptnet", "wikidata", "schema_org"])
    source_weights: Dict[str, float] = Field(default_factory=dict)
    source_timeouts: Dict[str, int] = Field(default_factory=dict)
    
    # Processing configuration
    max_entities_per_source: int = Field(default=10)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    enable_relation_discovery: bool = Field(default=True)
    max_relation_depth: int = Field(default=2, ge=1, le=3)
    
    # Entity resolution
    entity_similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    enable_cross_source_resolution: bool = Field(default=True)
    
    # Caching
    cache_enabled: bool = Field(default=True)
    cache_ttl_seconds: int = Field(default=3600)
    
    # Language support
    supported_languages: List[str] = Field(default=["en"])
    default_language: str = Field(default="en")
```

This design provides a comprehensive foundation for normalizing data from all reference sources into a consistent, queryable format while maintaining provenance and confidence information throughout the enrichment process.
