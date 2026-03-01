"""
Adapter Layer - Infrastructure Integration.

This package contains all infrastructure adapters that implement the port
interfaces defined in the domain layer. Adapters integrate with:
- Persistence (SQLite, DuckDB)
- Embedding services
- LLM providers
- NLP processors
- Reference data sources
- Event systems
- Graph databases
- Configuration stores
- Metrics collectors
- Web frameworks

See rearchitecture/architecture_design.md §6 for the complete architecture.
See rearchitecture/port_and_adapter_specs.md for port interface specifications.
"""
