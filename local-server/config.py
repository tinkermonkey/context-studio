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
    default_url: str = Field(default="sqlite:///./local.db", description="Default database URL")
    default_dataset_filename: str = Field(default="default.db", description="Default dataset filename")
    schema_org_path: str = Field(default="./schemaorg.db", description="Schema.org database path")
    reference_path: str = Field(default="./reference.db", description="Reference database path (multi-source knowledge graph)")
    reference_cache_path: str = Field(default="./reference_api_cache.db", description="Reference API cache database path")
    pipeline_path: str = Field(default="./pipeline.db", description="Pipeline database path")
    check_same_thread: bool = Field(default=False, description="SQLite check_same_thread setting")
    pool_timeout: int = Field(default=30, ge=1, description="Database pool timeout seconds")
    

class LLMConfig(BaseModel):
    """Large Language Model configuration section"""
    model_name: str = Field(default="gpt-3.5-turbo", description="OpenAI model name")
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


class ReferenceSourceRateLimitConfig(BaseModel):
    """Rate limiting configuration for a specific reference source"""
    requests_per_hour: int = Field(default=1000, ge=1, description="Requests per hour limit")
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

    # Individual source configurations
    conceptnet: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://api.conceptnet.io",
        rate_limit=ReferenceSourceRateLimitConfig(requests_per_hour=3600)
    ))
    
    dbpedia: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://lookup.dbpedia.org",
        use_proxy=False,  # Temporarily disable proxy for testing
        rate_limit=ReferenceSourceRateLimitConfig(requests_per_hour=3600)
    ))
    
    dbpedia_spotlight: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://api.dbpedia-spotlight.org/en/",
        rate_limit=ReferenceSourceRateLimitConfig(requests_per_hour=3600)
    ))
    
    wikidata: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://query.wikidata.org",
        rate_limit=ReferenceSourceRateLimitConfig(requests_per_hour=1000)  # Lower limit for Wikidata
    ))
    
    schema_org: ReferenceSourceConfig = Field(default_factory=lambda: ReferenceSourceConfig(
        upstream_url="https://schema.org",
        use_proxy=False,  # Local database, no proxy needed
        timeout=10,
        max_retries=1,
        rate_limit=ReferenceSourceRateLimitConfig(requests_per_hour=10000)  # Local, no real limit
    ))


class ProxyServerConfig(BaseModel):
    """Global proxy server configuration"""
    host: str = Field(default="127.0.0.1", description="Proxy server host")
    port: int = Field(default=18080, ge=1024, le=65535, description="Proxy server port")
    enabled: bool = Field(default=True, description="Enable proxy server globally")
    database_path: str = Field(default="./reference_api_cache.db", description="Cache database path")
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


class ReferenceConfig(BaseModel):
    """Overall reference service configuration (legacy compatibility)"""
    sources: Dict[SourceType, SourceConfig] = Field(default_factory=dict)
    default_timeout: int = Field(30, ge=1, le=300, description="Default timeout for all sources")
    concurrent_requests: int = Field(5, ge=1, le=20, description="Maximum concurrent requests per source")
    cache_results: bool = Field(True, description="Whether to cache reference results")
    cache_ttl: int = Field(3600, ge=60, description="Cache TTL in seconds")
    
    def get_source_config(self, source: SourceType) -> SourceConfig:
        """Get configuration for a specific source with defaults"""
        if source not in self.sources:
            self.sources[source] = SourceConfig()
        return self.sources[source]



class Settings(BaseModel):
    """Centralized configuration settings"""

    model_config = ConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Configuration sections
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    nlp: NLPConfig = Field(default_factory=NLPConfig)
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
        """Get configuration for a specific reference source"""
        if hasattr(self.reference_sources, source_name):
            return getattr(self.reference_sources, source_name)
        raise ValueError(f"Unknown reference source: {source_name}")
    
    def get_enabled_sources(self) -> List[str]:
        """Get list of enabled reference sources"""
        enabled = []
        for source_name in ["conceptnet", "dbpedia", "dbpedia_spotlight", "wikidata", "schema_org"]:
            config = getattr(self.reference_sources, source_name)
            if config.enabled:
                enabled.append(source_name)
        return enabled
    
    def get_proxy_enabled_sources(self) -> List[str]:
        """Get list of sources that should use the proxy"""
        proxy_enabled = []
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
                "dbpedia": ["dbpedia"],
                "wikidata": ["wikidata"]
            }
            domain_mappings[source_name] = {
                "upstream": config.upstream_url,
                "enabled_keys": legacy_keys.get(source_name, [source_name])
            }
        
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
                    "dbpedia": self.reference_sources.dbpedia.rate_limit.requests_per_hour,
                    "dbpedia_spotlight": self.reference_sources.dbpedia_spotlight.rate_limit.requests_per_hour,
                    "wikidata": self.reference_sources.wikidata.rate_limit.requests_per_hour
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
    def SCHEMA_ORG_DB_PATH(self) -> str:
        """Legacy compatibility property"""
        return self.database.schema_org_path
    
    @property
    def SCHEMA_ORG_SOURCE_URL(self) -> str:
        """Legacy compatibility property"""
        return "https://schema.org/version/latest/schemaorg-current-https.jsonld"
    
    @property
    def SCHEMA_ORG_AUTO_INITIALIZE(self) -> bool:
        """Legacy compatibility property"""
        return True
    
    @property
    def SCHEMA_ORG_SIMILARITY_THRESHOLD(self) -> float:
        """Legacy compatibility property"""
        return 0.7
    
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
    def REFERENCE_CONFIG(self) -> Dict[str, Any]:
        """Legacy compatibility property"""
        return {
            "sources": {
                "dbpedia": {
                    "enabled": self.reference_sources.dbpedia.enabled,
                    "use_proxy": self.reference_sources.dbpedia.use_proxy,
                    "timeout": self.reference_sources.dbpedia.timeout,
                    "max_retries": self.reference_sources.dbpedia.max_retries,
                    "base_url": None
                },
                "conceptnet": {
                    "enabled": self.reference_sources.conceptnet.enabled,
                    "use_proxy": self.reference_sources.conceptnet.use_proxy,
                    "timeout": self.reference_sources.conceptnet.timeout,
                    "max_retries": self.reference_sources.conceptnet.max_retries,
                    "base_url": None
                },
                "wikidata": {
                    "enabled": self.reference_sources.wikidata.enabled,
                    "use_proxy": self.reference_sources.wikidata.use_proxy,
                    "timeout": self.reference_sources.wikidata.timeout,
                    "max_retries": self.reference_sources.wikidata.max_retries,
                    "base_url": None
                },
                "schema_org": {
                    "enabled": self.reference_sources.schema_org.enabled,
                    "use_proxy": self.reference_sources.schema_org.use_proxy,
                    "timeout": self.reference_sources.schema_org.timeout,
                    "max_retries": self.reference_sources.schema_org.max_retries,
                    "base_url": None
                }
            },
            "default_timeout": 30,
            "concurrent_requests": 5,
            "cache_results": True,
            "cache_ttl": 3600
        }
    
    @property
    def ENABLE_CACHING_PROXY(self) -> Dict[str, bool]:
        """Legacy compatibility property"""
        return {
            "concepcy": (self.reference_sources.conceptnet.enabled and 
                        self.reference_sources.conceptnet.use_proxy),
            "spacy_dbpedia_spotlight": (self.reference_sources.dbpedia_spotlight.enabled and 
                                      self.reference_sources.dbpedia_spotlight.use_proxy),
            "conceptnet": (self.reference_sources.conceptnet.enabled and 
                          self.reference_sources.conceptnet.use_proxy),
            "dbpedia": (self.reference_sources.dbpedia.enabled and 
                       self.reference_sources.dbpedia.use_proxy),
            "wikidata": (self.reference_sources.wikidata.enabled and 
                        self.reference_sources.wikidata.use_proxy)
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
            "dbpedia": self.reference_sources.dbpedia.upstream_url,
            "conceptnet": self.reference_sources.conceptnet.upstream_url,
            "wikidata": self.reference_sources.wikidata.upstream_url,
            "dbpedia_spotlight": self.reference_sources.dbpedia_spotlight.upstream_url,
            "schema_org": self.reference_sources.schema_org.upstream_url
        }



class ConfigurationManager:
    """Manages configuration persistence and updates"""
    
    def __init__(self, config_file: str = "./config.json"):
        self.config_file = config_file
        self.settings = None
        self._lock = threading.Lock()
        self.load()
    
    def load(self) -> Settings:
        """Load configuration from file with defaults"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                self.settings = Settings(**config_data)
            else:
                self.settings = Settings()
                self.save()  # Create default config file
        except Exception as e:
            print(f"Error loading config: {e}")  # Use print to avoid circular dependency
            self.settings = Settings()
        return self.settings
    
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
        return self.settings.reference_sources.model_dump()
    
    async def update_reference_source(self, source_name: str, update_data: Dict[str, Any]):
        """Update a specific reference source configuration"""
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
        _config_manager = ConfigurationManager()
    return _config_manager


def get_settings() -> Settings:
    """
    Get the global settings instance.
    """
    # Load .env into the environment so callers can override settings using
    # standard environment variables. This does not perform automatic mapping
    # of environment variables to nested fields like BaseSettings would.
    load_dotenv()

    # Return settings from the configuration manager
    config_manager = get_config_manager()
    return config_manager.settings


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
