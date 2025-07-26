"""
Example SPARQL Queries for Context Studio Graph

This file contains example SPARQL queries that demonstrate the capabilities
of the Context Studio graph data model using RDFLib.
"""

# Example queries organized by use case

BASIC_QUERIES = {
    "count_all_entities": """
        PREFIX cs: <http://context-studio.local/vocab/>
        
        SELECT ?type (COUNT(?entity) as ?count) WHERE {
            ?entity a ?type .
            FILTER(?type IN (cs:Layer, cs:Domain, cs:Term))
        }
        GROUP BY ?type
        ORDER BY DESC(?count)
    """,
    
    "list_all_layers": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?layer ?title ?definition WHERE {
            ?layer a cs:Layer ;
                   rdfs:label ?title ;
                   rdfs:comment ?definition .
        }
        ORDER BY ?title
    """,
    
    "list_domains_with_layers": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?domain ?domainTitle ?layer ?layerTitle WHERE {
            ?domain a cs:Domain ;
                   rdfs:label ?domainTitle ;
                   cs:is_a ?layer .
            ?layer a cs:Layer ;
                  rdfs:label ?layerTitle .
        }
        ORDER BY ?layerTitle ?domainTitle
    """
}

HIERARCHY_QUERIES = {
    "find_term_hierarchy": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        SELECT ?child ?parent ?childLabel ?parentLabel WHERE {
            ?child skos:broader ?parent .
            ?child rdfs:label ?childLabel .
            ?parent rdfs:label ?parentLabel .
        }
        ORDER BY ?parentLabel ?childLabel
    """,
    
    "find_terms_in_specific_domain": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX entity: <http://context-studio.local/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?term ?title ?definition WHERE {
            # Replace DOMAIN_ID with actual domain ID
            ?term a cs:Term ;
                  rdfs:label ?title ;
                  rdfs:comment ?definition ;
                  cs:is_a entity:domain/DOMAIN_ID .
        }
        ORDER BY ?title
    """,
    
    "find_root_terms": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        SELECT ?term ?title WHERE {
            ?term a cs:Term ;
                  rdfs:label ?title .
            # Terms that don't have a parent (broader term)
            FILTER NOT EXISTS { ?term skos:broader ?parent }
        }
        ORDER BY ?title
    """,
    
    "find_leaf_terms": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        SELECT ?term ?title WHERE {
            ?term a cs:Term ;
                  rdfs:label ?title .
            # Terms that don't have children (narrower terms)
            FILTER NOT EXISTS { ?child skos:broader ?term }
        }
        ORDER BY ?title
    """
}

SEARCH_QUERIES = {
    "search_terms_by_keyword": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?term ?title ?definition WHERE {
            ?term a cs:Term ;
                  rdfs:label ?title ;
                  rdfs:comment ?definition .
            # Case-insensitive search in title or definition
            FILTER(
                CONTAINS(LCASE(?title), "KEYWORD") || 
                CONTAINS(LCASE(?definition), "KEYWORD")
            )
        }
        ORDER BY ?title
    """,
    
    "find_terms_by_exact_title": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?term ?title ?definition ?domain ?layer WHERE {
            ?term a cs:Term ;
                  rdfs:label ?title ;
                  rdfs:comment ?definition ;
                  cs:is_a ?domain .
            ?domain cs:is_a ?layer .
            FILTER(?title = "EXACT_TITLE")
        }
    """,
    
    "search_across_all_entities": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?entity ?type ?title ?definition WHERE {
            ?entity a ?type ;
                   rdfs:label ?title .
            OPTIONAL { ?entity rdfs:comment ?definition }
            FILTER(?type IN (cs:Layer, cs:Domain, cs:Term))
            FILTER(CONTAINS(LCASE(?title), "KEYWORD"))
        }
        ORDER BY ?type ?title
    """
}

RELATIONSHIP_QUERIES = {
    "find_all_term_relationships": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?source ?predicate ?target ?sourceLabel ?targetLabel WHERE {
            ?source ?predicate ?target .
            ?source a cs:Term ;
                    rdfs:label ?sourceLabel .
            ?target a cs:Term ;
                    rdfs:label ?targetLabel .
            # Exclude standard RDF/RDFS predicates
            FILTER(
                ?predicate != rdf:type && 
                ?predicate != rdfs:label && 
                ?predicate != rdfs:comment &&
                ?predicate != cs:is_a &&
                ?predicate != cs:belongsToLayer
            )
        }
        ORDER BY ?sourceLabel ?predicate ?targetLabel
    """,
    
    "find_relationships_for_term": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX entity: <http://context-studio.local/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?relatedTerm ?relation ?relatedLabel ?direction WHERE {
            VALUES ?targetTerm { entity:term/TERM_ID }
            
            {
                # Outgoing relationships
                ?targetTerm ?relation ?relatedTerm .
                BIND("outgoing" AS ?direction)
            } UNION {
                # Incoming relationships
                ?relatedTerm ?relation ?targetTerm .
                BIND("incoming" AS ?direction)
            }
            
            ?relatedTerm a cs:Term ;
                        rdfs:label ?relatedLabel .
            
            # Exclude standard predicates
            FILTER(
                ?relation != rdf:type && 
                ?relation != rdfs:label && 
                ?relation != rdfs:comment
            )
        }
        ORDER BY ?direction ?relation ?relatedLabel
    """,
    
    "find_terms_with_specific_relationship": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?source ?target ?sourceLabel ?targetLabel WHERE {
            ?source cs:PREDICATE_NAME ?target .
            ?source a cs:Term ;
                    rdfs:label ?sourceLabel .
            ?target a cs:Term ;
                    rdfs:label ?targetLabel .
        }
        ORDER BY ?sourceLabel ?targetLabel
    """
}

ANALYTICS_QUERIES = {
    "most_connected_terms": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?term ?title (COUNT(?relationship) as ?connectionCount) WHERE {
            ?term a cs:Term ;
                  rdfs:label ?title .
            {
                ?term ?relationship ?other .
            } UNION {
                ?other ?relationship ?term .
            }
            FILTER(?relationship != rdf:type && ?relationship != rdfs:label && ?relationship != rdfs:comment)
        }
        GROUP BY ?term ?title
        ORDER BY DESC(?connectionCount)
    """,
    
    "domain_term_counts": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?domain ?domainTitle (COUNT(?term) as ?termCount) WHERE {
            ?domain a cs:Domain ;
                   rdfs:label ?domainTitle .
            ?term a cs:Term ;
                  cs:is_a ?domain .
        }
        GROUP BY ?domain ?domainTitle
        ORDER BY DESC(?termCount)
    """,
    
    "layer_statistics": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?layer ?layerTitle 
               (COUNT(DISTINCT ?domain) as ?domainCount)
               (COUNT(DISTINCT ?term) as ?termCount) WHERE {
            ?layer a cs:Layer ;
                  rdfs:label ?layerTitle .
            ?domain a cs:Domain ;
                   cs:is_a ?layer .
            ?term a cs:Term ;
                  cs:belongsToLayer ?layer .
        }
        GROUP BY ?layer ?layerTitle
        ORDER BY DESC(?termCount)
    """
}

TEMPORAL_QUERIES = {
    "recently_created_entities": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        
        SELECT ?entity ?type ?title ?created WHERE {
            ?entity a ?type ;
                   rdfs:label ?title ;
                   dcterms:created ?created .
            FILTER(?type IN (cs:Layer, cs:Domain, cs:Term))
            # Filter for entities created in the last 30 days
            FILTER(?created > "2025-06-26T00:00:00Z"^^xsd:dateTime)
        }
        ORDER BY DESC(?created)
    """,
    
    "recently_modified_entities": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        
        SELECT ?entity ?type ?title ?modified WHERE {
            ?entity a ?type ;
                   rdfs:label ?title ;
                   dcterms:modified ?modified .
            FILTER(?type IN (cs:Layer, cs:Domain, cs:Term))
            # Filter for entities modified in the last 7 days
            FILTER(?modified > "2025-07-19T00:00:00Z"^^xsd:dateTime)
        }
        ORDER BY DESC(?modified)
    """,
    
    "entity_versions": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?entity ?type ?title ?version WHERE {
            ?entity a ?type ;
                   rdfs:label ?title ;
                   cs:version ?version .
            FILTER(?type IN (cs:Layer, cs:Domain, cs:Term))
        }
        ORDER BY ?type ?title ?version
    """
}

COMPLEX_QUERIES = {
    "terms_with_multiple_parents": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        SELECT ?term ?title (COUNT(?parent) as ?parentCount) WHERE {
            ?term a cs:Term ;
                  rdfs:label ?title ;
                  skos:broader ?parent .
        }
        GROUP BY ?term ?title
        HAVING (COUNT(?parent) > 1)
        ORDER BY DESC(?parentCount)
    """,
    
    "cross_domain_relationships": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?sourceTerm ?targetTerm ?sourceTitle ?targetTitle 
               ?sourceDomain ?targetDomain ?relation WHERE {
            ?sourceTerm ?relation ?targetTerm .
            ?sourceTerm a cs:Term ;
                       rdfs:label ?sourceTitle ;
                       cs:is_a ?sourceDomain .
            ?targetTerm a cs:Term ;
                       rdfs:label ?targetTitle ;
                       cs:is_a ?targetDomain .
            
            # Only show relationships between different domains
            FILTER(?sourceDomain != ?targetDomain)
            FILTER(?relation != rdf:type && ?relation != rdfs:label && ?relation != rdfs:comment)
        }
        ORDER BY ?sourceTitle ?targetTitle
    """,
    
    "deep_hierarchy_paths": """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        SELECT ?descendant ?ancestor ?descendantTitle ?ancestorTitle WHERE {
            # Use property paths to find transitive relationships
            ?descendant skos:broader+ ?ancestor .
            ?descendant a cs:Term ;
                       rdfs:label ?descendantTitle .
            ?ancestor a cs:Term ;
                     rdfs:label ?ancestorTitle .
        }
        ORDER BY ?ancestorTitle ?descendantTitle
    """
}

# Function to get a query by category and name
def get_query(category: str, name: str) -> str:
    """
    Get a specific query by category and name.
    
    Args:
        category: Query category (basic, hierarchy, search, etc.)
        name: Query name within the category
        
    Returns:
        SPARQL query string
    """
    categories = {
        'basic': BASIC_QUERIES,
        'hierarchy': HIERARCHY_QUERIES,
        'search': SEARCH_QUERIES,
        'relationship': RELATIONSHIP_QUERIES,
        'analytics': ANALYTICS_QUERIES,
        'temporal': TEMPORAL_QUERIES,
        'complex': COMPLEX_QUERIES
    }
    
    if category not in categories:
        raise ValueError(f"Unknown category: {category}")
    
    if name not in categories[category]:
        raise ValueError(f"Unknown query '{name}' in category '{category}'")
    
    return categories[category][name]

# Function to list all available queries
def list_queries() -> dict:
    """
    List all available queries organized by category.
    
    Returns:
        Dictionary with categories and their query names
    """
    return {
        'basic': list(BASIC_QUERIES.keys()),
        'hierarchy': list(HIERARCHY_QUERIES.keys()),
        'search': list(SEARCH_QUERIES.keys()),
        'relationship': list(RELATIONSHIP_QUERIES.keys()),
        'analytics': list(ANALYTICS_QUERIES.keys()),
        'temporal': list(TEMPORAL_QUERIES.keys()),
        'complex': list(COMPLEX_QUERIES.keys())
    }

# Function to substitute parameters in queries
def substitute_params(query: str, **params) -> str:
    """
    Substitute parameters in a query template.
    
    Args:
        query: SPARQL query string with placeholders
        **params: Parameter values to substitute
        
    Returns:
        Query string with parameters substituted
    """
    result = query
    for key, value in params.items():
        placeholder = key.upper()
        result = result.replace(placeholder, str(value))
    return result
