"""
LLM response cache with prompt hash invalidation.

Caches LLM responses by exact prompt hash (prompt + model + temperature).
Enables deterministic reruns without repeated API calls. Cache is invalidated
when the pipeline config changes.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

from utils.logger import get_logger

_logger = get_logger(__name__)


class PromptCache:
    """
    Prompt-based caching for LLM responses.

    Cache key is computed from:
    - prompt text (system + user prompt)
    - model identifier
    - temperature setting

    Cache directory structure:
    - <cache_dir>/
      - <hash>.json (cached response)
      - manifest.json (metadata about cached entries)
    """

    def __init__(self, cache_dir: str = ".benchmark-cache"):
        """
        Initialize prompt cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.cache_dir / "manifest.json"
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        """Load cache manifest."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path) as f:
                    return json.load(f)
            except Exception as e:
                _logger.warning(f"Failed to load cache manifest: {e}")
                return {"entries": {}}
        return {"entries": {}}

    def _save_manifest(self) -> None:
        """Save cache manifest."""
        with open(self.manifest_path, "w") as f:
            json.dump(self._manifest, f, indent=2)

    def compute_hash(
        self,
        system_prompt: str,
        user_prompt_template: str,
        model: str,
        temperature: float,
    ) -> str:
        """
        Compute cache key from prompt and config.

        Args:
            system_prompt: System prompt text
            user_prompt_template: User prompt template (may contain placeholders)
            model: Model identifier
            temperature: Temperature setting

        Returns:
            SHA256 hash hex string
        """
        cache_input = f"{system_prompt}||{user_prompt_template}||{model}||{temperature}"
        return hashlib.sha256(cache_input.encode()).hexdigest()[:16]

    def get(self, cache_hash: str) -> Optional[dict[str, Any]]:
        """
        Retrieve cached response.

        Args:
            cache_hash: Cache hash key

        Returns:
            Cached response dict or None if not found
        """
        cache_file = self.cache_dir / f"{cache_hash}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached = json.load(f)
            _logger.debug(f"Cache hit for {cache_hash}")
            return cached.get("response")
        except Exception as e:
            _logger.warning(f"Failed to read cache file {cache_file}: {e}")
            return None

    def set(
        self,
        cache_hash: str,
        response: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Store response in cache.

        Args:
            cache_hash: Cache hash key
            response: Response to cache
            metadata: Optional metadata about the cached response
        """
        cache_file = self.cache_dir / f"{cache_hash}.json"

        cached_entry = {
            "hash": cache_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response": response,
            "metadata": metadata or {},
        }

        try:
            with open(cache_file, "w") as f:
                json.dump(cached_entry, f, indent=2)

            # Update manifest
            self._manifest["entries"][cache_hash] = {
                "timestamp": cached_entry["timestamp"],
                "file": str(cache_file),
                "metadata": cached_entry["metadata"],
            }
            self._save_manifest()

            _logger.debug(f"Cached response for {cache_hash}")
        except Exception as e:
            _logger.error(f"Failed to write cache file {cache_file}: {e}")

    def invalidate_config(self, config_hash: str) -> None:
        """
        Invalidate all cache entries for a config.

        Called when pipeline config changes. Removes cache entries associated
        with a specific config hash.

        Args:
            config_hash: Config hash (computed from config JSON)
        """
        manifest = self._manifest.get("entries", {})
        entries_to_remove = [
            h for h, entry in manifest.items()
            if entry.get("metadata", {}).get("config_hash") == config_hash
        ]

        for cache_hash in entries_to_remove:
            cache_file = self.cache_dir / f"{cache_hash}.json"
            try:
                cache_file.unlink()
                del self._manifest["entries"][cache_hash]
                _logger.info(f"Invalidated cache entry {cache_hash}")
            except Exception as e:
                _logger.warning(f"Failed to invalidate {cache_hash}: {e}")

        if entries_to_remove:
            self._save_manifest()

    def clear(self) -> None:
        """Clear all cache entries."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name != "manifest.json":
                    cache_file.unlink()

            self._manifest = {"entries": {}}
            self._save_manifest()
            _logger.info("Cleared all cache entries")
        except Exception as e:
            _logger.error(f"Failed to clear cache: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        manifest = self._manifest.get("entries", {})
        return {
            "total_entries": len(manifest),
            "cache_dir": str(self.cache_dir),
            "entries": manifest,
        }
