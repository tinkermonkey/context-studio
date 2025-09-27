# LLM Model Capabilities and Structured Output Guide

This guide explains the new LLM model capabilities system and structured output parsing features added to Context Studio.

## Overview

Context Studio now provides:
- **Automatic model capability detection** for LLM configuration validation
- **Structured output parsing** using Pydantic models and LangChain
- **API endpoints** for UX to understand model capabilities and constraints
- **Graceful fallback** when advanced features aren't available

## Model Capabilities System

### What Are Model Capabilities?

Different LLM models support different parameters and features. For example:
- OpenAI models don't support `top_k` parameter
- Anthropic models don't support `frequency_penalty` or `presence_penalty`
- Only newer models support structured output via JSON schema

The capabilities system automatically handles these differences.

### API Endpoints for UX

#### List All Supported Models
```http
GET /api/model-capabilities
```

**Response:**
```json
{
  "models": [
    {
      "model_name": "gpt-4",
      "capabilities": {
        "supports_temperature": true,
        "supports_top_p": true,
        "supports_top_k": false,
        "supports_max_tokens": true,
        "supports_frequency_penalty": true,
        "supports_presence_penalty": true,
        "supports_structured_output": true,
        "supports_function_calling": true,
        "supports_streaming": true,
        "max_tokens_limit": 4096,
        "context_window": 8192,
        "provider": "openai",
        "model_family": "gpt-4"
      }
    }
  ],
  "total_count": 8
}
```

#### Get Capabilities for Specific Model
```http
GET /api/model-capabilities/gpt-3.5-turbo
```

#### Filter by Provider
```http
GET /api/model-capabilities?provider=openai
GET /api/model-capabilities/providers/anthropic
```

### UX Integration Guidelines

#### 1. Dynamic Form Fields

Use the capabilities data to show/hide configuration options:

```typescript
// Example: Only show top_k slider if model supports it
const modelCapabilities = await getModelCapabilities(selectedModel);

return (
  <div>
    <TemperatureSlider /> {/* Always available */}

    {modelCapabilities.supports_top_k && (
      <TopKSlider />
    )}

    {modelCapabilities.supports_frequency_penalty && (
      <FrequencyPenaltySlider />
    )}

    <MaxTokensSlider
      max={modelCapabilities.max_tokens_limit || 4096}
    />
  </div>
);
```

#### 2. Model Selection

Group models by provider and show capabilities:

```typescript
const modelsByProvider = {
  openai: models.filter(m => m.capabilities.provider === 'openai'),
  anthropic: models.filter(m => m.capabilities.provider === 'anthropic')
};

// Show badges for key features
<ModelCard model={model}>
  {model.capabilities.supports_structured_output && (
    <Badge>Structured Output</Badge>
  )}
  {model.capabilities.supports_function_calling && (
    <Badge>Function Calling</Badge>
  )}
</ModelCard>
```

#### 3. Validation and Warnings

The backend automatically validates configurations, but UX can provide real-time feedback:

```typescript
const validateConfig = (model: string, config: LLMConfig) => {
  const capabilities = getModelCapabilities(model);
  const warnings = [];

  if (config.top_k && !capabilities.supports_top_k) {
    warnings.push(`${model} doesn't support top_k parameter`);
  }

  if (config.max_tokens > capabilities.max_tokens_limit) {
    warnings.push(`Max tokens will be capped at ${capabilities.max_tokens_limit}`);
  }

  return warnings;
};
```

## Structured Output Parsing

### What Is Structured Output?

Instead of parsing free-form text responses, structured output ensures the LLM returns data in a predefined format using Pydantic models.

### Current Implementation

All pipeline types (`suggest_term_definition`, `suggest_layer_definition`, `suggest_domain_definition`) now return structured output with this format:

```typescript
interface StructuredOutput {
  definition: string;           // Required
  reasoning?: string;           // Optional
  discrepancies?: string;       // Optional
}
```

### API Changes

The `PipelineExecutionResponse` now includes structured data:

```json
{
  "response_content": "Definition: A technical term...\nReasoning: Based on context...",
  "execution_id": "12345",
  "flavor_id": "my-flavor",
  "pipeline_type": "suggest_term_definition",
  "token_usage": { "total_tokens": 150 },
  "structured_output": {
    "definition": "A technical term that describes...",
    "reasoning": "Based on the provided context...",
    "discrepancies": null
  }
}
```

### UX Integration for Structured Output

#### 1. Display Structured Data

```typescript
const response = await executePipeline(request);

// Use structured output when available
if (response.structured_output) {
  return (
    <div>
      <Section title="Definition">
        {response.structured_output.definition}
      </Section>

      {response.structured_output.reasoning && (
        <Section title="Reasoning">
          {response.structured_output.reasoning}
        </Section>
      )}

      {response.structured_output.discrepancies && (
        <Section title="Discrepancies">
          {response.structured_output.discrepancies}
        </Section>
      )}
    </div>
  );
}

// Fallback to raw text
return <div>{response.response_content}</div>;
```

#### 2. Analytics and Tracking

Structured output is automatically stored in the database for analytics:

```sql
-- Query executions with structured output
SELECT
  pipeline_type,
  JSON_EXTRACT(structured_output, '$.definition') as definition_length,
  JSON_EXTRACT(structured_output, '$.reasoning') IS NOT NULL as has_reasoning
FROM pipeline_flavor_executions
WHERE structured_output IS NOT NULL;
```

## Automatic Fallback System

### How It Works

1. **Primary**: LangChain structured output (JSON schema or function calling)
2. **Fallback**: Regex parsing of text response
3. **Final**: Raw text response

### Logging and Monitoring

The system logs structured output success/failure:

```
[DEBUG] Successfully extracted structured output using LangChain for pipeline suggest_term_definition
[WARN] LangChain structured output failed for pipeline suggest_term_definition, falling back to regex parsing
[INFO] Successfully parsed structured output from text for pipeline suggest_term_definition
```

Monitor these logs to understand which models work best with structured output.

## Best Practices for UX

### 1. Progressive Enhancement

Always design for the lowest common denominator (text responses) and enhance when structured output is available.

### 2. Loading States

Show appropriate loading states since structured output may take slightly longer:

```typescript
<LoadingSpinner message={
  modelSupportsStructuredOutput
    ? "Generating structured response..."
    : "Generating response..."
} />
```

### 3. Error Handling

Handle cases where structured output parsing fails:

```typescript
if (response.structured_output?.definition) {
  // Use structured output
} else if (response.response_content) {
  // Parse from text or show raw content
} else {
  // Handle error case
}
```

### 4. User Feedback

Let users know when they're getting enhanced structured output:

```typescript
{response.structured_output && (
  <InfoBadge>
    This response uses enhanced structured output parsing
  </InfoBadge>
)}
```

## Future Extensibility

The system is designed to easily support new structured output formats:

```python
# Add new structured output type
class SummaryOutput(BaseModel):
    summary: str
    key_points: List[str]
    confidence: float

# Add to mapping
PIPELINE_STRUCTURED_OUTPUT_MAPPING = {
    PipelineType.SUGGEST_TERM_DEFINITION: StructuredOutputDefinition,
    PipelineType.SUMMARIZE_CONTENT: SummaryOutput,  # New type
}
```

The UX will automatically adapt to new structured output formats without code changes.

## Troubleshooting

### Common Issues

1. **Model doesn't support structured output**: Check capabilities API, system will automatically fall back
2. **Parameters being filtered**: Check model capabilities and validation warnings
3. **Parsing failures**: Monitor logs for fallback parsing success rates

### Debug Information

- Check `/api/model-capabilities/{model_name}` for current capability data
- Monitor structured output success rates in execution tracking
- Review pipeline execution logs for validation warnings