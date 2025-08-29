# NLP Enrichment API Implementation Integration

## Integration with Existing Codebase

### 1. Database Models Extension

Extend existing `database/models.py` to support enrichment data:

```python
# Add to database/models.py

class EnrichmentEntity(Base):
    """Stores enriched entities from reference APIs"""
    __tablename__ = "enrichment_entities"
    
    id = Column(String, primary_key=True)  # entity_id from standardized model
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    description = Column(Text)
    aliases = Column(JSON)  # List of alternative names
    properties = Column(JSON)  # Serialized properties
    source_ids = Column(JSON)  # Dict of source -> source_id
    confidence = Column(Float)
    coordinates = Column(JSON)  # Lat/lng if applicable
    temporal_range = Column(JSON)  # Time period if applicable
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EnrichmentRelation(Base):
    """Stores relationships between enriched entities"""
    __tablename__ = "enrichment_relations"
    
    id = Column(String, primary_key=True)
    subject_entity_id = Column(String, ForeignKey("enrichment_entities.id"), nullable=False)
    predicate_name = Column(String, nullable=False)
    predicate_uri = Column(String)
    object_entity_id = Column(String, ForeignKey("enrichment_entities.id"), nullable=False)
    confidence = Column(Float)
    properties = Column(JSON)  # Additional relation metadata
    source_name = Column(String, nullable=False)
    source_url = Column(String)
    temporal_context = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class EnrichmentCache(Base):
    """Caches enrichment results for text spans"""
    __tablename__ = "enrichment_cache"
    
    id = Column(String, primary_key=True)  # Hash of text + config
    text_hash = Column(String, nullable=False, index=True)
    original_text = Column(Text, nullable=False)
    config_hash = Column(String, nullable=False)  # Hash of enrichment config
    results = Column(JSON, nullable=False)  # Serialized StandardizedEnrichmentResponse
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
```

### 2. Service Layer Implementation

Create `enrichment/` module structure:

```
enrichment/
├── __init__.py
├── service.py              # Main enrichment service
├── mappers/               # Source-specific mappers
│   ├── __init__.py
│   ├── dbpedia.py
│   ├── conceptnet.py
│   ├── wikidata.py
│   └── schema_org.py
├── resolvers/             # Entity resolution
│   ├── __init__.py
│   ├── entity_resolver.py
│   └── similarity.py
└── models.py              # Pydantic models from design doc
```

### 3. Main Enrichment Service

```python
# enrichment/service.py

from typing import List, Dict, Optional, Any
from .models import StandardizedEnrichmentResponse, EnrichmentConfig, Entity, Relation
from .mappers import DBpediaMapper, ConceptNetMapper, WikidataMapper, SchemaOrgMapper
from .resolvers import EntityResolver
from nlp.proxy_manager import get_proxy_manager
from database.utils import get_db_session
from database.models import EnrichmentCache
import hashlib
import json
from datetime import datetime, timedelta

class EnrichmentService:
    """Main service for text enrichment using reference APIs"""
    
    def __init__(self, config: EnrichmentConfig):
        self.config = config
        self.entity_resolver = EntityResolver()
        self.mappers = {
            'dbpedia': DBpediaMapper(),
            'conceptnet': ConceptNetMapper(),
            'wikidata': WikidataMapper(),
            'schema_org': SchemaOrgMapper()
        }
    
    async def enrich_text(self, text: str, sources: Optional[List[str]] = None) -> StandardizedEnrichmentResponse:
        """Main enrichment method"""
        start_time = datetime.utcnow()
        
        # Check cache first
        if self.config.cache_enabled:
            cached_result = await self._get_cached_result(text, sources)
            if cached_result:
                return cached_result
        
        # Use configured sources if none specified
        if not sources:
            sources = self.config.enabled_sources
        
        # Process each source
        source_results = {}
        source_stats = {}
        
        for source in sources:
            if source in self.config.enabled_sources:
                try:
                    results, stats = await self._process_source(text, source)
                    source_results[source] = results
                    source_stats[source] = stats
                except Exception as e:
                    source_stats[source] = {"error": str(e), "entities": 0, "relations": 0}
        
        # Resolve and merge entities
        all_entities = []
        all_relations = []
        
        for source, results in source_results.items():
            all_entities.extend(results.get('entities', []))
            all_relations.extend(results.get('relations', []))
        
        # Entity resolution and deduplication
        resolved_entities = self.entity_resolver.resolve_entities(all_entities)
        
        # Build response
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        response = StandardizedEnrichmentResponse(
            original_text=text,
            processing_time_ms=int(processing_time),
            timestamp=start_time,
            entities=resolved_entities,
            relations=all_relations,
            source_stats=source_stats,
            total_entities=len(resolved_entities),
            total_relations=len(all_relations),
            sources_used=list(source_results.keys())
        )
        
        # Cache result
        if self.config.cache_enabled:
            await self._cache_result(text, sources, response)
        
        # Store in database
        await self._store_enrichment_data(response)
        
        return response
    
    async def _process_source(self, text: str, source: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Process text with a specific source"""
        mapper = self.mappers[source]
        
        if source == 'dbpedia':
            return await self._process_dbpedia(text, mapper)
        elif source == 'conceptnet':
            return await self._process_conceptnet(text, mapper)
        elif source == 'wikidata':
            return await self._process_wikidata(text, mapper)
        elif source == 'schema_org':
            return await self._process_schema_org(text, mapper)
        else:
            raise ValueError(f"Unknown source: {source}")
    
    async def _process_dbpedia(self, text: str, mapper: DBpediaMapper) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Process text using DBpedia APIs"""
        entities = []
        relations = []
        stats = {"entities": 0, "relations": 0, "api_calls": 0}
        
        # Use existing NLP pipeline to identify potential entities
        # Then enrich each entity with DBpedia data
        
        # 1. Use DBpedia Spotlight for entity recognition
        spotlight_results = await self._call_dbpedia_spotlight(text)
        stats["api_calls"] += 1
        
        for mention in spotlight_results.get('Resources', []):
            # 2. Get full entity data from DBpedia
            entity_data = await self._call_dbpedia_resource(mention['@URI'])
            stats["api_calls"] += 1
            
            # 3. Map to standardized entity
            entity = mapper.map_entity(entity_data)
            entities.append(entity)
            stats["entities"] += 1
            
            # 4. Get relations for this entity
            entity_relations = await self._call_dbpedia_relations(mention['@URI'])
            for rel_data in entity_relations:
                relation = mapper.map_relation(rel_data)
                relations.append(relation)
                stats["relations"] += 1
        
        return {"entities": entities, "relations": relations}, stats
    
    async def _call_dbpedia_spotlight(self, text: str) -> Dict[str, Any]:
        """Call DBpedia Spotlight API (via proxy if enabled)"""
        proxy_manager = get_proxy_manager()
        
        if proxy_manager.is_running and 'spacy_dbpedia_spotlight' in proxy_manager.config.get('domain_mappings', {}):
            # Use proxy
            url = f"http://127.0.0.1:{proxy_manager.config['server']['port']}/dbpedia_spotlight/annotate"
        else:
            # Direct API call
            url = "https://api.dbpedia-spotlight.org/en/annotate"
        
        # Implementation of actual HTTP call
        # Return parsed JSON response
        pass
    
    def _generate_cache_key(self, text: str, sources: Optional[List[str]]) -> str:
        """Generate cache key for text and configuration"""
        config_str = json.dumps({
            "sources": sources or self.config.enabled_sources,
            "config": self.config.dict()
        }, sort_keys=True)
        
        combined = f"{text}:{config_str}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    async def _get_cached_result(self, text: str, sources: Optional[List[str]]) -> Optional[StandardizedEnrichmentResponse]:
        """Retrieve cached enrichment result"""
        cache_key = self._generate_cache_key(text, sources)
        
        with get_db_session() as session:
            cache_entry = session.query(EnrichmentCache).filter_by(id=cache_key).first()
            
            if cache_entry and cache_entry.expires_at > datetime.utcnow():
                return StandardizedEnrichmentResponse.parse_obj(cache_entry.results)
        
        return None
```

### 4. API Router Implementation

```python
# api/enrichment.py

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from enrichment.service import EnrichmentService
from enrichment.models import StandardizedEnrichmentResponse, EnrichmentConfig
from config import get_settings
from utils.logger import get_logger

router = APIRouter(prefix="/api/nlp_analysis/enrich", tags=["enrichment"])
logger = get_logger(__name__)

# Request models
class EnrichTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    sources: Optional[List[str]] = Field(None, description="Sources to use for enrichment")
    options: Optional[Dict[str, Any]] = Field(None, description="Enrichment options")

class BatchEnrichRequest(BaseModel):
    texts: List[Dict[str, str]] = Field(..., description="List of {id, text} pairs")
    sources: Optional[List[str]] = Field(None)
    options: Optional[Dict[str, Any]] = Field(None)

class EntityResolveRequest(BaseModel):
    entity: Dict[str, Any] = Field(..., description="Entity to resolve")
    sources: Optional[List[str]] = Field(None)
    options: Optional[Dict[str, Any]] = Field(None)

# Dependency to get enrichment service
def get_enrichment_service() -> EnrichmentService:
    settings = get_settings()
    config = EnrichmentConfig(**settings.ENRICHMENT_CONFIG)
    return EnrichmentService(config)

@router.post("/", response_model=StandardizedEnrichmentResponse)
async def enrich_text(
    request: EnrichTextRequest,
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Enrich text with entity and relation information from reference APIs"""
    try:
        # Apply options to service config if provided
        if request.options:
            # Create temporary config with options applied
            config_dict = service.config.dict()
            config_dict.update(request.options)
            temp_config = EnrichmentConfig(**config_dict)
            service.config = temp_config
        
        result = await service.enrich_text(request.text, request.sources)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error enriching text: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/batch")
async def enrich_batch(
    request: BatchEnrichRequest,
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Batch enrich multiple texts"""
    try:
        results = {}
        
        for text_item in request.texts:
            text_id = text_item["id"]
            text_content = text_item["text"]
            
            result = await service.enrich_text(text_content, request.sources)
            results[text_id] = result
        
        return {"results": results, "total_processed": len(request.texts)}
        
    except Exception as e:
        logger.error(f"Error in batch enrichment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/entity/{entity_id}")
async def get_entity_enrichment(
    entity_id: str,
    sources: Optional[str] = None,
    include_relations: bool = True,
    relation_depth: int = 1,
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Get enrichment data for a specific entity"""
    try:
        source_list = sources.split(",") if sources else None
        
        # Implementation would retrieve entity from database
        # and optionally refresh from sources
        
        return {"entity_id": entity_id, "message": "Not implemented yet"}
        
    except Exception as e:
        logger.error(f"Error getting entity enrichment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/sources")
async def list_sources(service: EnrichmentService = Depends(get_enrichment_service)):
    """List available enrichment sources and their status"""
    try:
        sources = {}
        
        for source in service.config.enabled_sources:
            # Check if source is available via proxy or direct connection
            status = await service._check_source_health(source)
            sources[source] = status
        
        return {
            "sources": sources,
            "total_enabled": len(service.config.enabled_sources)
        }
        
    except Exception as e:
        logger.error(f"Error listing sources: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cache/stats")
async def get_cache_stats():
    """Get enrichment cache statistics"""
    try:
        with get_db_session() as session:
            total_entries = session.query(EnrichmentCache).count()
            active_entries = session.query(EnrichmentCache).filter(
                EnrichmentCache.expires_at > datetime.utcnow()
            ).count()
            
        return {
            "total_entries": total_entries,
            "active_entries": active_entries,
            "expired_entries": total_entries - active_entries
        }
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 5. Configuration Updates

Add to `config.py`:

```python
# Add to config.py

class Settings(BaseSettings):
    # ... existing settings ...
    
    # Enrichment API configuration
    ENRICHMENT_CONFIG: Dict[str, Any] = {
        "enabled_sources": ["dbpedia", "conceptnet", "wikidata", "schema_org"],
        "source_weights": {
            "dbpedia": 1.0,
            "conceptnet": 0.8,
            "wikidata": 1.0,
            "schema_org": 0.6
        },
        "source_timeouts": {
            "dbpedia": 30,
            "conceptnet": 20,
            "wikidata": 30,
            "schema_org": 10
        },
        "max_entities_per_source": 10,
        "confidence_threshold": 0.5,
        "enable_relation_discovery": True,
        "max_relation_depth": 2,
        "entity_similarity_threshold": 0.8,
        "enable_cross_source_resolution": True,
        "cache_enabled": True,
        "cache_ttl_seconds": 3600,
        "supported_languages": ["en"],
        "default_language": "en"
    }
```

### 6. Integration with Main App

Update `app.py` to include the new router:

```python
# Add to app.py

from api import enrichment

# Include the enrichment router
app.include_router(enrichment.router)
```

This integration plan shows how the enrichment API would fit seamlessly into the existing codebase while leveraging current infrastructure like the proxy manager, database utilities, and configuration system.
