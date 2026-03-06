"""
Metrics collection adapters for Context Studio.

This package contains adapters that implement the MetricsCollector port
defined in domain/admin/ports.py.

The MetricsCollector port defines:
- record_metric(name: str, value: float, tags: dict) -> None: Record a metric
- get_metric(name: str) -> float: Retrieve current metric value
- get_all_metrics() -> dict: Retrieve all metrics

Adapter implementations support:
- In-memory metrics (current)
- Prometheus metrics (via prometheus-client)
- Datadog metrics (via datadog API)
- CloudWatch (AWS)
- Custom time-series database

Per rearchitecture/architecture_design.md §5.11, metrics collection is
part of the admin bounded context for operational visibility. Phase 0
establishes the port; implementation occurs in Phase 2.

Collected metrics include:
- Ontology size (node count, link count, taxonomy count)
- Query performance (latency percentiles)
- Embedding generation time
- LLM API latency and token usage
- Change event backlog
- Sync status (last push/pull, pending changes)
"""
