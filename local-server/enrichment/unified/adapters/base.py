"""Abstract base class for unified reference source adapters"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import hashlib
from ..models import UnifiedNode, UnifiedLink, ReferenceSource

class ReferenceAdapter(ABC):
    """Abstract base class for reference source adapters"""

    def __init__(self, source_type: ReferenceSource):
        self.source_type = source_type
        self.source = self._get_source_implementation()

    @abstractmethod
    def _get_source_implementation(self):
        """Get the existing source implementation"""
        pass

    @abstractmethod
    async def search_nodes(
        self,
        query: str,
        search_type: str = "title",
        limit: int = 20,
        offset: int = 0
    ) -> List[UnifiedNode]:
        """Search for nodes in the source"""
        pass

    @abstractmethod
    async def get_links(
        self,
        node_id: str,
        direction: str = "both"
    ) -> List[UnifiedLink]:
        """Get links for a node"""
        pass

    @abstractmethod
    def transform_node(self, source_data: Dict) -> UnifiedNode:
        """Transform source-specific node to unified format"""
        pass

    @abstractmethod
    def transform_link(self, source_data: Dict) -> UnifiedLink:
        """Transform source-specific link to unified format"""
        pass

    def _generate_id(self, source_id: str) -> str:
        """Generate unique ID for cross-source deduplication"""
        hash_input = f"{self.source_type.value}:{source_id}"
        return f"{self.source_type.value}:{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"

    def _normalize_query(self, query: str) -> str:
        """Normalize query string for consistent searching"""
        return query.strip().lower()

    def _extract_base_attributes(self, source_data: Dict) -> Dict:
        """Extract common attributes from source data"""
        return {
            "raw_data": source_data,
            "processed_at": source_data.get("retrieved_at") or source_data.get("timestamp")
        }