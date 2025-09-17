"""Pydantic models for the enrichment service.

This module implements the full set of request/response models described in
the enrichment design (DBpedia, ConceptNet, Wikidata, Schema.org).
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    DBPEDIA = "dbpedia"
    CONCEPTNET = "conceptnet"
    WIKIDATA = "wikidata"
    SCHEMA_ORG = "schema_org"


class ResponseFormat(str, Enum):
    JSON = "json"
    XML = "xml"
    RDF = "rdf"


# Base response model for all sources
class BaseSourceResponse(BaseModel):
    """Base response model for all reference API sources"""
    success: bool = Field(..., description="Whether the request was successful")
    source: SourceType = Field(..., description="Source that provided the data")
    retrieved_at: datetime = Field(..., description="Timestamp when data was retrieved")
    error: Optional[str] = Field(None, description="Error message if success is false")


# ------------------ DBpedia Models ------------------
class DBpediaResourceRequest(BaseModel):
    """Request model for DBpedia resource retrieval"""
    resource_url: str = Field(..., description="DBpedia resource URL")
    format: ResponseFormat = Field(ResponseFormat.JSON, description="Response format")

    @field_validator('resource_url')
    @classmethod
    def validate_resource_url(cls, v):
        # More flexible validation - accept any URL that contains dbpedia.org/resource/
        if 'dbpedia.org/resource/' not in v:
            raise ValueError('Must be a valid DBpedia resource URL containing dbpedia.org/resource/')
        return v


class DBpediaResourceResponse(BaseSourceResponse):
    """Response model for DBpedia resource data"""
    resource_uri: Optional[str] = None
    data_url: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class DBpediaSearchRequest(BaseModel):
    """Request model for DBpedia search"""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Result offset for pagination")
    format: ResponseFormat = Field(ResponseFormat.JSON, description="Response format")


class DBpediaSearchResult(BaseModel):
    """Individual DBpedia search result"""
    uri: str
    label: str
    description: Optional[str] = None
    score: float = Field(..., ge=0.0, le=1.0)
    types: List[str] = Field(default_factory=list)


class DBpediaSearchResponse(BaseSourceResponse):
    """Response model for DBpedia search"""
    query: Optional[str] = None
    total_results: Optional[int] = None
    results: List[DBpediaSearchResult] = Field(default_factory=list)


class DBpediaSparqlRequest(BaseModel):
    """Request model for DBpedia SPARQL query"""
    query: str = Field(..., min_length=1, description="SPARQL query")
    format: ResponseFormat = Field(ResponseFormat.JSON, description="Response format")

    @field_validator('query')
    @classmethod
    def validate_sparql_query(cls, v):
        # Basic SPARQL validation
        v = v.strip()
        if not any(keyword in v.upper() for keyword in ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE']):
            raise ValueError('Must be a valid SPARQL query')
        return v


class DBpediaSparqlResponse(BaseSourceResponse):
    """Response model for DBpedia SPARQL query"""
    query_type: str = "sparql"
    results: Optional[Dict[str, Any]] = None


# ------------------ ConceptNet Models ------------------
class ConceptNetQueryRequest(BaseModel):
    """Request model for ConceptNet query"""
    start: Optional[str] = Field(None, description="Starting concept (e.g., /c/en/apple)")
    end: Optional[str] = Field(None, description="Ending concept")
    node: Optional[str] = Field(None, description="Any concept")
    rel: Optional[str] = Field(None, description="Relation type (e.g., /r/IsA)")
    limit: int = Field(20, ge=1, le=100, description="Result limit")
    offset: int = Field(0, ge=0, description="Result offset")

    @field_validator('start', 'end', 'node')
    @classmethod
    def validate_concept_format(cls, v):
        if v and not v.startswith('/c/'):
            raise ValueError('Concept must start with /c/')
        return v

    @field_validator('rel')
    @classmethod
    def validate_relation_format(cls, v):
        if v and not v.startswith('/r/'):
            raise ValueError('Relation must start with /r/')
        return v


class ConceptNetEdge(BaseModel):
    """ConceptNet edge representation"""
    id: str = Field(..., alias='@id')
    start: Dict[str, str]
    rel: Dict[str, str]
    end: Dict[str, str]
    weight: float
    sources: Optional[List[Dict[str, str]]] = None


class ConceptNetQueryResponse(BaseSourceResponse):
    """Response model for ConceptNet query"""
    query_params: Optional[Dict[str, str]] = None
    edges: List[ConceptNetEdge] = Field(default_factory=list)


class ConceptNetConceptResponse(BaseSourceResponse):
    """Response model for ConceptNet concept lookup"""
    concept: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ConceptNetRelatedConcept(BaseModel):
    """Related concept from ConceptNet"""
    id: str = Field(..., alias='@id')
    label: str
    weight: float


class ConceptNetRelatedResponse(BaseSourceResponse):
    """Response model for ConceptNet related concepts"""
    concept: Optional[str] = None
    filter: Optional[str] = None
    related: List[ConceptNetRelatedConcept] = Field(default_factory=list)


# ------------------ Wikidata Models ------------------
class WikidataSparqlRequest(BaseModel):
    """Request model for Wikidata SPARQL query"""
    query: str = Field(..., min_length=1, description="SPARQL query")
    format: ResponseFormat = Field(ResponseFormat.JSON, description="Response format")


class WikidataSparqlResponse(BaseSourceResponse):
    """Response model for Wikidata SPARQL query"""
    query_type: str = "sparql"
    results: Optional[Dict[str, Any]] = None


class WikidataEntityRequest(BaseModel):
    """Request model for Wikidata entity retrieval"""
    entity_url: str = Field(..., description="Wikidata entity URL")
    properties: Optional[List[str]] = Field(None, description="Specific properties to retrieve")
    format: ResponseFormat = Field(ResponseFormat.JSON, description="Response format")

    @field_validator('entity_url')
    @classmethod
    def validate_entity_url(cls, v):
        # More flexible validation - accept any URL that contains wikidata.org and entity/Q pattern
        if not ('wikidata.org' in v and ('/wiki/Q' in v or '/entity/Q' in v)):
            raise ValueError('Must be a valid Wikidata entity URL containing wikidata.org and entity/Q pattern')
        return v


class WikidataEntityResponse(BaseSourceResponse):
    """Response model for Wikidata entity data"""
    entity_id: Optional[str] = None
    entity_url: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# ------------------ Schema.org Models ------------------
class SchemaOrgEntityRequest(BaseModel):
    """Request model for Schema.org entity retrieval"""
    identifier: str = Field(..., description="Schema.org identifier")
    include_inherited: bool = Field(True, description="Include inherited properties")
    include_children: bool = Field(False, description="Include child entities")


class SchemaOrgProperty(BaseModel):
    """Schema.org property representation"""
    identifier: str
    title: str
    definition: Optional[str] = None
    expected_types: List[str] = Field(default_factory=list)
    inherited: bool = False
    inherited_from: Optional[str] = None


class SchemaOrgChildEntity(BaseModel):
    """Schema.org child entity representation"""
    identifier: str
    title: str


class SchemaOrgEntity(BaseModel):
    """Schema.org entity representation"""
    id: str
    identifier: str
    title: str
    definition: Optional[str] = None
    parent_identifier: Optional[str] = None
    properties: List[SchemaOrgProperty] = Field(default_factory=list)
    children: List[SchemaOrgChildEntity] = Field(default_factory=list)


class SchemaOrgEntityResponse(BaseSourceResponse):
    """Response model for Schema.org entity retrieval"""
    identifier: Optional[str] = None
    entity: Optional[SchemaOrgEntity] = None


class SchemaOrgPropertyRequest(BaseModel):
    """Request model for Schema.org property retrieval"""
    identifier: str = Field(..., description="Schema.org property identifier")
    include_usage: bool = Field(True, description="Include entities that use this property")


class SchemaOrgPropertyData(BaseModel):
    """Schema.org property data representation"""
    id: str
    identifier: str
    title: str
    definition: Optional[str] = None
    domain_includes: List[str] = Field(default_factory=list)
    range_includes: List[str] = Field(default_factory=list)
    inverse_of: List[str] = Field(default_factory=list)
    used_by_entities: List[Dict[str, str]] = Field(default_factory=list)


class SchemaOrgPropertyResponse(BaseSourceResponse):
    """Response model for Schema.org property retrieval"""
    identifier: Optional[str] = None
    property: Optional[SchemaOrgPropertyData] = None


class SchemaOrgSearchRequest(BaseModel):
    """Request model for Schema.org search"""
    query: str = Field(..., min_length=1, description="Search query")
    search_type: Literal["entities", "properties", "both"] = Field("both", description="Type of items to search")
    limit: int = Field(20, ge=1, le=100, description="Result limit")
    offset: int = Field(0, ge=0, description="Result offset")
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Similarity threshold for semantic search")


class SchemaOrgSearchResult(BaseModel):
    """Schema.org search result"""
    type: Literal["entity", "property"]
    identifier: str
    title: str
    definition: Optional[str] = None
    relevance_score: float


class SchemaOrgSearchResponse(BaseSourceResponse):
    """Response model for Schema.org search"""
    query: Optional[str] = None
    search_type: Optional[str] = None
    total_results: Optional[int] = None
    results: List[SchemaOrgSearchResult] = Field(default_factory=list)


# ------------------ WordNet Models ------------------
class WordNetSearchRequest(BaseModel):
    """Request model for WordNet search"""
    word: str = Field(..., min_length=1, description="Word to search for")
    pos: Optional[Literal["noun", "verb", "adj", "adv"]] = Field(None, description="Part of speech filter")
    lang: str = Field("eng", description="Language (default: English)")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of synsets")

class WordNetSynset(BaseModel):
    """WordNet synset representation"""
    id: str = Field(..., description="Synset ID")
    name: str = Field(..., description="Synset name")
    pos: str = Field(..., description="Part of speech")
    definition: str = Field(..., description="Definition")
    examples: List[str] = Field(default_factory=list, description="Usage examples")
    lemmas: List[str] = Field(default_factory=list, description="Lemma names")
    lexfile: Optional[str] = Field(None, description="Lexical file")
    offset: Optional[int] = Field(None, description="WordNet offset")

class WordNetSearchResponse(BaseSourceResponse):
    """Response model for WordNet search"""
    word: Optional[str] = None
    pos: Optional[str] = None
    synsets: List[WordNetSynset] = Field(default_factory=list)

class WordNetRelationsRequest(BaseModel):
    """Request model for WordNet relations"""
    synset_id: str = Field(..., description="Synset ID to get relations for")
    relation_types: Optional[List[str]] = Field(None, description="Specific relation types")

class WordNetRelation(BaseModel):
    """WordNet semantic relation"""
    relation_type: str = Field(..., description="Type of relation")
    target_synset: WordNetSynset = Field(..., description="Target synset")

class WordNetRelationsResponse(BaseSourceResponse):
    """Response model for WordNet relations"""
    synset_id: Optional[str] = None
    relations: List[WordNetRelation] = Field(default_factory=list)


# ------------------ Multi-Source Search Models ------------------
class SearchNode(BaseModel):
    """Simplified node representation for multi-source search results"""
    id: str = Field(..., description="Unique identifier from source")
    source: SourceType = Field(..., description="Original source of the node")
    title: str = Field(..., min_length=1, description="Primary label or title")
    definition: Optional[str] = Field(None, description="Definition or description")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Source-specific attributes")
    source_url: Optional[str] = Field(None, description="URL to original resource")
    relevance_score: float = Field(default=1.0, ge=0, le=1, description="Source relevance score")

    @field_validator('source_url')
    @classmethod
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Invalid URL format')
        return v


class MultiSourceSearchRequest(BaseModel):
    """Request model for multi-source search"""
    query: str = Field(..., min_length=1, description="Search query string")
    sources: Optional[List[SourceType]] = Field(None, description="Specific sources to search (default: all enabled)")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results per source")
    offset: int = Field(default=0, ge=0, description="Result offset for pagination")


class MultiSourceSearchResponse(BaseModel):
    """Response model for multi-source search"""
    query: str = Field(..., description="Original search query")
    results: List[SearchNode] = Field(..., description="Search results from all sources")
    total_results: int = Field(..., description="Total number of results across all sources")
    sources_queried: List[str] = Field(..., description="Sources that were queried")
    source_errors: Dict[str, str] = Field(default_factory=dict, description="Errors encountered per source")
    offset: int = Field(..., description="Result offset used")
    limit: int = Field(..., description="Result limit used per source")
    search_time_ms: float = Field(..., description="Total search time in milliseconds")
