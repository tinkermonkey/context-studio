"""
Pydantic schemas for FastAPI request/response validation.

Schemas are defined per bounded context and handle request parsing and response serialization.
They should never be imported by domain code—they are strictly adapter layer concerns.

Schemas map between:
- HTTP request JSON → Pydantic model → domain entities
- domain entities → Pydantic model → HTTP response JSON

This separation keeps the domain pure and independent of serialization details.
"""
