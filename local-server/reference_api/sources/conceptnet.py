"""ConceptNet source implementation"""

from typing import Optional
from .base import BaseReferenceSource
from config import get_settings
from ..models import ConceptNetQueryResponse, ConceptNetConceptResponse, ConceptNetRelatedResponse


class ConceptNetSource(BaseReferenceSource):
    def _get_default_base_url(self) -> str:
        settings = get_settings()
        return settings.reference_sources.get("conceptnet", "https://api.conceptnet.io")

    def _get_proxy_domain_key(self) -> str:
        return "conceptnet"

    async def query(self, start: Optional[str] = None, end: Optional[str] = None,
                   node: Optional[str] = None, rel: Optional[str] = None,
                   limit: int = 20, offset: int = 0) -> ConceptNetQueryResponse:
        try:
            query_url = f"{self._get_base_url()}/query"
            params = {"limit": limit, "offset": offset}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            if node:
                params["node"] = node
            if rel:
                params["rel"] = rel

            response_data = await self._make_request("GET", query_url, params=params)

            edges = []
            if isinstance(response_data, dict) and "edges" in response_data:
                for edge in response_data.get("edges", []):
                    edges.append({
                        "@id": edge.get("@id", ""),
                        "start": edge.get("start", {}),
                        "rel": edge.get("rel", {}),
                        "end": edge.get("end", {}),
                        "weight": edge.get("weight", 0.0),
                        "sources": edge.get("sources", []),
                    })

            return ConceptNetQueryResponse(**self._create_base_response(), query_params={k: v for k, v in params.items() if k not in ["limit", "offset"]}, edges=edges)
        except Exception as e:
            return ConceptNetQueryResponse(**self._create_base_response(success=False, error=str(e)))

    async def get_concept(self, concept_path: str) -> ConceptNetConceptResponse:
        try:
            if not concept_path.startswith("/"):
                concept_path = "/" + concept_path
            concept_url = f"{self._get_base_url()}{concept_path}"
            response_data = await self._make_request("GET", concept_url)
            return ConceptNetConceptResponse(**self._create_base_response(), concept=concept_path, data=response_data)
        except Exception as e:
            return ConceptNetConceptResponse(**self._create_base_response(success=False, error=str(e)))

    async def get_related(self, concept_path: str, filter: Optional[str] = None, limit: int = 20) -> ConceptNetRelatedResponse:
        try:
            if not concept_path.startswith("/"):
                concept_path = "/" + concept_path
            related_url = f"{self._get_base_url()}/related{concept_path}"
            params = {"limit": limit}
            if filter:
                params["filter"] = filter
            response_data = await self._make_request("GET", related_url, params=params)

            related = []
            if isinstance(response_data, dict) and "related" in response_data:
                for item in response_data.get("related", []):
                    related.append({"@id": item.get("@id", ""), "label": item.get("label", ""), "weight": item.get("weight", 0.0)})

            return ConceptNetRelatedResponse(**self._create_base_response(), concept=concept_path, filter=filter, related=related)
        except Exception as e:
            return ConceptNetRelatedResponse(**self._create_base_response(success=False, error=str(e)))
