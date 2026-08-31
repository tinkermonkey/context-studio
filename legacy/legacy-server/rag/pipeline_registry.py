# mypy: ignore-errors
"""
RAG Pipeline Registry

This module provides a singleton registry for discovering and instantiating
RAG pipeline variants. Pipelines register themselves using a decorator pattern,
allowing for easy discovery and comparison.
"""

import threading
from typing import Any, Optional

from sqlalchemy.orm import Session
from utils.logger import get_logger

from rag.base_pipeline import BaseRAGPipeline

logger = get_logger(__name__)


class PipelineRegistry:
    """
    Singleton registry for RAG pipeline implementations.

    Provides centralized registration and discovery of pipeline variants,
    enabling systematic testing and comparison of different configurations.
    """

    _instance: Optional["PipelineRegistry"] = None
    _lock = threading.Lock()
    _pipelines: dict[str, type[BaseRAGPipeline]] = {}

    def __new__(cls):
        """Ensure singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    logger.info("PipelineRegistry singleton created")
        return cls._instance

    @classmethod
    def register(cls, pipeline_class: type[BaseRAGPipeline]) -> type[BaseRAGPipeline]:
        """
        Register a pipeline class.

        This method can be used as a decorator:

        @PipelineRegistry.register
        class MyCustomPipeline(BaseRAGPipeline):
            ...

        Args:
            pipeline_class: Pipeline class to register

        Returns:
            The registered pipeline class (allows use as decorator)
        """
        pipeline_name = pipeline_class.get_name()

        if pipeline_name in cls._pipelines:
            logger.warning(
                f"Pipeline '{pipeline_name}' is already registered. Overwriting with new implementation."
            )

        cls._pipelines[pipeline_name] = pipeline_class
        logger.info(f"Registered pipeline: {pipeline_name}")

        return pipeline_class

    @classmethod
    def get_pipeline_class(cls, pipeline_name: str) -> type[BaseRAGPipeline] | None:
        """
        Get a pipeline class by name.

        Args:
            pipeline_name: Name of the pipeline class to retrieve

        Returns:
            Pipeline class, or None if not found
        """
        return cls._pipelines.get(pipeline_name)

    @classmethod
    def list_pipelines(cls) -> list[str]:
        """
        List all registered pipeline names.

        Returns:
            List of registered pipeline class names
        """
        return list(cls._pipelines.keys())

    @classmethod
    def get_pipeline_info(cls, pipeline_name: str) -> dict[str, Any] | None:
        """
        Get information about a registered pipeline.

        Args:
            pipeline_name: Name of the pipeline class

        Returns:
            Dictionary with pipeline info (name, description), or None if not found
        """
        pipeline_class = cls._pipelines.get(pipeline_name)
        if not pipeline_class:
            return None

        return {
            "name": pipeline_class.get_name(),
            "description": pipeline_class.get_description(),
            "class": pipeline_class.__name__,
        }

    @classmethod
    def list_all_pipeline_info(cls) -> list[dict[str, Any]]:
        """
        Get information about all registered pipelines.

        Returns:
            List of dictionaries with pipeline info
        """
        return [cls.get_pipeline_info(name) for name in cls.list_pipelines()]

    @classmethod
    def create_pipeline(
        cls,
        pipeline_name: str,
        kg_db_session: Session,
        ops_db_session: Session,
        config: dict[str, Any] | None = None,
    ) -> BaseRAGPipeline | None:
        """
        Create an instance of a registered pipeline.

        Args:
            pipeline_name: Name of the pipeline class to instantiate
            kg_db_session: Database session for knowledge graph (local.db)
            ops_db_session: Database session for operations/observability (operations.db)
            config: Pipeline-specific configuration parameters

        Returns:
            Pipeline instance, or None if pipeline not found
        """
        pipeline_class = cls._pipelines.get(pipeline_name)
        if not pipeline_class:
            logger.error(f"Pipeline '{pipeline_name}' not found in registry")
            return None

        try:
            pipeline_instance = pipeline_class(
                kg_db_session=kg_db_session,
                ops_db_session=ops_db_session,
                config=config,
            )
            logger.info(f"Created pipeline instance: {pipeline_name}")
            return pipeline_instance

        except Exception as e:
            logger.error(
                f"Failed to create pipeline '{pipeline_name}': {e}", exc_info=True
            )
            return None

    @classmethod
    def unregister(cls, pipeline_name: str) -> bool:
        """
        Unregister a pipeline class.

        Args:
            pipeline_name: Name of the pipeline class to unregister

        Returns:
            True if pipeline was unregistered, False if not found
        """
        if pipeline_name in cls._pipelines:
            del cls._pipelines[pipeline_name]
            logger.info(f"Unregistered pipeline: {pipeline_name}")
            return True
        return False

    @classmethod
    def clear(cls):
        """Clear all registered pipelines (useful for testing)."""
        cls._pipelines.clear()
        logger.info("Cleared all pipeline registrations")


# Convenience function for accessing the singleton
def get_pipeline_registry() -> PipelineRegistry:
    """
    Get the global pipeline registry instance.

    Returns:
        PipelineRegistry singleton instance
    """
    return PipelineRegistry()


# Auto-register the standard pipeline
def _register_default_pipelines():
    """Register default pipeline implementations."""
    try:
        from rag.standard_pipeline import StandardRAGPipeline

        PipelineRegistry.register(StandardRAGPipeline)
        logger.info("Default pipelines registered successfully")
    except Exception as e:
        logger.error(f"Failed to register default pipelines: {e}", exc_info=True)


# Register defaults on module import
_register_default_pipelines()
