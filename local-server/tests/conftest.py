"""Root conftest for test configuration."""


# Note: Pydantic validation errors are handled by FastAPI's default behavior
# which returns 422 (UNPROCESSABLE_ENTITY). No custom patching is needed.
