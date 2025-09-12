"""DBpedia source implementation"""


from .base import BaseReferenceSource
from config import get_settings
from ..models import DBpediaResourceResponse, DBpediaSearchResponse, DBpediaSparqlResponse


class DBpediaSource(BaseReferenceSource):
    def _get_default_base_url(self) -> str:
        settings = get_settings()
        return settings.reference_sources.get("dbpedia", "http://dbpedia.org")

    def _get_proxy_domain_key(self) -> str:
        return "dbpedia"

    async def get_resource_data(self, resource_url: str, format: str = "json") -> DBpediaResourceResponse:
        try:
            # Extract resource path from URL - handle different base URLs
            resource_path = resource_url
            for prefix in ["http://dbpedia.org/resource/", "https://dbpedia.org/resource/"]:
                if resource_path.startswith(prefix):
                    resource_path = resource_path[len(prefix):]
                    break
            
            # If no prefix matched, try to extract from any URL containing /resource/
            if resource_path == resource_url and "/resource/" in resource_url:
                resource_path = resource_url.split("/resource/", 1)[1]
            
            data_url = f"{self._get_base_url()}/data/{resource_path}.{format}"

            response_data = await self._make_request("GET", data_url)

            return DBpediaResourceResponse(
                **self._create_base_response(),
                resource_uri=resource_url,
                data_url=data_url,
                data=response_data,
            )

        except Exception as e:
            return DBpediaResourceResponse(**self._create_base_response(success=False, error=str(e)))

    async def search(self, query: str, limit: int = 10, offset: int = 0, format: str = "json") -> DBpediaSearchResponse:
        try:
            search_url = f"{self._get_base_url()}/search.json"
            params = {"q": query, "maxResults": limit, "start": offset, "format": format}

            response_data = await self._make_request("GET", search_url, params=params)

            results = []
            if isinstance(response_data, dict) and "results" in response_data:
                for item in response_data.get("results", []):
                    results.append({
                        "uri": item.get("uri", ""),
                        "label": item.get("label", ""),
                        "description": item.get("description"),
                        "score": float(item.get("score", 0.0)),
                        "types": item.get("types", []),
                    })

            return DBpediaSearchResponse(**self._create_base_response(), query=query, total_results=response_data.get("totalResults", len(results)), results=results)

        except Exception as e:
            return DBpediaSearchResponse(**self._create_base_response(success=False, error=str(e)))

    async def sparql_query(self, query: str, format: str = "json") -> DBpediaSparqlResponse:
        try:
            sparql_url = f"{self._get_base_url()}/sparql"
            headers = {"Accept": "application/json" if format == "json" else "application/xml"}
            data = {"query": query, "format": format}

            response_data = await self._make_request("POST", sparql_url, data=data, headers=headers)

            return DBpediaSparqlResponse(**self._create_base_response(), results=response_data)

        except Exception as e:
            return DBpediaSparqlResponse(**self._create_base_response(success=False, error=str(e)))
