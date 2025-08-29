"""
Configuration settings for the Context Studio Local Server.
"""

import os
from pydantic import BaseSettings, Field



class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    """

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
        "spacy_dbpedia_spotlight": True
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
        "throttling": {
            "default_requests_per_hour": 1000,
            "progressive_max_delay": 300,
            "domain_limits": {
                "conceptnet": 3600,      # Allow 3600 requests per hour
                "dbpedia_spotlight": 3600 # Allow 3600 requests per hour
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

    # Schema.org Configuration
    SCHEMA_ORG_DB_PATH: str = Field(default="./schemaorg.db", description="Path to schema.org database")
    SCHEMA_ORG_SOURCE_URL: str = Field(
        default="https://schema.org/version/latest/schemaorg-current-https.jsonld",
        description="URL to download schema.org data"
    )
    SCHEMA_ORG_AUTO_INITIALIZE: bool = Field(default=True, description="Auto-initialize schema.org database")
    SCHEMA_ORG_SIMILARITY_THRESHOLD: float = Field(default=0.7, description="Default similarity threshold for searches")

    class Config:
        env_file = ".env"
        case_sensitive = True



def get_settings() -> Settings:
    """
    Get the global settings instance.
    """
    return Settings()
