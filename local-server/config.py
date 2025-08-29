"""
Configuration settings for the Context Studio Local Server.
"""

import os
from typing import Dict, Any, Optional
from pydantic import BaseSettings, Field, BaseModel
from enum import Enum


class SourceType(str, Enum):
    """Reference API source types for enrichment service"""
    DBPEDIA = "dbpedia"
    CONCEPTNET = "conceptnet"
    WIKIDATA = "wikidata"
    SCHEMA_ORG = "schema_org"


class SourceConfig(BaseModel):
    """Configuration for individual reference API source"""
    enabled: bool = Field(True, description="Whether this source is enabled")
    use_proxy: bool = Field(True, description="Whether to use caching proxy for this source")
    timeout: int = Field(30, ge=1, le=300, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum number of retries")
    base_url: Optional[str] = Field(None, description="Override base URL for source")


class EnrichmentConfig(BaseModel):
    """Overall enrichment service configuration"""
    sources: Dict[SourceType, SourceConfig] = Field(default_factory=dict)
    default_timeout: int = Field(30, ge=1, le=300, description="Default timeout for all sources")
    concurrent_requests: int = Field(5, ge=1, le=20, description="Maximum concurrent requests per source")
    cache_results: bool = Field(True, description="Whether to cache enrichment results")
    cache_ttl: int = Field(3600, ge=60, description="Cache TTL in seconds")
    
    def get_source_config(self, source: SourceType) -> SourceConfig:
        """Get configuration for a specific source with defaults"""
        if source not in self.sources:
            self.sources[source] = SourceConfig()
        return self.sources[source]



class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    """

    # Reference API Source URLs
    reference_sources: Dict[str, str] = Field(default_factory=lambda: {
        "dbpedia": "https://dbpedia.org",
        "conceptnet": "https://api.conceptnet.io",
        "wikidata": "https://query.wikidata.org", 
        "dbpedia_spotlight": "https://api.dbpedia-spotlight.org/en/",
        "schema_org": "https://schema.org"
    }, description="Upstream URLs for reference API sources")

    # NLP Configuration
    NLP_MAX_TEXT_LENGTH: int = Field(default=512, description="Maximum text length for NLP analysis")

    s2v_config: dict = Field(default_factory=lambda: {
        "abs_path": os.path.abspath("./downloads/s2v_reddit_2015_md")
    }, description="Sense2Vec configuration")

    concepcy_config: dict = Field(default_factory=lambda: {
        "relations_of_interest": [
            "RelatedTo",
            "FormOf",
            "IsA",
            "PartOf",
            "HasA",
            "UsedFor",
            "CapableOf",
            "AtLocation",
            "Causes",
            "HasSubevent",
            "HasFirstSubevent",
            "HasLastSubevent",
            "HasPrerequisite",
            "HasProperty",
            "MotivatedByGoal",
            "ObstructedBy",
            "Desires",
            "CreatedBy",
            "Synonym",
            "Antonym",
            "DistinctFrom",
            "DerivedFrom",
            "SymbolOf",
            "DefinedAs",
            "MannerOf",
            "LocatedNear",
            "HasContext",
            "SimilarTo",
            "EtymologicallyRelatedTo",
            "EtymologicallyDerivedFrom",
            "CausesDesire",
            "MadeOf",
            "ReceivesAction",
            "ExternalURL"
        ],
        "filter_missing_text": True,
        "filter_edge_weight": 2
    }, description="ConcepCy configuration")

    # Reference API Buddy Configuration
    ENABLE_CACHING_PROXY: dict = Field(default_factory=lambda: {
        "concepcy": True,
        "spacy_dbpedia_spotlight": True,
        "conceptnet": True,
        "dbpedia": True,
        "wikidata": True  # Now enabled by default
    }, description="Enable caching proxy for reference APIs")

    REFERENCE_API_BUDDY_CONFIG: dict = Field(default_factory=lambda: {
        "server": {
            "host": "127.0.0.1",
            "port": 18080
        },
        "cache": {
            "database_path": "./reference_api_cache.db",
            "max_cache_response_size": 10485760,  # 10MB
            "max_cache_entries": 10000
        },
        "domain_mappings": {},  # Will be populated dynamically from reference_sources
        "throttling": {
            "default_requests_per_hour": 1000,
            "progressive_max_delay": 300,
            "domain_limits": {
                "conceptnet": 3600,
                "dbpedia": 3600,
                "dbpedia_spotlight": 3600,
                "wikidata": 1000  # Lower limit for Wikidata
            }
        },
        "security": {
            "require_secure_key": False,
            "log_security_events": False
        },
        "logging": {
            "level": "INFO",
            "enable_console": False,
            "enable_file": True,
            "file_path": "./logs/reference_api_buddy.log",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "date_format": "%Y-%m-%d %H:%M:%S",
            "max_file_size": 10485760,
            "backup_count": 5
        }
    }, description="Reference API Buddy proxy configuration")

    def get_concepcy_config(self, use_proxy: bool = False) -> dict:
        """Get concepcy configuration with optional proxy URL"""
        config = self.concepcy_config.copy()
        if use_proxy:
            proxy_config = self.REFERENCE_API_BUDDY_CONFIG
            host = proxy_config["server"]["host"]
            port = proxy_config["server"]["port"]
            config["url"] = f"http://{host}:{port}/conceptnet/query?node=/c/{{lang}}/{{word}}&other=/c/{{lang}}"
        return config

    def get_reference_api_buddy_config(self) -> dict:
        """Get complete reference API buddy configuration with domain mappings"""
        config = self.REFERENCE_API_BUDDY_CONFIG.copy()
        
        # Build domain mappings from reference_sources
        config["domain_mappings"] = {
            "conceptnet": {
                "upstream": self.reference_sources["conceptnet"],
                "enabled_keys": ["concepcy", "conceptnet"]
            },
            "dbpedia": {
                "upstream": self.reference_sources["dbpedia"],
                "enabled_keys": ["dbpedia"]
            },
            "dbpedia_spotlight": {
                "upstream": self.reference_sources["dbpedia_spotlight"],
                "enabled_keys": ["spacy_dbpedia_spotlight", "dbpedia_spotlight"]
            },
            "wikidata": {
                "upstream": self.reference_sources["wikidata"],
                "enabled_keys": ["wikidata"]
            }
        }
        
        return config

    # Schema.org Configuration
    SCHEMA_ORG_DB_PATH: str = Field(default="./schemaorg.db", description="Path to schema.org database")
    SCHEMA_ORG_SOURCE_URL: str = Field(
        default="https://schema.org/version/latest/schemaorg-current-https.jsonld",
        description="URL to download schema.org data"
    )
    SCHEMA_ORG_AUTO_INITIALIZE: bool = Field(default=True, description="Auto-initialize schema.org database")
    SCHEMA_ORG_SIMILARITY_THRESHOLD: float = Field(default=0.7, description="Default similarity threshold for searches")

    # Enrichment API Configuration
    ENRICHMENT_CONFIG: Dict[str, Any] = Field(default_factory=lambda: {
        "sources": {
            "dbpedia": {
                "enabled": True,
                "use_proxy": True,
                "timeout": 30,
                "max_retries": 3,
                "base_url": None
            },
            "conceptnet": {
                "enabled": True,
                "use_proxy": True,
                "timeout": 30,
                "max_retries": 3,
                "base_url": None
            },
            "wikidata": {
                "enabled": True,
                "use_proxy": True,  # Now enabled by default
                "timeout": 30,
                "max_retries": 3,
                "base_url": None
            },
            "schema_org": {
                "enabled": True,
                "use_proxy": False,  # Local database, no proxy needed
                "timeout": 10,
                "max_retries": 1,
                "base_url": None
            }
        },
        "default_timeout": 30,
        "concurrent_requests": 5,
        "cache_results": True,
        "cache_ttl": 3600
    }, description="Enrichment API configuration")

    class Config:
        env_file = ".env"
        case_sensitive = True



def get_settings() -> Settings:
    """
    Get the global settings instance.
    """
    return Settings()
