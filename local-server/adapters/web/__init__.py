"""
Web framework adapters for Context Studio.

This package contains adapters that translate between domain entities and
web request/response models. The web adapter layer includes:

- Request/response schemas: Pydantic models for API validation and serialization
- Dependency injection: FastAPI Depends() wiring domain services to endpoints
- Middleware: CORS, error handling, request logging
- Serializers: JSON encoding for domain types

Per rearchitecture/architecture_design.md §5.12 and ADR-002, Pydantic
validation belongs in the adapter layer, not the domain. Domain entities
use dataclasses. Web schemas (adapters/web/schemas.py) validate incoming
requests and deserialize responses.

The current api/ directory contains FastAPI route handlers. In Phase 2,
those routes will be refactored to use dependency injection to receive
domain services from app.py, replacing direct imports from services/.

Endpoints remain unchanged between Phase 0 and Phase 1+. Phase 0 is
purely structural; no behavior changes.
"""
