"""Wikidata source implementation"""

from typing import Optional, List
from .base import BaseReferenceSource
from config import get_settings
from ..models import WikidataSparqlResponse, WikidataEntityResponse, WikidataSearchResponse, WikidataSearchResult


class WikidataSource(BaseReferenceSource):
    def _get_default_base_url(self) -> str:
        settings = get_settings()
        return settings.reference_sources.get("wikidata", "https://query.wikidata.org")

    def _get_proxy_domain_key(self) -> str:
        return "wikidata"

    async def sparql_query(self, query: str, format: str = "json") -> WikidataSparqlResponse:
        try:
            sparql_url = f"{self._get_base_url()}/sparql"
            headers = {"Accept": "application/json" if format == "json" else "application/xml"}
            # Wikimedia requires a User-Agent identifying the application
            headers.setdefault("User-Agent", "ContextStudio/LocalServer (contact: devnull@example.com)")
            data = {"query": query, "format": format}
            response_data = await self._make_request("POST", sparql_url, data=data, headers=headers)
            return WikidataSparqlResponse(**self._create_base_response(), results=response_data)
        except Exception as e:
            return WikidataSparqlResponse(**self._create_base_response(success=False, error=str(e)))

    async def get_entity_data(self, entity_url: str, properties: Optional[List[str]] = None, format: str = "json") -> WikidataEntityResponse:
        try:
            # Normalize entity id
            if "/wiki/" in entity_url:
                entity_id = entity_url.rstrip('/').split('/')[-1]
            elif "/entity/" in entity_url:
                entity_id = entity_url.rstrip('/').split('/')[-1]
            else:
                entity_id = entity_url

            data_url = f"{self._get_base_url()}/wiki/Special:EntityData/{entity_id}.{format}"
            headers = {"Accept": "application/json" if format == "json" else "application/xml"}
            headers.setdefault("User-Agent", "ContextStudio/LocalServer (contact: devnull@example.com)")
            response_data = await self._make_request("GET", data_url, headers=headers)

            # Optionally filter properties client-side
            if properties and isinstance(response_data, dict) and "entities" in response_data:
                ent = response_data.get("entities", {}).get(entity_id, {})
                if ent and "claims" in ent:
                    filtered = {p: ent["claims"].get(p) for p in properties if p in ent["claims"]}
                    ent_filtered = {"entities": {entity_id: {**ent, "claims": filtered}}}
                    return WikidataEntityResponse(**self._create_base_response(), entity_id=entity_id, entity_url=entity_url, data=ent_filtered)

            return WikidataEntityResponse(**self._create_base_response(), entity_id=entity_id, entity_url=entity_url, data=response_data)
        except Exception as e:
            return WikidataEntityResponse(**self._create_base_response(success=False, error=str(e)))

    async def search(self, query: str, limit: int = 20, offset: int = 0, format: str = "json") -> WikidataSearchResponse:
        """Search Wikidata entities using the wbsearchentities API"""
        try:
            # Use the Wikidata action API for entity search
            # Always use the main Wikidata API, not the query endpoint
            search_url = "https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "format": "json",
                "limit": min(limit, 50),  # Wikidata API has a max limit of 50
                "continue": offset
            }

            headers = {"User-Agent": "ContextStudio/LocalServer (contact: devnull@example.com)"}
            response_data = await self._make_request("GET", search_url, params=params, headers=headers)

            results = []
            if "search" in response_data:
                for item in response_data["search"]:
                    result = WikidataSearchResult(
                        id=item.get("id", ""),
                        label=item.get("label", ""),
                        description=item.get("description", ""),
                        url=item.get("concepturi", "")
                    )
                    results.append(result)

            total_results = len(results)  # Wikidata API doesn't provide total count

            return WikidataSearchResponse(
                **self._create_base_response(),
                query=query,
                total_results=total_results,
                results=results
            )
        except Exception as e:
            return WikidataSearchResponse(
                **self._create_base_response(success=False, error=str(e)),
                query=query,
                total_results=0,
                results=[]
            )
