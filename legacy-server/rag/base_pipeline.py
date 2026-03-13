"""
Base RAG Pipeline Interface

This module defines the abstract base class for all RAG pipeline variants.
All pipeline implementations must inherit from BaseRAGPipeline and implement
the standard interface for entity extraction.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from rag.models import RAGExtractionResponse
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseRAGPipeline(ABC):
    """
    Abstract base class for RAG pipeline implementations.

    All pipeline variants must implement this interface to ensure consistent
    behavior across different pipeline configurations and allow for
    systematic testing and comparison.
    """

    def __init__(
        self,
        kg_db_session: Session,
        ops_db_session: Session,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the RAG pipeline.

        Args:
            kg_db_session: Database session for knowledge graph (local.db)
            ops_db_session: Database session for operations/observability (operations.db)
            config: Pipeline-specific configuration parameters
        """
        self.kg_db_session = kg_db_session
        self.ops_db_session = ops_db_session
        self.config = config or {}
        logger.info(f"Initialized {self.__class__.__name__} with config: {self.config}")

    @abstractmethod
    async def extract_entities(
        self, text: str, enable_trace: bool = False, enable_llm_layer: bool = True
    ) -> RAGExtractionResponse:
        """
        Extract entities from text using this pipeline variant.

        Args:
            text: Input text to analyze and extract entities from
            enable_trace: Enable detailed tracing for observability (default: False)
            enable_llm_layer: Enable Layer 1 LLM extraction (default: True)

        Returns:
            RAGExtractionResponse with extracted entities, metrics, and trace info
        """
        pass

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration of this pipeline.

        Returns:
            Dictionary containing pipeline configuration for auditing and comparison
        """
        pass

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of this pipeline class.

        Returns:
            Pipeline class name
        """
        return cls.__name__

    @classmethod
    def get_description(cls) -> str:
        """
        Get a human-readable description of this pipeline variant.

        Returns:
            Description of the pipeline's purpose and characteristics
        """
        return cls.__doc__ or f"{cls.__name__} - No description available"
