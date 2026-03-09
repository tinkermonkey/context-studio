"""
OpenRouter model discovery service.

This module fetches available models from OpenRouter's API and converts them
to our internal ModelCapabilities format for dynamic model registry updates.
"""

import requests
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re

from .model_capabilities import ModelCapabilities
from utils.logger import get_logger

logger = get_logger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


@dataclass
class OpenRouterModel:
    """OpenRouter model information"""

    id: str
    name: str
    description: str
    context_length: int
    pricing: Dict[str, Any]
    architecture: Dict[str, Any]


class OpenRouterDiscoveryService:
    """Service for discovering and converting OpenRouter models"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.logger = logger

    async def fetch_available_models(self) -> List[OpenRouterModel]:
        """Fetch available models from OpenRouter API"""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self.logger.info("Fetching available models from OpenRouter...")

            # Use asyncio to make the request non-blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    OPENROUTER_MODELS_URL, headers=headers, timeout=10
                ),
            )

            if response.status_code != 200:
                self.logger.error(
                    f"OpenRouter API returned status {response.status_code}"
                )
                return []

            data = response.json()
            models = []

            for model_data in data.get("data", []):
                try:
                    model = OpenRouterModel(
                        id=model_data.get("id", ""),
                        name=model_data.get("name", ""),
                        description=model_data.get("description", ""),
                        context_length=model_data.get("context_length", 0),
                        pricing=model_data.get("pricing", {}),
                        architecture=model_data.get("architecture", {}),
                    )
                    models.append(model)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse model {model_data.get('id', 'unknown')}: {e}"
                    )

            self.logger.info(
                f"Successfully fetched {len(models)} models from OpenRouter"
            )
            return models

        except Exception as e:
            self.logger.error(f"Failed to fetch models from OpenRouter: {e}")
            return []

    def convert_to_model_capabilities(
        self, openrouter_models: List[OpenRouterModel]
    ) -> Dict[str, ModelCapabilities]:
        """Convert OpenRouter models to our ModelCapabilities format"""
        capabilities_map = {}

        for model in openrouter_models:
            try:
                # Parse provider from model ID (e.g., "anthropic/claude-3-opus" -> "anthropic")
                provider = self._extract_provider(model.id)
                clean_model_name = self._clean_model_name(model.id)

                # Determine capabilities based on provider and model info
                capabilities = self._infer_capabilities(model, provider)

                capabilities_map[clean_model_name] = capabilities

            except Exception as e:
                self.logger.warning(f"Failed to convert model {model.id}: {e}")

        return capabilities_map

    def _extract_provider(self, model_id: str) -> str:
        """Extract provider from OpenRouter model ID"""
        if "/" in model_id:
            return model_id.split("/")[0]
        return "openrouter"

    def _extract_model_family(self, model_id: str) -> str:
        """Extract model family from OpenRouter model ID"""
        # Examples: "anthropic/claude-3-opus" -> "claude-3"
        #          "openai/gpt-4-turbo" -> "gpt-4"
        clean_name = model_id.split("/")[-1] if "/" in model_id else model_id

        # Common patterns
        if "claude-4" in clean_name:
            return "claude-4"
        elif "claude-3" in clean_name:
            return "claude-3"
        elif "gpt-5" in clean_name:
            return "gpt-5"
        elif "gpt-4o" in clean_name:
            return "gpt-4o"
        elif "gpt-4" in clean_name:
            return "gpt-4"
        elif "gpt-3.5" in clean_name:
            return "gpt-3.5"
        else:
            return "unknown"

    def _clean_model_name(self, model_id: str) -> str:
        """Clean model name for our registry"""
        # Convert "anthropic/claude-3-opus" to "claude-3-opus"
        # Convert "openai/gpt-4-turbo" to "gpt-4-turbo"
        clean_name = model_id.split("/")[-1] if "/" in model_id else model_id

        # Remove common suffixes that might cause issues
        clean_name = re.sub(r"-\d{8}$", "", clean_name)  # Remove date suffixes
        clean_name = re.sub(r"@\w+$", "", clean_name)  # Remove version tags

        return clean_name

    def _infer_capabilities(
        self, model: OpenRouterModel, provider: str
    ) -> ModelCapabilities:
        """Infer model capabilities based on provider and model info"""
        # Base capabilities
        capabilities = ModelCapabilities(
            context_window=model.context_length,
            provider=provider,
            model_family=self._extract_model_family(model.id),
        )

        # Provider-specific adjustments
        if provider == "openai":
            capabilities.supports_top_k = False
            capabilities.supports_frequency_penalty = True
            capabilities.supports_presence_penalty = True

        elif provider == "anthropic":
            capabilities.supports_top_k = True
            capabilities.supports_frequency_penalty = False
            capabilities.supports_presence_penalty = False

            # Claude-4 models have enhanced capabilities
            if "claude-4" in model.id:
                capabilities.supports_structured_output = True
                capabilities.max_tokens_limit = 8192
                if "opus" in model.id:
                    capabilities.max_tokens_limit = 16384

        elif provider == "google":
            capabilities.supports_top_k = True
            capabilities.supports_top_p = True

        # Infer token limits based on model name and context
        if not capabilities.max_tokens_limit:
            if "mini" in model.id.lower():
                capabilities.max_tokens_limit = 2048
            elif model.context_length > 100000:
                capabilities.max_tokens_limit = 8192
            else:
                capabilities.max_tokens_limit = 4096

        return capabilities

    async def get_dynamic_model_registry(self) -> Dict[str, ModelCapabilities]:
        """Get a dynamic model registry from OpenRouter"""
        try:
            models = await self.fetch_available_models()
            if not models:
                self.logger.warning(
                    "No models fetched from OpenRouter, using empty registry"
                )
                return {}

            capabilities_map = self.convert_to_model_capabilities(models)
            self.logger.info(
                f"Generated capabilities for {len(capabilities_map)} OpenRouter models"
            )

            return capabilities_map

        except Exception as e:
            self.logger.error(f"Failed to generate dynamic model registry: {e}")
            return {}

    def filter_models(
        self, models: List[OpenRouterModel], criteria: Dict[str, Any]
    ) -> List[OpenRouterModel]:
        """Filter models based on criteria"""
        filtered = []

        for model in models:
            # Filter by provider
            if "provider" in criteria:
                provider = self._extract_provider(model.id)
                if provider not in criteria["provider"]:
                    continue

            # Filter by minimum context length
            if "min_context" in criteria:
                if model.context_length < criteria["min_context"]:
                    continue

            # Filter by model family
            if "model_family" in criteria:
                family = self._extract_model_family(model.id)
                if family not in criteria["model_family"]:
                    continue

            filtered.append(model)

        return filtered


# Global instance
_discovery_service = None


def get_openrouter_discovery_service(
    api_key: Optional[str] = None,
) -> OpenRouterDiscoveryService:
    """Get the global OpenRouter discovery service instance"""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = OpenRouterDiscoveryService(api_key)
    return _discovery_service
