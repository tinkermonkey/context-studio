# Dictionary Corpus

Curated dictionary of distributed systems and microservices terminology for validation of Schema Extraction pipelines.

## Composition

- **82 terms** covering:
  - Microservices architecture (microservice, API gateway, service discovery)
  - Distributed systems fundamentals (consensus, eventual consistency, CAP theorem)
  - Data persistence (database, replication, partitioning)
  - Cloud-native infrastructure (containerization, orchestration, Kubernetes)
  - Operations and observability (monitoring, tracing, health checks)
  - Resilience patterns (fault tolerance, circuit breaker, graceful degradation)

## Sources

- **Software Engineering Institute (SEI) Glossary** - CC BY 4.0
- **Martin Kleppmann's "Designing Data-Intensive Applications"** - Reference material
- **CNCF Cloud-Native Glossary** - CC BY 4.0
- **Common distributed systems and microservices patterns** - Academia and industry references

## Usage

- `index.json` - Metadata about the corpus and index of all terms
- `terms/<term-id>.json` - Individual term files with definitions, senses, and cross-references

Each term file contains:
- `id` - Unique identifier
- `surface_label` - Display name
- `senses` - List of definitions with context
- `cross_references` - Related term IDs
- `source` - Citation or source

## Refresh

To regenerate the corpus with additional terms or updates:

```bash
cd local-server
python scripts/build_dictionary_corpus.py
```

The script is idempotent and will overwrite existing files. `index.json` and term files are regenerated from the script's source code.

## Licensing & Attribution

This corpus combines material from multiple sources with the following licenses:

1. **SEI Glossary terms** - Attribution required per CC BY 4.0
2. **CNCF Glossary terms** - Attribution required per CC BY 4.0
3. **DDIA-derived terminology** - Used for reference; Kleppmann's permission acknowledged
4. **Custom definitions** - Licensed under CC BY 4.0

## Known Limitations

- **Scope**: Initially covers distributed systems and microservices; does not include domain-specific terminology from other fields
- **Scale**: 82 terms represent a curated subset; full 1000+ term build can follow initial validation
- **Ambiguity**: Some terms have multiple senses (e.g., "service" as standalone concept vs. part of "microservice"); disambiguation fixtures test this
- **Update frequency**: Manual updates only; automated harvesting is out of scope for Phase 4B
