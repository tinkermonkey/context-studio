# mypy: ignore-errors
"""
Configuration settings for the Context Studio Local Server.
"""

import os
import json
import threading
import asyncio
from typing import Dict, Any, Optional, List, Callable
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from enum import Enum
from dataclasses import dataclass
from dotenv import load_dotenv

from utils.logger import get_logger

logger = get_logger(__name__)


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class S3Config:
    bucket: str
    region: str = "us-east-1"
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    endpoint: Optional[str] = None  # For S3-compatible services


class ServerConfig(BaseModel):
    """Server configuration section"""
    host: str = Field(default="127.0.0.1", description="Server host address")
    port: int = Field(default=8000, ge=1024, le=65535, description="Server port")
    reload: bool = Field(default=True, description="Enable auto-reload in development")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    access_log: bool = Field(default=False, description="Enable uvicorn access logs")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Server log level")


class DatabaseConfig(BaseModel):
    """Database configuration section"""
    default_url: str = Field(default="sqlite:///./datafiles/local.db", description="Default database URL")
    default_dataset_filename: str = Field(default="default.db", description="Default dataset filename")
    datasets_directory: Optional[str] = Field(default=None, description="Directory for dataset management. If None or path doesn't exist, dataset manager is disabled and default_url is used directly.")
    reference_path: str = Field(default="./datafiles/reference.db", description="Reference database path (multi-source knowledge graph)")
    reference_cache_path: str = Field(default="./datafiles/reference_api_cache.db", description="Reference API cache database path")
    operations_path: str = Field(default="./datafiles/operations.db", description="Operations database path (pipeline configs, audit logs, task management)")
    check_same_thread: bool = Field(default=False, description="SQLite check_same_thread setting")
    pool_timeout: int = Field(default=30, ge=1, description="Database pool timeout seconds")
    

class LLMConfig(BaseModel):
    """Large Language Model configuration section"""
    model_name: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32000, description="Maximum tokens for response")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    max_text_length: int = Field(default=1000, ge=1, le=10000, description="Maximum input text length")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    

class NLPConfig(BaseModel):
    """Natural Language Processing configuration section"""
    model_name: str = Field(default="en_core_web_lg", description="spaCy model name")
    max_text_length: int = Field(default=512, ge=1, le=10000, description="Maximum text length for analysis")
    sense2vec_path: str = Field(default="./downloads/s2v_reddit_2015_md", description="Sense2Vec model path")
    concepcy_relations: List[str] = Field(default=["RELATED_TO", "IS_A", "PART_OF"], description="List of ConceptNet relations to use")
    filter_missing_text: bool = Field(default=True, description="Whether to filter out missing text")
    edge_weight_filter: float = Field(default=2.0, ge=0.0, description="Minimum edge weight for filtering")
    request_timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")

    # Model auto-download settings
    auto_download_models: bool = Field(default=True, description="Automatically download missing NLP models on startup")
    download_timeout: int = Field(default=600, ge=60, le=1800, description="Timeout for model downloads in seconds")


class RAGPipelineConfig(BaseModel):
    """RAG (Retrieval-Augmented Generation) pipeline configuration section"""

    # Knowledge graph context retrieval settings
    kg_context_top_k: int = Field(default=50, ge=1, le=1000, description="Top-k results for knowledge graph context retrieval")
    kg_vector_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Minimum similarity threshold for vector search in knowledge graph (Layer 0 and Layer 3)")

    # RAG Pipeline layer timeouts (in seconds)
    timeout_layer_0: float = Field(default=1.0, ge=0.1, le=60.0, description="Timeout for Layer 0 (KG context preparation) in seconds")
    timeout_layer_1: float = Field(default=30.0, ge=1.0, le=300.0, description="Timeout for Layer 1 (LLM extraction) in seconds")
    timeout_layer_2: float = Field(default=0.5, ge=0.1, le=60.0, description="Timeout for Layer 2 (spaCy gap detection) in seconds")
    timeout_layer_3: float = Field(default=30.0, ge=1.0, le=300.0, description="Timeout for Layer 3 (concept resolution) in seconds")

    # LLM pipeline settings
    llm_pipeline_flavor: Optional[str] = Field(default=None, description="LLM pipeline flavor to use for RAG operations")
    llm_timeout: int = Field(default=30, ge=1, le=300, description="LLM request timeout in seconds (deprecated: use timeout_layer_1 instead)")
    enable_llm_layer: bool = Field(default=True, description="Enable Layer 1 LLM extraction (can be disabled for testing or cost reduction)")

    # Gap detection settings
    gap_detection_deps: List[str] = Field(default_factory=list, description="Dependencies for gap detection layer")

    # Web search settings
    web_search_enabled: bool = Field(default=True, description="Enable web search for gap filling")
    web_search_max_attempts: int = Field(default=3, ge=1, le=10, description="Maximum web search attempts per query")
    web_search_rate_limit: int = Field(default=5, ge=1, le=100, description="Web search rate limit (searches per minute)")
    web_search_max_per_session: int = Field(default=10, ge=1, le=100, description="Maximum web searches per session")

    # Observability settings
    enable_observability: bool = Field(default=True, description="Enable observability and metrics collection")
    observability_retention_days: int = Field(default=30, ge=1, le=365, description="Retention period for metrics data in days")
    trace_retention_days: int = Field(default=7, ge=1, le=90, description="Retention period for trace data in days")
    trace_max_data_size_kb: int = Field(default=100, ge=1, le=10000, description="Maximum size of trace data per request in KB")

    # Deduplication settings
    deduplication_threshold: float = Field(default=0.9, ge=0.0, le=1.0, description="Similarity threshold for entity deduplication")

    # Extraction decision thresholds
    extraction_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold for entity extraction")


class ReferenceSourceRateLimitConfig(BaseModel):
    """Rate limiting configuration for a specific reference source"""
    requests_per_hour: int = Field(default=1000, ge=1, description="Requests per hour limit")
    requests_per_minute: Optional[int] = Field(default=None, ge=1, description="Requests per minute limit (optional)")
    requests_per_second: Optional[int] = Field(default=None, ge=1, description="Requests per second limit (optional)")
    progressive_delay: bool = Field(default=True, description="Enable progressive delay on rate limit")
    max_delay: int = Field(default=300, ge=1, description="Maximum delay in seconds")


class ReferenceSourceConfig(BaseModel):
    """Configuration for a specific reference source"""
    enabled: bool = Field(default=True, description="Enable this reference source")
    upstream_url: str = Field(..., description="Upstream API URL for this source")
    use_proxy: bool = Field(default=True, description="Route requests through caching proxy")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    rate_limit: ReferenceSourceRateLimitConfig = Field(default_factory=ReferenceSourceRateLimitConfig)
    
    # Source-specific configuration overrides
    custom_headers: Dict[str, str] = Field(default_factory=dict, description="Custom headers for requests")
    custom_params: Dict[str, str] = Field(default_factory=dict, description="Custom query parameters")


class ReferenceSourcesConfig(BaseModel):
    """Central configuration for all reference sources"""

    # Global language setting for all reference sources
    default_language: str = Field(default="en", description="Default language code for all reference source queries")

    # Global search timeout for multi-source search operations
    search_timeout: int = Field(default=30, ge=5, le=300, description="Timeout in seconds for multi-source search operations")

    # Reference link filtering settings
    enable_relevance_filtering: bool = Field(default=False, description="Enable predicate relevance filtering for reference queries by default")
    filter_cache_ttl: int = Field(default=300, ge=60, le=3600, description="Cache TTL for predicate relevance filters in seconds")

    # Individual source configurations
    conceptnet: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://api.conceptnet.io",
        rate_limit=ReferenceSourceRateLimitConfig(
            requests_per_hour=3600,
            requests_per_minute=60,  # Conservative: ~1/sec to avoid 30-60s hangs reported by users
            requests_per_second=1    # Very conservative to avoid API hangs
        )
    ))
    
    # DBpedia has multiple services, so we configure them separately
    dbpedia_lookup: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://lookup.dbpedia.org",
        rate_limit=ReferenceSourceRateLimitConfig(
            requests_per_hour=360000,  # 100 req/sec * 3600 sec
            requests_per_minute=6000,   # 100 req/sec * 60 sec
            requests_per_second=100     # Official limit: 100 req/sec per IP
        )
    ))

    dbpedia_sparql: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://dbpedia.org",
        rate_limit=ReferenceSourceRateLimitConfig(
            requests_per_hour=360000,  # 100 req/sec * 3600 sec
            requests_per_minute=6000,   # 100 req/sec * 60 sec
            requests_per_second=100     # Official limit: 100 req/sec per IP
        )
    ))

    dbpedia_spotlight: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://api.dbpedia-spotlight.org/en/",
        rate_limit=ReferenceSourceRateLimitConfig(
            requests_per_hour=100000,  # No official limit, but be reasonable
            requests_per_minute=1800,   # ~30 req/sec (documented self-hosted performance)
            requests_per_second=30      # Conservative based on documented performance
        )
    ))
    
    wikidata: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://query.wikidata.org",
        rate_limit=ReferenceSourceRateLimitConfig(
            requests_per_hour=3000,     # Conservative hourly limit
            requests_per_minute=50,     # 60 seconds of query time per minute, be conservative
            requests_per_second=2       # Conservative: allow short bursts but avoid overwhelming
        )
    ))
    
    duckduckgo: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://api.duckduckgo.com",
        rate_limit=ReferenceSourceRateLimitConfig(
            requests_per_hour=3600,  # Free API, conservative limit
            requests_per_minute=60,   # ~1 per second
            requests_per_second=1     # Conservative to avoid overwhelming free service
        )
    ))

    schema_org: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://schema.org",
        use_proxy=False,  # Local database, no proxy needed
        timeout=10,
        max_retries=1,
        rate_limit=ReferenceSourceRateLimitConfig(requests_per_hour=10000)  # Local, no real limit
    ))

    # LLM API endpoints - NOTE: Currently disabled for proxy routing
    # The reference-api-buddy proxy is a reverse proxy and doesn't support
    # HTTPS CONNECT tunneling required by OpenAI/Anthropic clients.
    # LLM response caching is handled by LangChain's built-in cache instead.
    openai: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://api.openai.com",
        use_proxy=False,  # Disabled: requires CONNECT proxy, not reverse proxy
        enabled=True,
        timeout=60,
        max_retries=2,
        rate_limit=ReferenceSourceRateLimitConfig(
            requests_per_hour=500,      # Tier 1: 500 RPM for most models
            requests_per_minute=10,     # Conservative for free tier (3 RPM) / Tier 1
            requests_per_second=1,      # Avoid bursts, smooth rate limiting
            progressive_delay=True,
            max_delay=60
        )
    ))

    anthropic: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://api.anthropic.com",
        use_proxy=False,  # Disabled: requires CONNECT proxy, not reverse proxy
        enabled=True,
        timeout=60,
        max_retries=2,
        rate_limit=ReferenceSourceRateLimitConfig(
            requests_per_hour=3000,     # Tier 1: 50 RPM, being conservative at hourly level
            requests_per_minute=50,     # Tier 1: 50 RPM official limit
            requests_per_second=1,      # Smoothed: 1 request per second (60 RPM spread evenly)
            progressive_delay=True,
            max_delay=60
        )
    ))


class ProxyServerConfig(BaseModel):
    """Global proxy server configuration"""
    host: str = Field(default="127.0.0.1", description="Proxy server host")
    port: int = Field(default=18080, ge=1024, le=65535, description="Proxy server port")
    enabled: bool = Field(default=True, description="Enable proxy server globally")
    database_path: str = Field(default="./datafiles/reference_api_cache.db", description="Cache database path")
    max_cache_entries: int = Field(default=10000, ge=100, description="Maximum total cache entries")
    
    # Global cache defaults (can be overridden per source)
    default_cache_ttl: int = Field(default=3600, ge=60, description="Default cache TTL (seconds)")
    default_max_response_size: int = Field(default=10485760, ge=1024, description="Default maximum cached response size (bytes)")
    
    # Global rate limiting defaults
    default_requests_per_hour: int = Field(default=1000, ge=1, description="Default requests per hour")
    progressive_max_delay: int = Field(default=300, ge=1, description="Default maximum progressive delay (seconds)")


class LoggingConfig(BaseModel):
    """Logging configuration section"""
    level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    enable_console: bool = Field(default=False, description="Enable console logging")
    enable_file: bool = Field(default=True, description="Enable file logging")
    file_path: str = Field(default="./logs/context_studio.log", description="Log file path")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format")
    date_format: str = Field(default="%Y-%m-%d %H:%M:%S", description="Date format")
    max_file_size: int = Field(default=10485760, ge=1024, description="Maximum log file size (bytes)")
    backup_count: int = Field(default=5, ge=0, description="Number of backup files")


class SecurityConfig(BaseModel):
    """Security configuration section"""
    require_secure_key: bool = Field(default=False, description="Require secure key for proxy")
    secure_key: Optional[str] = Field(default=None, description="Secure key for proxy access")
    log_security_events: bool = Field(default=False, description="Log security events")
    api_key_header: str = Field(default="X-API-Key", description="API key header name")


# Legacy compatibility classes for backward compatibility
class SourceType(str, Enum):
    """Reference API source types for reference service (legacy compatibility)"""
    DBPEDIA = "dbpedia"
    CONCEPTNET = "conceptnet"
    WIKIDATA = "wikidata"
    SCHEMA_ORG = "schema_org"
    WORDNET = "wordnet"


class SourceConfig(BaseModel):
    """Configuration for individual reference API source (legacy compatibility)"""
    enabled: bool = Field(True, description="Whether this source is enabled")
    use_proxy: bool = Field(True, description="Whether to use caching proxy for this source")
    timeout: int = Field(30, ge=1, le=300, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum number of retries")
    base_url: Optional[str] = Field(None, description="Override base URL for source")



class Settings(BaseModel):
    """Centralized configuration settings"""

    model_config = ConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        env_nested_delimiter='__'
    )

    # Configuration sections
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    nlp: NLPConfig = Field(default_factory=NLPConfig)
    rag_pipeline: RAGPipelineConfig = Field(default_factory=RAGPipelineConfig)
    reference_sources: ReferenceSourcesConfig = Field(default_factory=ReferenceSourcesConfig)
    proxy_server: ProxyServerConfig = Field(default_factory=ProxyServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # S3 Configuration
    S3_BUCKET: Optional[str] = None
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_ENDPOINT: Optional[str] = None

    # DuckDB Configuration
    DUCKDB_MEMORY_LIMIT: str = "2GB"
    DUCKDB_THREADS: int = 4

    @property
    def s3_bucket(self) -> Optional[str]:
        return self.S3_BUCKET

    @property
    def s3_region(self) -> str:
        return self.S3_REGION

    @property
    def s3_access_key(self) -> Optional[str]:
        return self.S3_ACCESS_KEY

    @property
    def s3_secret_key(self) -> Optional[str]:
        return self.S3_SECRET_KEY

    @property
    def s3_endpoint(self) -> Optional[str]:
        return self.S3_ENDPOINT

    @property
    def duckdb_memory_limit(self) -> str:
        return self.DUCKDB_MEMORY_LIMIT

    @property
    def duckdb_threads(self) -> int:
        return self.DUCKDB_THREADS
    
    def get_s3_config(self) -> Optional[S3Config]:
        if not self.s3_bucket:
            return None
        return S3Config(
            bucket=self.s3_bucket,
            region=self.s3_region,
            access_key=self.s3_access_key,
            secret_key=self.s3_secret_key,
            endpoint=self.s3_endpoint
        )
    
    def get_source_config(self, source_name: str) -> ReferenceSourceConfig:
        """
        Get configuration for a specific reference source.
        
        Supports aliases for backwards compatibility:
        - 'dbpedia' maps to 'dbpedia_sparql' (SPARQL endpoint used for discovery)
        """
        # Handle aliases
        if source_name == 'dbpedia':
            source_name = 'dbpedia_sparql'
        
        if hasattr(self.reference_sources, source_name):
            return getattr(self.reference_sources, source_name)
        raise ValueError(f"Unknown reference source: {source_name}")
    
    def get_enabled_sources(self) -> List[str]:
        """Get list of enabled reference sources"""
        enabled = []
        for source_name in ["conceptnet", "dbpedia_lookup", "dbpedia_sparql", "dbpedia_spotlight", "wikidata", "schema_org"]:
            config = getattr(self.reference_sources, source_name, None)
            if config and config.enabled:
                enabled.append(source_name)
        return enabled
    
    def get_proxy_enabled_sources(self) -> List[str]:
        """Get list of sources that should use the proxy"""
        proxy_enabled: List[str] = []
        if not self.proxy_server.enabled:
            return proxy_enabled
            
        for source_name in self.get_enabled_sources():
            config = getattr(self.reference_sources, source_name)
            if config.use_proxy:
                proxy_enabled.append(source_name)
        return proxy_enabled
    
    def get_proxy_domain_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Build domain mappings for proxy configuration compatibility"""
        mappings = {}
        for source_name in self.get_proxy_enabled_sources():
            config = getattr(self.reference_sources, source_name)
            mappings[source_name] = {
                "upstream": config.upstream_url,
                "enabled_keys": [source_name],  # Can be extended for aliases
                "timeout": config.timeout,
                "max_retries": config.max_retries,
                "rate_limit": config.rate_limit.requests_per_hour
            }
        return mappings

    # Legacy compatibility methods for gradual migration
    def get_concepcy_config(self, use_proxy: bool = False) -> dict:
        """Get concepcy configuration with optional proxy URL (legacy compatibility)"""
        config = {
            "relations_of_interest": self.nlp.concepcy_relations,
            "filter_missing_text": self.nlp.filter_missing_text,
            "filter_edge_weight": self.nlp.edge_weight_filter
        }
        if use_proxy and self.proxy_server.enabled:
            host = self.proxy_server.host
            port = self.proxy_server.port
            config["url"] = f"http://{host}:{port}/conceptnet/query?node=/c/{{lang}}/{{word}}&other=/c/{{lang}}"
        return config

    def get_reference_api_buddy_config(self) -> dict:
        """Get complete reference API buddy configuration (legacy compatibility)"""
        domain_mappings = {}
        for source_name in self.get_proxy_enabled_sources():
            config = getattr(self.reference_sources, source_name)
            # Map to legacy keys for backward compatibility
            legacy_keys = {
                "conceptnet": ["concepcy", "conceptnet"],
                "dbpedia_spotlight": ["spacy_dbpedia_spotlight", "dbpedia_spotlight"],
                "dbpedia_lookup": ["dbpedia", "dbpedia_lookup"],  # Map dbpedia_lookup to legacy 'dbpedia' key
                "dbpedia_sparql": ["dbpedia_sparql"],
                "wikidata": ["wikidata"],
                "duckduckgo": ["duckduckgo"],
                "openai": ["openai"],
                "anthropic": ["anthropic"]
            }

            # Add mapping for primary key
            mapping_entry = {
                "upstream": config.upstream_url,
                "enabled_keys": legacy_keys.get(source_name, [source_name])
            }
            domain_mappings[source_name] = mapping_entry

            # Add mappings for all legacy keys pointing to the same upstream URL
            for legacy_key in legacy_keys.get(source_name, []):
                if legacy_key != source_name:
                    domain_mappings[legacy_key] = mapping_entry
        
        return {
            "server": {
                "host": self.proxy_server.host,
                "port": self.proxy_server.port
            },
            "cache": {
                "database_path": self.proxy_server.database_path,
                "max_cache_response_size": self.proxy_server.default_max_response_size,
                "max_cache_entries": self.proxy_server.max_cache_entries
            },
            "domain_mappings": domain_mappings,
            "throttling": {
                "default_requests_per_hour": self.proxy_server.default_requests_per_hour,
                "progressive_max_delay": self.proxy_server.progressive_max_delay,
                "domain_limits": {
                    "conceptnet": self.reference_sources.conceptnet.rate_limit.requests_per_hour,
                    "dbpedia_lookup": self.reference_sources.dbpedia_lookup.rate_limit.requests_per_hour,
                    "dbpedia_sparql": self.reference_sources.dbpedia_sparql.rate_limit.requests_per_hour,
                    "dbpedia_spotlight": self.reference_sources.dbpedia_spotlight.rate_limit.requests_per_hour,
                    "wikidata": self.reference_sources.wikidata.rate_limit.requests_per_hour,
                    "duckduckgo": self.reference_sources.duckduckgo.rate_limit.requests_per_hour,
                    "openai": self.reference_sources.openai.rate_limit.requests_per_hour,
                    "anthropic": self.reference_sources.anthropic.rate_limit.requests_per_hour
                }
            },
            "security": {
                "require_secure_key": self.security.require_secure_key,
                "log_security_events": self.security.log_security_events
            },
            "logging": {
                "level": self.logging.level.value,
                "enable_console": self.logging.enable_console,
                "enable_file": self.logging.enable_file,
                "file_path": self.logging.file_path,
                "format": self.logging.format,
                "date_format": self.logging.date_format,
                "max_file_size": self.logging.max_file_size,
            }
        }

    # Legacy compatibility properties for gradual migration
    
    @property
    def NLP_MAX_TEXT_LENGTH(self) -> int:
        """Legacy compatibility property"""
        return self.nlp.max_text_length
    
    @property
    def LLM_MODEL_NAME(self) -> str:
        """Legacy compatibility property"""
        return self.llm.model_name
    
    @property
    def LLM_TEMPERATURE(self) -> float:
        """Legacy compatibility property"""
        return self.llm.temperature
    
    @property
    def LLM_MAX_TOKENS(self) -> Optional[int]:
        """Legacy compatibility property"""
        return self.llm.max_tokens
    
    @property
    def LLM_TIMEOUT(self) -> int:
        """Legacy compatibility property"""
        return self.llm.timeout
    
    @property
    def ENABLE_CACHING_PROXY(self) -> Dict[str, bool]:
        """Legacy compatibility property"""
        return {
            "concepcy": (self.reference_sources.conceptnet.enabled and
                        self.reference_sources.conceptnet.use_proxy),
            "spacy_dbpedia_spotlight": (self.reference_sources.dbpedia_spotlight.enabled and
                                      self.reference_sources.dbpedia_spotlight.use_proxy),
            "dbpedia_spotlight": (self.reference_sources.dbpedia_spotlight.enabled and
                                self.reference_sources.dbpedia_spotlight.use_proxy),
            "conceptnet": (self.reference_sources.conceptnet.enabled and
                          self.reference_sources.conceptnet.use_proxy),
            # Map legacy 'dbpedia' to dbpedia_lookup for backward compatibility
            "dbpedia": (self.reference_sources.dbpedia_lookup.enabled and
                       self.reference_sources.dbpedia_lookup.use_proxy),
            "dbpedia_lookup": (self.reference_sources.dbpedia_lookup.enabled and
                              self.reference_sources.dbpedia_lookup.use_proxy),
            "dbpedia_sparql": (self.reference_sources.dbpedia_sparql.enabled and
                              self.reference_sources.dbpedia_sparql.use_proxy),
            "wikidata": (self.reference_sources.wikidata.enabled and
                        self.reference_sources.wikidata.use_proxy),
            "duckduckgo": (self.reference_sources.duckduckgo.enabled and
                          self.reference_sources.duckduckgo.use_proxy),
            "openai": (self.reference_sources.openai.enabled and
                      self.reference_sources.openai.use_proxy),
            "anthropic": (self.reference_sources.anthropic.enabled and
                         self.reference_sources.anthropic.use_proxy)
        }
    
    @property
    def REFERENCE_API_BUDDY_CONFIG(self) -> Dict[str, Any]:
        """Legacy compatibility property"""
        return self.get_reference_api_buddy_config()
    
    @property
    def s2v_config(self) -> Dict[str, Any]:
        """Legacy compatibility property"""
        return {
            "abs_path": os.path.abspath(self.nlp.sense2vec_path)
        }
    
    @property
    def concepcy_config(self) -> Dict[str, Any]:
        """Legacy compatibility property"""
        return {
            "relations_of_interest": self.nlp.concepcy_relations,
            "filter_missing_text": self.nlp.filter_missing_text,
            "filter_edge_weight": self.nlp.edge_weight_filter
        }

    @property
    def reference_sources_dict(self) -> Dict[str, str]:
        """Legacy compatibility property for reference sources URLs"""
        return {
            "dbpedia": self.reference_sources.dbpedia_sparql.upstream_url,  # Map legacy 'dbpedia' to dbpedia_sparql
            "conceptnet": self.reference_sources.conceptnet.upstream_url,
            "wikidata": self.reference_sources.wikidata.upstream_url,
            "dbpedia_spotlight": self.reference_sources.dbpedia_spotlight.upstream_url,
            "schema_org": self.reference_sources.schema_org.upstream_url
        }



class ConfigurationManager:
    """Manages configuration persistence and updates"""

    def __init__(self, config_file: str = "./config.json"):
        self.config_file = config_file
        self.settings: Optional[Settings] = None
        self._lock = threading.Lock()
        print(f"[ConfigurationManager] Loading config from: {self.config_file}")
        self.load()
    
    def load(self) -> Settings:
        """Load configuration from file with defaults and apply environment overrides"""
        try:
            # Load environment variables first
            load_dotenv()

            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)

                # Apply environment variable overrides to config_data
                config_data = self._apply_env_overrides(config_data)
                self.settings = Settings(**config_data)
                print(f"[ConfigurationManager] Config loaded successfully from {self.config_file}")
                print(f"[ConfigurationManager] Server port: {self.settings.server.port}")
                print(f"[ConfigurationManager] Database URL: {self.settings.database.default_url}")
            else:
                print(f"[ConfigurationManager] Config file not found: {self.config_file}, using defaults")
                self.settings = Settings()
                self.save()  # Create default config file
        except Exception as e:
            print(f"Error loading config: {e}")  # Use print to avoid circular dependency
            self.settings = Settings()
        return self.settings

    def _apply_env_overrides(self, config_data: dict) -> dict:
        """Apply environment variable overrides to configuration data"""
        # Environment variables use double underscore for nesting: SECTION__KEY
        # e.g., SERVER__PORT overrides server.port
        env_overrides: Dict[str, Dict[str, Any]] = {}

        # Collect all environment variables that match configuration pattern
        for env_key, env_value in os.environ.items():
            if '__' in env_key:
                parts = env_key.lower().split('__')
                if len(parts) == 2:
                    section, key = parts
                    if section not in env_overrides:
                        env_overrides[section] = {}
                    # Try to convert to appropriate type
                    env_overrides[section][key] = self._convert_env_value(env_value)

        # Apply overrides to config_data
        for section, overrides in env_overrides.items():
            if section in config_data:
                config_data[section].update(overrides)
            else:
                config_data[section] = overrides

        return config_data

    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string value to appropriate type"""
        # Try to parse as JSON first (handles numbers, booleans, etc.)
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            # Return as string if not valid JSON
            return value
    
    def save(self) -> bool:
        """Save current configuration to file"""
        try:
            with self._lock:
                return self._save_locked()
        except Exception as e:
            print(f"Error saving config: {e}")  # Use print to avoid circular dependency
            return False
    
    def _save_locked(self) -> bool:
        """Save configuration to file (assumes lock is already held)"""
        try:
            if self.settings is None:
                return False
            config_dir = os.path.dirname(self.config_file)
            if config_dir:  # Only create directory if there is one
                os.makedirs(config_dir, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.settings.model_dump(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")  # Use print to avoid circular dependency
            return False
    
    def get(self, path: str) -> Any:
        """Get configuration value using dot notation"""
        try:
            value = self.settings
            for part in path.split('.'):
                if hasattr(value, part):
                    value = getattr(value, part)
                elif isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    raise KeyError(f"Configuration path not found: {path}")
            return value
        except Exception as e:
            print(f"Error getting config value {path}: {e}")  # Use print to avoid circular dependency
            raise
    
    def set(self, path: str, value: Any) -> bool:
        """Set configuration value using dot notation"""
        try:
            with self._lock:
                parts = path.split('.')
                obj = self.settings
                
                # Navigate to parent object
                for part in parts[:-1]:
                    if hasattr(obj, part):
                        obj = getattr(obj, part)
                    else:
                        raise KeyError(f"Configuration path not found: {'.'.join(parts[:-1])}")
                
                # Set the final value
                final_key = parts[-1]
                if hasattr(obj, final_key):
                    setattr(obj, final_key, value)
                else:
                    raise KeyError(f"Configuration key not found: {final_key}")
                
                save_success = self._save_locked()
                
                # Trigger notifications if save was successful
                if save_success:
                    try:
                        # Schedule notification for next event loop iteration
                        loop = asyncio.get_event_loop()
                        loop.create_task(notify_configuration_change(path))
                    except RuntimeError:
                        # No event loop available, skip notifications
                        pass
                
                return save_success
        except Exception as e:
            print(f"Error setting config value {path}: {e}")  # Use print to avoid circular dependency
            return False
    
    def get_reference_sources(self) -> Dict[str, Any]:
        """Get all reference source configurations"""
        if self.settings is None:
            return {}
        return self.settings.reference_sources.model_dump()

    async def update_reference_source(self, source_name: str, update_data: Dict[str, Any]):
        """Update a specific reference source configuration"""
        if self.settings is None:
            raise ValueError("Settings not initialized")
        if not hasattr(self.settings.reference_sources, source_name):
            raise ValueError(f"Reference source '{source_name}' not found")
        
        # Update each field in the source configuration
        for key, value in update_data.items():
            path = f"reference_sources.{source_name}.{key}"
            success = self.set(path, value)
            if not success:
                raise ValueError(f"Failed to update {path}")
    
    def validate(self) -> List[str]:
        """Validate current configuration and return errors"""
        errors = []
        try:
            # Re-create settings object to trigger validation
            if self.settings is not None:
                Settings(**self.settings.model_dump())
        except ValidationError as e:
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                errors.append(f"{field}: {error['msg']}")
        return errors


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        # Check for CONFIG_PATH environment variable (useful for testing)
        config_path = os.getenv('CONFIG_PATH', './config.json')
        _config_manager = ConfigurationManager(config_file=config_path)
    return _config_manager


def get_settings() -> Settings:
    """
    Get the global settings instance with environment variable overrides.

    Environment variables can override config.json settings using the format:
    SECTION__KEY (e.g., SERVER__PORT=9999 overrides server.port)
    """
    # Load .env into the environment and apply overrides
    load_dotenv()

    # Return settings from the configuration manager (includes env overrides)
    config_manager = get_config_manager()
    settings = config_manager.settings
    if settings is None:
        raise RuntimeError("Configuration manager settings not initialized")
    return settings


def get_test_settings() -> Settings:
    """
    Get settings instance for testing with dependency injection support.
    
    This function is designed to be overridden in tests using FastAPI's
    dependency injection system (app.dependency_overrides) or pytest fixtures.
    
    By default, it returns the same settings as get_settings(), but tests
    can override this to provide isolated test configurations.
    
    Example usage in tests:
        @pytest.fixture
        def test_settings():
            return create_test_settings(temp_dir, overrides)
            
        app.dependency_overrides[get_test_settings] = lambda: test_settings
        
    Returns:
        Settings instance (can be overridden for testing)
    """
    return get_settings()


class ConfigurationNotifier:
    """Manages configuration change notifications"""
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}
        self.global_listeners: List[Callable] = []
    
    def register_listener(self, path_pattern: str, callback: Callable):
        """Register a listener for specific configuration paths"""
        if path_pattern not in self.listeners:
            self.listeners[path_pattern] = []
        self.listeners[path_pattern].append(callback)
    
    def register_global_listener(self, callback: Callable):
        """Register a listener for all configuration changes"""
        self.global_listeners.append(callback)
    
    async def notify(self, path: str, new_value: Any):
        """Notify listeners of configuration changes"""
        # Notify specific path listeners
        for pattern, callbacks in self.listeners.items():
            if path.startswith(pattern):
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(path, new_value)
                        else:
                            callback(path, new_value)
                    except Exception as e:
                        print(f"Error in config listener for {pattern}: {e}")
        
        # Notify global listeners
        for callback in self.global_listeners:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(path, new_value)
                else:
                    callback(path, new_value)
            except Exception as e:
                print(f"Error in global config listener: {e}")


# Service-specific notification handlers
async def handle_server_config_change(path: str, value: Any):
    """Handle server configuration changes"""
    if path.startswith("server."):
        print(f"Server configuration changed: {path} = {value}")
        # Note: Server restart required for host/port changes


async def handle_database_config_change(path: str, value: Any):
    """Handle database configuration changes"""
    if path.startswith("database."):
        print(f"Database configuration changed: {path} = {value}")
        # Invalidate connection pools if needed


async def handle_nlp_config_change(path: str, value: Any):
    """Handle NLP configuration changes"""
    if path.startswith("nlp."):
        print(f"NLP configuration changed: {path} = {value}")
        # Reload NLP pipeline if needed
        try:
            from nlp.pipeline import invalidate_pipeline
            invalidate_pipeline()
        except ImportError:
            print("NLP pipeline invalidation not available")


async def handle_llm_config_change(path: str, value: Any):
    """Handle LLM configuration changes"""
    if path.startswith("llm."):
        print(f"LLM configuration changed: {path} = {value}")
        # Clear LLM service cache if needed


async def handle_reference_source_config_change(path: str, value: Any):
    """Handle reference source configuration changes"""
    if path.startswith("reference_sources."):
        print(f"Reference source configuration changed: {path} = {value}")
        # Extract source name from path
        parts = path.split('.')
        if len(parts) >= 2:
            source_name = parts[1]
            field = parts[2] if len(parts) > 2 else None
            
            # Invalidate NLP pipeline if NLP-related sources change
            if source_name in ["conceptnet", "dbpedia_spotlight"] and field in ["enabled", "use_proxy", "upstream_url"]:
                try:
                    from nlp.pipeline import invalidate_pipeline
                    invalidate_pipeline()
                except ImportError:
                    print("NLP pipeline invalidation not available")


async def handle_proxy_config_change(path: str, value: Any):
    """Handle proxy server configuration changes"""
    if path.startswith("proxy_server."):
        print(f"Proxy server configuration changed: {path} = {value}")
        # Restart proxy if needed


# Global notifier instance
_config_notifier = ConfigurationNotifier()

# Register notification handlers
_config_notifier.register_listener("server.", handle_server_config_change)
_config_notifier.register_listener("database.", handle_database_config_change)
_config_notifier.register_listener("nlp.", handle_nlp_config_change)
_config_notifier.register_listener("llm.", handle_llm_config_change)
_config_notifier.register_listener("reference_sources.", handle_reference_source_config_change)
_config_notifier.register_listener("proxy_server.", handle_proxy_config_change)


async def notify_configuration_change(path: str):
    """Notify relevant services of configuration changes"""
    config_manager = get_config_manager()
    new_value = config_manager.get(path)
    await _config_notifier.notify(path, new_value)


async def notify_global_configuration_reload():
    """Notify all services of configuration reload"""
    print("Configuration reloaded - notifying all services")
    # This could trigger a full system refresh if needed


def get_config_notifier() -> ConfigurationNotifier:
    """Get the global configuration notifier instance"""
    return _config_notifier
