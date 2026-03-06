"""
Persistence adapters for Context Studio.

This package contains adapters that implement the OntologyRepository,
ChangeRepository, and PipelineRepository ports defined in the domain layer.

Subpackages:
- sqlite: Implements repository ports using SQLite + SQLiteVector
- duckdb: Implements repository ports using DuckDB for analytical queries

Per rearchitecture/architecture_design.md §5, persistence adapters translate
between domain entities and storage-specific representations. The domain
layer never imports from this package.
"""
