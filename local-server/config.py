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
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """
    Get the global settings instance.
    """
    return Settings()
