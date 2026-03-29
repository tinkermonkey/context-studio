# OpenRouter LLM Provider Implementation Plan

## Overview

OpenRouter is a unified API gateway that provides access to multiple LLM providers (OpenAI, Anthropic, Cohere, Llama, etc.) through a single endpoint. Adding OpenRouter support to the pipeline management system requires implementing a new adapter that conforms to the existing `LLMProvider` port.

## Implementation Steps

### 1. Create OpenRouter Provider Adapter

**File**: `adapters/llm/openrouter_provider.py`

This adapter will:
- Implement the `LLMProvider` protocol (structural typing via Protocol)
- Use the OpenRouter API client library (Python `requests` or `openrouter` package if available)
- Support routing to any OpenRouter-available model
- Handle API key validation and request formatting

**Key Methods**:
- `complete()` — Execute a completion request via OpenRouter API
- `is_model_available(model)` — Check if a model is available (consult OpenRouter model list)
- `list_available_models()` — Return list of supported models

**Configuration**:
- OpenRouter API key from `config.json` (section: `llm_config.openrouter_api_key`)
- Base URL: `https://openrouter.ai/api/v1`
- Support for model routing: OpenRouter accepts any model in their catalog

### 2. Update Configuration

**File**: `config.py`

Add OpenRouter API key to the `LLMConfig` class:

```python
class LLMConfig(BaseModel):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""  # NEW
```

**File**: `config.json` (sample)

```json
{
  "llm_config": {
    "openai_api_key": "...",
    "anthropic_api_key": "...",
    "openrouter_api_key": "..."
  }
}
```

### 3. Update Provider Router

**File**: `adapters/llm/provider_router.py`

Modify `LLMProviderRouter.__init__()` to instantiate the OpenRouter provider if configured:

```python
if openrouter_api_key:
    try:
        self._providers["openrouter"] = OpenRouterProvider(openrouter_api_key)
        logger.info("OpenRouter provider initialized")
    except Exception as e:
        logger.error(f"Failed to initialize OpenRouter provider: {str(e)}")
```

### 4. OpenRouter API Details

**HTTP Method**: POST
**Endpoint**: `https://openrouter.ai/api/v1/chat/completions`

**Request Format** (same as OpenAI):
```json
{
  "model": "openrouter/auto",  // or specific model
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "..." }
  ],
  "temperature": 0.0,
  "max_tokens": 2000,
  "response_format": { "type": "json_object" }  // optional
}
```

**Response Format** (compatible with OpenAI):
```json
{
  "choices": [
    {
      "message": {
        "content": "..."
      }
    }
  ],
  "usage": {
    "prompt_tokens": N,
    "completion_tokens": N
  }
}
```

### 5. Model Support

OpenRouter provides access to hundreds of models including:
- OpenAI: gpt-4, gpt-4-turbo, gpt-4o, gpt-3.5-turbo, etc.
- Anthropic: claude-opus-4, claude-sonnet-3, etc.
- Meta: llama-2-7b, llama-3-8b, etc.
- Cohere, Mistral, Perplexity, and others

The adapter should:
- Fetch available models from OpenRouter API on initialization (optional, for validation)
- Allow any model identifier that OpenRouter recognizes
- Default to `openrouter/auto` for unrestricted model selection (lowest-cost available)

### 6. Error Handling

Handle OpenRouter-specific errors:
- **Invalid API Key**: 401 Unauthorized → log warning, mark provider unavailable
- **Model Not Found**: 404 Not Found → return ValueError with model name
- **Rate Limiting**: 429 Too Many Requests → propagate TimeoutError
- **Provider Outage**: 5xx → propagate RuntimeError

### 7. Testing

**Unit Tests** (`tests/unit/adapters/test_openrouter_provider.py`):
- Model availability check (mocked API)
- Completion request formatting
- Response parsing
- Error handling for invalid keys and missing models

**Integration Tests** (`tests/integration/adapters/test_openrouter_provider.py`):
- Real API calls (if test API key available)
- End-to-end completion flow

Mark tests with `@pytest.mark.llm` for selective execution.

### 8. Dependencies

Add to `requirements.txt`:
- `requests>=2.31.0` (or use existing requests dependency)
- Optionally: `openrouter>=0.1.0` (if official package becomes available)

The implementation uses `requests` for HTTP calls, which is already a transitive dependency of other packages in the project.

## Impact on Existing Code

- **No breaking changes** to `LLMProvider` protocol
- **Router composition root** updated in `app.py` to wire OpenRouter provider
- **Health endpoint** automatically includes OpenRouter in available models
- **Pipeline execution** transparent to OpenRouter — no changes to pipeline service

## Future Enhancements

1. **Cost Optimization**: Track token usage per provider and route based on cost
2. **Fallback Strategy**: If primary provider unavailable, retry with OpenRouter
3. **Provider-Specific Features**: Support provider-specific parameters via `config` dict
4. **Usage Analytics**: Log provider/model usage for cost tracking

## References

- OpenRouter API Docs: https://openrouter.ai/docs
- OpenRouter Model List: https://openrouter.ai/docs/models
- Protocol-Based Integration: Existing `OpenAIProvider` and `AnthropicProvider` implementations
