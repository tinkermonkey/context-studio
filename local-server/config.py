"""
Configuration settings for the Context Studio Local Server.
"""

import os
import json
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from dotenv import load_dotenv


class LogLevel(str, Enum):
    """Log level options"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


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


class Settings(BaseModel):
    """Centralized configuration settings"""

    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    reference: ReferenceConfig = Field(default_factory=ReferenceConfig)
    sync: Optional[S3Config] = Field(default=None, description="S3 synchronization configuration")


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
            with open(self.config_file, "r") as f:
                config_data = json.load(f)
            self.settings = Settings(**config_data)
        else:
            self.settings = Settings()
            self.save()

        return self.settings

    def save(self) -> bool:
        """Save current configuration to file"""
        try:
            if self.settings is None:
                return False
            config_dir = os.path.dirname(self.config_file)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(self.settings.model_dump(), f, indent=2)
            return True
        except Exception:
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
