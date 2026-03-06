"""
DuckDB persistence adapter for Context Studio.

This package implements analytical query adapters using DuckDB for
high-performance graph analysis and semantic search over distributed
SQLite databases.

DuckDB adapters are used for:
- GraphEngine: Path finding, subgraph extraction, transitive closure analysis
- SemanticQueryEngine: Vector similarity search over embeddings

The DuckDB adapter reads from SQLite databases (local.db, reference.db)
using DuckDB's SQLite extension but does not write to them. DuckDB is
used exclusively for read-only analytical workloads.

Per rearchitecture/architecture_design.md §5.2, this adapter is introduced
in Phase 0 as an empty skeleton. Implementation begins in Phase 2.
"""
