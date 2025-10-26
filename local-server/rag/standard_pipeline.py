"""
Standard RAG Pipeline Implementation

This module provides the StandardRAGPipeline which wraps the existing
RAGPipelineService as the default baseline implementation for comparison.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session

from rag.base_pipeline import BaseRAGPipeline
from rag.rag_pipeline_service import RAGPipelineService
from rag.models import RAGExtractionResponse
from utils.logger import get_logger

logger = get_logger(__name__)


class StandardRAGPipeline(BaseRAGPipeline):
    """
    Standard RAG Pipeline - Default baseline implementation.

    This pipeline uses the existing RAGPipelineService with default configurations.
    It serves as the baseline for comparing experimental pipeline variants.

    Configuration Options:
        - llm_flavor_id: LLM pipeline flavor ID (default: "default")
        - kg_top_k: Number of top KG nodes to retrieve (default: 50)
        - kg_vector_threshold: Minimum similarity for KG vector search (default: 0.6)
        - timeout_layer_0: Layer 0 timeout in seconds (default: 0.5)
        - timeout_layer_1: Layer 1 timeout in seconds (default: 30.0)
        - timeout_layer_2: Layer 2 timeout in seconds (default: 0.5)
        - timeout_layer_3: Layer 3 timeout in seconds (default: 30.0)
        - timeout_total: Total pipeline timeout in seconds (default: 120.0)
        - dedup_similarity_threshold: Similarity threshold for deduplication (default: 0.9)
    """

    def __init__(
        self,
        kg_db_session: Session,
        ops_db_session: Session,
        config: Dict[str, Any] = None
    ):
        """
        Initialize Standard RAG Pipeline.

        Args:
            kg_db_session: Database session for knowledge graph (local.db)
            ops_db_session: Database session for operations/observability (operations.db)
            config: Pipeline-specific configuration parameters
        """
        super().__init__(kg_db_session, ops_db_session, config)

        # Extract configuration with defaults
        llm_flavor_id = self.config.get("llm_flavor_id", "default")
        kg_top_k = self.config.get("kg_top_k", 50)
        kg_vector_threshold = self.config.get("kg_vector_threshold", 0.6)
        timeout_layer_0 = self.config.get("timeout_layer_0", RAGPipelineService.DEFAULT_TIMEOUT_LAYER_0)
        timeout_layer_1 = self.config.get("timeout_layer_1", RAGPipelineService.DEFAULT_TIMEOUT_LAYER_1)
        timeout_layer_2 = self.config.get("timeout_layer_2", RAGPipelineService.DEFAULT_TIMEOUT_LAYER_2)
        timeout_layer_3 = self.config.get("timeout_layer_3", RAGPipelineService.DEFAULT_TIMEOUT_LAYER_3)
        timeout_total = self.config.get("timeout_total", RAGPipelineService.DEFAULT_TIMEOUT_TOTAL)
        dedup_similarity_threshold = self.config.get(
            "dedup_similarity_threshold",
            RAGPipelineService.DEFAULT_DEDUP_SIMILARITY_THRESHOLD
        )

        # Initialize the underlying RAGPipelineService
        self.service = RAGPipelineService(
            kg_db_session=kg_db_session,
            ops_db_session=ops_db_session,
            llm_flavor_id=llm_flavor_id,
            kg_top_k=kg_top_k,
            kg_vector_threshold=kg_vector_threshold,
            timeout_layer_0=timeout_layer_0,
            timeout_layer_1=timeout_layer_1,
            timeout_layer_2=timeout_layer_2,
            timeout_layer_3=timeout_layer_3,
            timeout_total=timeout_total,
            dedup_similarity_threshold=dedup_similarity_threshold
        )

        logger.info(f"StandardRAGPipeline initialized with config: {self.get_config()}")

    async def extract_entities(
        self,
        text: str,
        enable_trace: bool = False,
        enable_llm_layer: bool = True
    ) -> RAGExtractionResponse:
        """
        Extract entities from text using the standard RAG pipeline.

        Args:
            text: Input text to analyze and extract entities from
            enable_trace: Enable detailed tracing for observability (default: False)
            enable_llm_layer: Enable Layer 1 LLM extraction (default: True)

        Returns:
            RAGExtractionResponse with extracted entities, metrics, and trace info
        """
        logger.debug(f"StandardRAGPipeline.extract_entities called with text length: {len(text)}")
        return await self.service.extract_entities(
            text=text,
            enable_trace=enable_trace,
            enable_llm_layer=enable_llm_layer
        )

    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration of this pipeline.

        Returns:
            Dictionary containing pipeline configuration for auditing and comparison
        """
        return {
            "pipeline_class": self.__class__.__name__,
            "llm_flavor_id": self.config.get("llm_flavor_id", "default"),
            "kg_top_k": self.config.get("kg_top_k", 50),
            "kg_vector_threshold": self.config.get("kg_vector_threshold", 0.6),
            "timeout_layer_0": self.config.get("timeout_layer_0", RAGPipelineService.DEFAULT_TIMEOUT_LAYER_0),
            "timeout_layer_1": self.config.get("timeout_layer_1", RAGPipelineService.DEFAULT_TIMEOUT_LAYER_1),
            "timeout_layer_2": self.config.get("timeout_layer_2", RAGPipelineService.DEFAULT_TIMEOUT_LAYER_2),
            "timeout_layer_3": self.config.get("timeout_layer_3", RAGPipelineService.DEFAULT_TIMEOUT_LAYER_3),
            "timeout_total": self.config.get("timeout_total", RAGPipelineService.DEFAULT_TIMEOUT_TOTAL),
            "dedup_similarity_threshold": self.config.get(
                "dedup_similarity_threshold",
                RAGPipelineService.DEFAULT_DEDUP_SIMILARITY_THRESHOLD
            )
        }
