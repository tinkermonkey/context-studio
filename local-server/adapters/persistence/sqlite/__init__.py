"""
SQLite persistence adapter for Context Studio.

This package implements the OntologyRepository, ChangeRepository, and
PipelineRepository port interfaces using SQLite + SQLiteVector.

The current schema (structure_nodes, structure_node_links, predicates,
change_events, pipeline_flavors, pipeline_flavor_executions) remains
unchanged during Phase 0. This adapter translates between ORM models
(database/models.py) and domain entities (domain/ontology/entities.py, etc.).

Key adapters:
- SQLiteOntologyRepository: Maps structure_nodes table to Taxonomy, ConceptScheme,
  Class, Individual entities based on node_type discriminator
- SQLiteChangeRepository: Maps change_events table to ChangeEvent domain entities
- SQLitePipelineRepository: Maps pipeline_flavors table to PipelineConfiguration domain entities

Per rearchitecture/architecture_design.md §5.1 and ADR-003, the unified table
with adapter mapping is chosen for Phase 0 to minimize database migration
complexity while maintaining a fully typed domain model.
"""
