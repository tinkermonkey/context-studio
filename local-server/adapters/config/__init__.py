"""
Configuration adapters for Context Studio.

This package contains adapters that implement the ConfigurationStore port
defined in domain/admin/ports.py.

The ConfigurationStore port defines:
- get(key: str) -> Any: Retrieve configuration value
- set(key: str, value: Any) -> None: Set configuration value
- get_all() -> dict: Retrieve all configuration
- reload() -> None: Reload configuration from source

Adapter implementations support:
- JSON file-based (config.json, current default)
- Environment variables
- Database-backed configuration
- Distributed config (etcd, Consul for multi-instance deployments)

Per rearchitecture/architecture_design.md §5.10 and CLAUDE.md configuration
management notes, the current config.py and config.json are the primary
source. This adapter layer will wrap that implementation to conform to
the domain port contract.

Configuration is read-only at runtime (except in admin endpoints for managing
system settings). All application configuration is read from config.json
during startup. Environment variables (.env) may be used for development
convenience but never override application configuration.
"""
