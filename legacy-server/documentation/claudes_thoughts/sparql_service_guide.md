# SPARQL Service Documentation

## Overview

The Context Studio SPARQL Service provides powerful graph querying capabilities using RDFLib to create an in-memory RDF representation of your SQLite database. This service converts your hierarchical data model (Layers, Domains, Terms, and TermRelationships) into a semantic graph that can be queried using SPARQL.

## Architecture

The service consists of three main components:

1. **SPARQLService**: Core RDF graph building and SPARQL querying
2. **NetworkService**: NetworkX-based graph analytics
3. **GraphService**: Combined interface providing both capabilities

### Data Mapping

Your SQLite data is mapped to RDF as follows:

- **Layers** → `cs:Layer` class
- **Domains** → `cs:Domain` class  
- **Terms** → `cs:Term` class
- **Hierarchical relationships** → Use layer's `primary_predicate` or default `cs:is_a`
- **Term relationships** → Custom predicates based on `TermRelationship.predicate`

### Namespaces

- `cs:` → `http://context-studio.local/vocab/` (Context Studio vocabulary)
- `entity:` → `http://context-studio.local/entity/` (Entity instances)
- Standard namespaces: `rdf:`, `rdfs:`, `skos:`, `dcterms:`, `foaf:`

## Usage Examples

### Basic Service Initialization

```python
from sqlalchemy.orm import Session
from graph_data_model import GraphService

# Initialize with database session
graph_service = GraphService(db_session)

# Get comprehensive statistics
stats = graph_service.get_comprehensive_stats()
print(f"Total RDF triples: {stats['sparql_stats']['total_triples']}")
print(f"Total NetworkX nodes: {stats['network_stats']['total_nodes']}")
```

### SPARQL Queries

#### Count Entities by Type
```python
query = """
PREFIX cs: <http://context-studio.local/vocab/>

SELECT ?type (COUNT(?entity) as ?count) WHERE {
    ?entity a ?type .
    FILTER(?type IN (cs:Layer, cs:Domain, cs:Term))
}
GROUP BY ?type
"""

results = graph_service.sparql_query(query)
for result in results:
    print(f"{result['type']}: {result['count']}")
```

#### Find Terms by Title
```python
# Using the built-in method
terms = graph_service.find_terms_by_title("Patient", exact=False)

# Or using raw SPARQL
query = """
PREFIX cs: <http://context-studio.local/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?term ?title ?definition WHERE {
    ?term a cs:Term ;
          rdfs:label ?title ;
          rdfs:comment ?definition .
    FILTER(CONTAINS(LCASE(?title), "patient"))
}
"""
results = graph_service.sparql_query(query)
```

#### Get Domain Hierarchy
```python
query = """
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
hierarchy = graph_service.sparql_query(query)
```

#### Find Term Relationships
```python
query = """
PREFIX cs: <http://context-studio.local/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?source ?predicate ?target ?sourceLabel ?targetLabel WHERE {
    ?source ?predicate ?target .
    ?source a cs:Term ;
            rdfs:label ?sourceLabel .
    ?target a cs:Term ;
            rdfs:label ?targetLabel .
    FILTER(?predicate != rdf:type && ?predicate != rdfs:label && ?predicate != rdfs:comment)
}
"""
relationships = graph_service.sparql_query(query)
```

### NetworkX Analytics

#### Calculate Node Centrality
```python
# PageRank centrality
pagerank = graph_service.calculate_centrality("pagerank")
top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]

# Betweenness centrality
betweenness = graph_service.calculate_centrality("betweenness")

# Degree centrality
degree = graph_service.calculate_centrality("degree")
```

#### Find Shortest Path
```python
path = graph_service.find_shortest_path(
    source_id="term_id_1",
    target_id="term_id_2",
    source_type="term",
    target_type="term"
)
print(f"Shortest path: {path}")
```

#### Get Node Neighbors
```python
neighbors = graph_service.get_neighbors(
    entity_id="term_id",
    entity_type="term",
    depth=2,
    direction="both"
)
print(f"Neighbors at depth 1: {neighbors.get('depth_1', [])}")
print(f"Neighbors at depth 2: {neighbors.get('depth_2', [])}")
```

#### Detect Communities
```python
communities = graph_service.detect_communities("louvain")
print(f"Found {len(communities)} communities")
for i, community in enumerate(communities[:5]):
    print(f"Community {i+1}: {len(community)} nodes")
```

### Combined Operations

#### Comprehensive Term Analysis
```python
analysis = graph_service.find_related_terms_comprehensive(
    term_id="your_term_id",
    max_depth=2
)

print(f"Semantic relationships: {len(analysis['semantic_relationships'])}")
print(f"Structural neighbors: {analysis['structural_neighbors']}")
print(f"Centrality score: {analysis['centrality_score']}")
```

#### Domain Structure Analysis
```python
domain_analysis = graph_service.analyze_domain_structure("domain_id")
print(f"Terms in domain: {domain_analysis['terms_count']}")
print(f"Domain network info: {domain_analysis['domain_network_info']}")
```

#### Search and Analyze
```python
results = graph_service.search_and_analyze(
    search_term="insurance",
    analysis_depth=1
)

for analyzed_term in results['analyzed_terms']:
    term_info = analyzed_term['term_info']
    analysis = analyzed_term['analysis']
    print(f"Term: {term_info['title']}")
    print(f"Centrality: {analysis['centrality_score']}")
```

## API Endpoints

The service provides REST API endpoints via FastAPI:

### Graph Statistics
- `GET /graph/stats` - Comprehensive graph statistics
- `POST /graph/refresh` - Refresh graphs from database

### SPARQL Operations
- `POST /graph/sparql/query` - Execute SPARQL query
- `GET /graph/sparql/export` - Export RDF in various formats

### Search and Discovery
- `GET /graph/search/terms` - Search terms by title
- `POST /graph/search/analyze` - Search with comprehensive analysis

### Analytics
- `POST /graph/analytics/centrality` - Calculate node centrality
- `GET /graph/analytics/communities` - Detect communities

### Relationships and Paths
- `POST /graph/path/shortest` - Find shortest path between nodes
- `POST /graph/neighbors` - Get node neighbors
- `GET /graph/terms/{id}/related` - Find related terms
- `GET /graph/terms/{id}/hierarchy` - Get term hierarchy

### Domain and Layer Analysis
- `GET /graph/domains/{id}/analyze` - Analyze domain structure
- `GET /graph/domains/hierarchy` - Get domain hierarchy
- `GET /graph/layers/analytics` - Get layer analytics

## Advanced Features

### Property Paths
Use SPARQL property paths for complex relationship queries:

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?descendant ?ancestor WHERE {
    ?descendant skos:broader+ ?ancestor .
}
```

### Temporal Queries
Query based on creation/modification times:

```sparql
PREFIX dcterms: <http://purl.org/dc/terms/>

SELECT ?entity ?created WHERE {
    ?entity dcterms:created ?created .
    FILTER(?created > "2025-07-01T00:00:00Z"^^xsd:dateTime)
}
```

### Cross-Domain Analysis
Find relationships that span multiple domains:

```sparql
SELECT ?sourceTerm ?targetTerm ?relation WHERE {
    ?sourceTerm ?relation ?targetTerm .
    ?sourceTerm cs:is_a ?sourceDomain .
    ?targetTerm cs:is_a ?targetDomain .
    FILTER(?sourceDomain != ?targetDomain)
}
```

## Performance Considerations

1. **Memory Usage**: The entire graph is loaded into memory for fast querying
2. **Refresh Strategy**: Call `refresh()` when data changes significantly
3. **Query Optimization**: Use FILTER and LIMIT to constrain large result sets
4. **Indexing**: NetworkX automatically optimizes for common graph operations

## Example Queries File

See `graph_data_model/sparql_queries.py` for a comprehensive collection of example queries organized by category:

- **Basic**: Entity counts, listings
- **Hierarchy**: Parent-child relationships, root/leaf nodes
- **Search**: Keyword searches, exact matches
- **Relationships**: Term connections, cross-references
- **Analytics**: Connection counts, statistics
- **Temporal**: Recent changes, versioning
- **Complex**: Multi-level hierarchies, cross-domain analysis

## Integration Examples

### With FastAPI
```python
from fastapi import Depends
from graph_data_model import GraphService

@app.get("/custom-analysis")
async def custom_analysis(graph_service: GraphService = Depends(get_graph_service)):
    query = "YOUR_SPARQL_QUERY"
    results = graph_service.sparql_query(query)
    return {"results": results}
```

### With Background Tasks
```python
from fastapi import BackgroundTasks

def refresh_graph_background(graph_service: GraphService):
    graph_service.refresh()

@app.post("/data-update")
async def data_updated(background_tasks: BackgroundTasks):
    background_tasks.add_task(refresh_graph_background, graph_service)
    return {"status": "refresh scheduled"}
```

## Troubleshooting

### Common Issues

1. **Empty Results**: Ensure data exists and graph has been built
2. **Namespace Errors**: Check prefix declarations in queries
3. **Performance**: Use LIMIT for large datasets, optimize FILTERs
4. **Memory**: Monitor memory usage with large datasets

### Debug Queries
```python
# Check graph statistics
stats = graph_service.get_comprehensive_stats()
print(f"Triples: {stats['sparql_stats']['total_triples']}")

# Validate data mapping
query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
sample = graph_service.sparql_query(query)
print("Sample triples:", sample)

# Check namespaces
namespaces = graph_service.sparql_service.graph.namespaces()
print("Available namespaces:", dict(namespaces))
```

This SPARQL service provides a powerful, standards-compliant way to query and analyze your Context Studio graph data using the full expressiveness of SPARQL combined with NetworkX's analytical capabilities.
