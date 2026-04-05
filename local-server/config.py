"""
Configuration settings for the Context Studio Local Server.
"""

import os
import json
import logging
from typing import Optional, List
from pydantic import BaseModel, Field, ValidationError, field_validator
from enum import Enum
from dotenv import load_dotenv

# Configure a dedicated logger for config module to avoid circular dependencies
_config_logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log level options"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SyncAdapterType(str, Enum):
    """Sync adapter type options"""

    S3 = "s3"
    DUCKDB = "duckdb"
    NONE = "none"


class ServerConfig(BaseModel):
    """Server configuration section"""

    host: str = Field(default="127.0.0.1", description="Server host address")
    port: int = Field(default=8000, ge=1024, le=65535, description="Server port")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")


class DatabaseConfig(BaseModel):
    """Database configuration section"""

    local_db_path: str = Field(
        default="./local.db", description="Main workspace database path"
    )
    operations_db_path: str = Field(
        default="./operations.db", description="Operations database path"
    )


class LoggingConfig(BaseModel):
    """Logging configuration section"""

    log_level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    max_bytes: int = Field(
        default=10 * 1024 * 1024, description="Max log file size in bytes"
    )
    backup_count: int = Field(default=5, description="Number of backup log files")


class LLMConfig(BaseModel):
    """LLM provider configuration section"""

    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")


class ReferenceConfig(BaseModel):
    """Reference data configuration section"""

    cache_db_path: str = Field(
        default="./reference_api_cache.db", description="Reference API cache database path"
    )
    reference_db_path: str = Field(
        default="./reference.db", description="Reference data database path"
    )


class S3Config(BaseModel):
    """S3 synchronization configuration section"""

    s3_bucket: Optional[str] = Field(default=None, description="S3 bucket name")
    s3_prefix: Optional[str] = Field(default=None, description="S3 key prefix for changes")
    s3_access_key: Optional[str] = Field(default=None, description="AWS access key ID")
    s3_secret_key: Optional[str] = Field(default=None, description="AWS secret access key")
    s3_region: Optional[str] = Field(default="us-east-1", description="AWS region")


class DuckDBConfig(BaseModel):
    """DuckDB synchronization configuration section"""

    output_dir: str = Field(description="Local directory for Parquet files")


class SyncConfig(BaseModel):
    """Synchronization configuration with adapter selection"""

    adapter: SyncAdapterType = Field(default=SyncAdapterType.NONE, description="Sync adapter type: 's3', 'duckdb', or 'none'")
    s3: Optional[S3Config] = Field(default=None, description="S3-specific configuration")
    duckdb: Optional[DuckDBConfig] = Field(default=None, description="DuckDB-specific configuration")

    @field_validator("adapter", mode="before")
    @classmethod
    def validate_adapter(cls, v: str | SyncAdapterType) -> str | SyncAdapterType:
        """Validate adapter type and convert to lowercase for case-insensitive matching"""
        if isinstance(v, str):
            v = v.lower()
        return v


class Settings(BaseModel):
    """Centralized configuration settings"""

    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    reference: ReferenceConfig = Field(default_factory=ReferenceConfig)
    sync: Optional[SyncConfig] = Field(default=None, description="Synchronization configuration")


class ConfigurationManager:
    """Manages configuration loading from config.json"""

    def __init__(self, config_file: str = "./config.json"):
        self.config_file = config_file
        self.settings: Optional[Settings] = None
        self.load()

    def load(self) -> Settings:
        """Load configuration from file with defaults"""
        load_dotenv()

        if os.path.exists(self.config_file) and os.path.getsize(self.config_file) > 0:
            try:
                with open(self.config_file, "r") as f:
                    config_data = json.load(f)
                self.settings = Settings(**config_data)
                _config_logger.info(f"Successfully loaded configuration from {self.config_file}")
            except json.JSONDecodeError as e:
                _config_logger.error(
                    f"Failed to parse {self.config_file}: Invalid JSON at line {e.lineno}, "
                    f"column {e.colno}. {e.msg}. Using default configuration. "
                    f"Fix the file and reload the application."
                )
                self.settings = Settings()
            except ValidationError as e:
                _config_logger.error(
                    f"Configuration validation failed: Invalid values in {self.config_file}. "
                    f"Errors: {e.errors()}. Using default configuration."
                )
                self.settings = Settings()
            except PermissionError as e:
                _config_logger.error(
                    f"Permission denied reading {self.config_file}: {e}. Using default configuration."
                )
                self.settings = Settings()
            except OSError as e:
                _config_logger.error(
                    f"I/O error reading {self.config_file}: {e}. Using default configuration."
                )
                self.settings = Settings()
            except Exception as e:
                _config_logger.error(
                    f"Unexpected error loading configuration from {self.config_file}: {type(e).__name__}: {e}. "
                    f"Using default configuration."
                )
                self.settings = Settings()
        else:
            self.settings = Settings()
            self.save()

        return self.settings

    def save(self) -> bool:
        """Save current configuration to file"""
        if self.settings is None:
            _config_logger.error("Cannot save configuration: settings not initialized")
            return False

        try:
            config_dir = os.path.dirname(self.config_file)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(self.settings.model_dump(), f, indent=2)
            _config_logger.info(f"Successfully saved configuration to {self.config_file}")
            return True
        except PermissionError as e:
            _config_logger.error(f"Permission denied writing to {self.config_file}: {e}")
            return False
        except FileNotFoundError as e:
            _config_logger.error(f"Configuration file path not found: {e}")
            return False
        except OSError as e:
            _config_logger.error(f"I/O error writing to {self.config_file}: {e}")
            return False
        except TypeError as e:
            _config_logger.error(
                f"Failed to serialize configuration: {e}. Configuration contains non-serializable objects."
            )
            return False
        except Exception as e:
            _config_logger.error(
                f"Unexpected error saving configuration to {self.config_file}: {type(e).__name__}: {e}"
            )
            return False

    def get_settings(self) -> Settings:
        """Get the current settings"""
        if self.settings is None:
            raise RuntimeError("Settings not initialized")
        return self.settings


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        config_path = os.getenv("CONFIG_PATH", "./config.json")
        _config_manager = ConfigurationManager(config_file=config_path)
    return _config_manager


def get_settings() -> Settings:
    """Get the global settings instance from configuration manager"""
    config_manager = get_config_manager()
    return config_manager.get_settings()
