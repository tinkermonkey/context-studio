"""
SQLAlchemy models for pipeline database.
"""

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, String, Text, TypeDecorator
from sqlalchemy.orm import declarative_base

Base: Any = declarative_base()


class JSONEncodedDict(TypeDecorator):
    """Enables JSON storage by encoding/decoding on the fly."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert dict to JSON string before saving."""
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        """Convert JSON string to dict after loading."""
        if value is None:
            return None
        return json.loads(value)


class LLMPipeline(Base):
    """Model for LLM pipeline configurations."""

    __tablename__ = "llm_pipelines"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    config = Column(JSONEncodedDict)  # JSON configuration

    def __repr__(self):
        return f"<LLMPipeline(id={self.id}, name={self.name})>"
