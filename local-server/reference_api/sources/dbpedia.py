"""DBpedia source implementation"""


from .base import BaseReferenceSource
from ..models import DBpediaResourceResponse, DBpediaSearchResponse, DBpediaSparqlResponse


class DBpediaSource(BaseReferenceSource):
    """
    DBpedia source implementation with support for multiple service endpoints.
    
    Uses different proxy domain keys for different services:
    - dbpedia_lookup: for search and data retrieval (lookup.dbpedia.org)
    - dbpedia_sparql: for SPARQL queries (dbpedia.org/sparql)
    """
    
    def _get_default_base_url(self) -> str:
        # Default to lookup service
        return "https://lookup.dbpedia.org"

    def _get_proxy_domain_key(self) -> str:
        # Default domain key for lookup operations
        return "dbpedia_lookup"
    
    def _get_sparql_proxy_domain_key(self) -> str:
        # Domain key for SPARQL operations
        return "dbpedia_sparql"

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
            search_url = f"{self._get_base_url()}/api/search"
            params = {"query": query, "maxResults": limit}

            # DBpedia Lookup returns XML by default, but we can request JSON format
            # lookup.dbpedia.org provides English results by default
            params["format"] = "JSON"
            response_data = await self._make_request("GET", search_url, params=params)

            results = []
            # DBpedia Lookup API returns a dict with "docs" key containing a list
            if isinstance(response_data, dict) and "docs" in response_data:
                for item in response_data.get("docs", []):
                    # Parse DBpedia Lookup response format
                    # Labels come with HTML markup like <B>Apple</B>, clean them
                    label = item.get("label", [""])[0] if item.get("label") else ""
                    label = label.replace("<B>", "").replace("</B>", "") if label else ""

                    # Comments contain descriptions
                    description = item.get("comment", [""])[0] if item.get("comment") else ""
                    description = description.replace("<B>", "").replace("</B>", "") if description else ""

                    results.append({
                        "uri": item.get("resource", [""])[0] if item.get("resource") else "",
                        "label": label,
                        "description": description,
                        "score": float(item.get("score", ["1.0"])[0]) if item.get("score") else 1.0,
                        "types": item.get("type", []),
                    })

            return DBpediaSearchResponse(**self._create_base_response(), query=query, total_results=len(results), results=results)

        except Exception as e:
            return DBpediaSearchResponse(**self._create_base_response(success=False, error=str(e)))

    async def sparql_query(self, query: str, format: str = "json") -> DBpediaSparqlResponse:
        try:
            # Use SPARQL-specific proxy configuration
            if getattr(self.config, 'use_proxy', False):
                # Get proxy base URL for SPARQL endpoint
                from nlp.proxy_manager import get_proxy_manager
                proxy_manager = get_proxy_manager()
                if getattr(proxy_manager, 'is_running', False):
                    proxy_config = proxy_manager.get_proxy_config()
                    if proxy_config and 'domain_mappings' in proxy_config:
                        domain_key = self._get_sparql_proxy_domain_key()
                        if domain_key in proxy_config['domain_mappings']:
                            server_config = proxy_config.get('server', {})
                            host = server_config.get('host', '127.0.0.1')
                            port = server_config.get('port', 18080)
                            # Proxy will forward to dbpedia.org/sparql
                            sparql_url = f"http://{host}:{port}/{domain_key}/sparql"
                        else:
                            # Fallback to direct connection
                            sparql_url = "https://dbpedia.org/sparql"
                    else:
                        sparql_url = "https://dbpedia.org/sparql"
                else:
                    sparql_url = "https://dbpedia.org/sparql"
            else:
                # Direct connection to DBpedia SPARQL endpoint
                sparql_url = "https://dbpedia.org/sparql"
            
            headers = {
                "Accept": "application/sparql-results+json" if format == "json" else "application/sparql-results+xml"
            }
            data = {"query": query, "format": format}

            response_data = await self._make_request("POST", sparql_url, data=data, headers=headers)

            return DBpediaSparqlResponse(**self._create_base_response(), results=response_data)

        except Exception as e:
            return DBpediaSparqlResponse(**self._create_base_response(success=False, error=str(e)))
