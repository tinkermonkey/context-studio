"""
Graph analysis adapters for Context Studio.

This package contains adapters that implement the GraphEngine and
SemanticQueryEngine ports defined in domain/graph/ports.py.

The GraphEngine port defines:
- find_path(source_id: str, target_id: str) -> PathResult: Find shortest path between nodes
- find_subgraph(root_id: str, depth: int) -> KnowledgeGraph: Extract subgraph
- transitive_closure(node_id: str) -> Sequence[str]: Find all reachable nodes
- circular_references(taxonomy_id: str) -> Sequence[tuple[str, str]]: Detect cycles

The SemanticQueryEngine port defines:
- search_by_embedding(query_embedding: np.ndarray, k: int) -> Sequence[str]: Find similar nodes
- semantic_drill_down(query_embedding: np.ndarray, taxonomy_id: str) -> KnowledgeGraph: Find subgraph of similar nodes

Per rearchitecture/architecture_design.md §5.9, the current graph/ directory
contains basic algorithms. DuckDB adapter (adapters/persistence/duckdb/) will
provide high-performance implementations. Phase 0 contains only the skeleton.
"""
