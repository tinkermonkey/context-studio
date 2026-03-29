# Project Memory

## Pipeline Management Error Handling

### Exception Strategy
- **Specific exceptions over broad catch**: Use specific exception types (ValueError, RuntimeError, TimeoutError) instead of `except Exception`
- **System errors must propagate**: Don't catch MemoryError, SystemError, KeyboardInterrupt — let them reach monitoring/observability
- **LLM adapter responsibility**: Hard timeouts belong in the adapter layer (OpenAI, Anthropic, OpenRouter), not domain
- **Domain records what happened**: Record whatever the adapter returns; if timeout occurs, adapter raises TimeoutError (caught and recorded as status="timeout")

### Soft Timeout Anti-pattern
- **Never discard successful results**: If LLM completes successfully, record it as success, not timeout
- **Duration is metadata, not control**: Duration can be tracked (for observability) without affecting execution status
- **Trust the adapter layer**: Don't post-hoc timeout-check completed calls; the adapter handles hard timeouts and raises TimeoutError if limit is exceeded

### Schema Design
- **Expose metadata on responses**: Include provider and model fields in API responses so clients can track which provider/model was used (helpful for cost analysis and debugging)

## OpenRouter Integration Pattern
- Follows same structure as OpenAI/Anthropic adapters
- API-compatible with OpenAI (use requests library)
- Optional/future implementation (YAGNI)
- Implementation plan documented in `openrouter_implementation_plan.md`
