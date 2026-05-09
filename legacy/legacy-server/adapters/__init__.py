"""
Adapter layer for Context Studio.

This package contains all infrastructure adapters that implement the port
interfaces defined in the domain layer. Adapters translate between domain
models and external concerns: persistence, LLM APIs, NLP services,
synchronization, and web frameworks.

Per hexagonal architecture (rearchitecture/architecture_design.md §5),
adapters are organized by concern, not by technology choice. Multiple
adapters can implement the same port (e.g., SQLiteOntologyRepository
and PostgresOntologyRepository both implement OntologyRepository).

Adapters depend on the domain layer but the domain layer has zero
dependencies on adapters. The application bootstrap layer (app.py)
wires domain ports to concrete adapter implementations.
"""
