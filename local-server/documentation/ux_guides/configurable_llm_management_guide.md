# Configurable LLM Management System Guide

This guide explains the new configurable LLM management system that allows users to dynamically enable/disable models and route them through different providers.

## Overview

The system separates two concerns:

1. **Static Model Capabilities** (`llm/model_capabilities.py`) - Technical specifications of what each model can do
2. **Dynamic Enabled Models** (`enabled_models.json`) - User's configuration of which models to use and how to route them

## Provider Types

The system supports four provider routing types:

- **`native_openai`** - Direct LangChain → OpenAI API
- **`native_anthropic`** - Direct LangChain → Anthropic API
- **`native_google`** - Direct LangChain → Google Gemini API
- **`openrouter`** - Route through OpenRouter for any model

## Configuration File Structure

Models are configured in `enabled_models.json`:

```json
{
  "models": {
    "gpt-3.5-turbo": {
      "model_name": "gpt-3.5-turbo",
      "provider_type": "native_openai",
      "display_name": "GPT-3.5 Turbo",
      "enabled": true,
      "api_key_env_var": "OPENAI_API_KEY",
      "custom_endpoint": null,
      "model_override": null,
      "description": "Fast, cost-effective OpenAI model",
      "cost_tier": "low",
      "tags": ["openai", "fast", "cost-effective"]
    }
  }
}
```

## API Endpoints

### List Enabled Models
```http
GET /api/enabled-models
GET /api/enabled-models?enabled_only=true
GET /api/enabled-models?provider_type=native_anthropic
GET /api/enabled-models?tag=fast
```

### Manage Individual Models
```http
GET /api/enabled-models/{model_name}
POST /api/enabled-models
PUT /api/enabled-models/{model_name}
DELETE /api/enabled-models/{model_name}
```

### Enable/Disable Models
```http
POST /api/enabled-models/{model_name}/enable
POST /api/enabled-models/{model_name}/disable
```

### Provider Summary
```http
GET /api/enabled-models/providers/summary
```

## Environment Variables Required

Each provider type requires specific API keys:

- **OpenAI**: `OPENAI_API_KEY`
- **Anthropic**: `ANTHROPIC_API_KEY`
- **Google**: `GOOGLE_API_KEY`
- **OpenRouter**: `OPENROUTER_API_KEY`

You can override the environment variable name per model using `api_key_env_var`.

## Adding New Models

### Via API
```bash
curl -X POST "http://localhost:8001/api/enabled-models" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "claude-3-opus",
    "provider_type": "openrouter",
    "display_name": "Claude 3 Opus (OpenRouter)",
    "enabled": true,
    "api_key_env_var": "OPENROUTER_API_KEY",
    "description": "High-performance Claude model via OpenRouter",
    "cost_tier": "high",
    "tags": ["anthropic", "openrouter", "high-performance"]
  }'
```

### Manual Configuration
Edit `enabled_models.json` directly and restart the service.

## Integration with Pipeline Flavors

Pipeline flavors automatically use the new routing system. When you create a flavor with a specific `llm_model`, the system will:

1. Check if the model is enabled in `enabled_models.json`
2. Route to the appropriate provider based on `provider_type`
3. Apply model capabilities validation and parameter filtering
4. Create the LLM instance with proper authentication

## UX Integration Guidelines

### 1. Model Selection Dropdown

```typescript
const availableModels = await fetch('/api/enabled-models?enabled_only=true')
  .then(r => r.json());

const modelsByProvider = groupBy(availableModels.models, 'provider_type');

// Show models grouped by provider
<ModelSelector>
  {Object.entries(modelsByProvider).map(([provider, models]) => (
    <OptGroup label={provider.replace('_', ' ').toUpperCase()}>
      {models.map(model => (
        <Option value={model.model_name}>
          {model.display_name}
          <Badge color={model.cost_tier}>{model.cost_tier}</Badge>
        </Option>
      ))}
    </OptGroup>
  ))}
</ModelSelector>
```

### 2. Provider Status Indicators

```typescript
const providerSummary = await fetch('/api/enabled-models/providers/summary')
  .then(r => r.json());

// Show provider health status
{Object.entries(providerSummary.providers).map(([provider, info]) => (
  <ProviderCard key={provider}>
    <h3>{provider}</h3>
    <p>{info.enabled_models} of {info.total_models} enabled</p>
    <StatusBadge status={info.enabled_models > 0 ? 'active' : 'inactive'} />
  </ProviderCard>
))}
```

### 3. Model Management Interface

```typescript
const toggleModel = async (modelName: string, enabled: boolean) => {
  const action = enabled ? 'enable' : 'disable';
  await fetch(`/api/enabled-models/${modelName}/${action}`, {
    method: 'POST'
  });
  // Refresh model list
};

// Show model management table
<ModelTable>
  {models.map(model => (
    <tr key={model.model_name}>
      <td>{model.display_name}</td>
      <td><ProviderBadge type={model.provider_type} /></td>
      <td><CostBadge tier={model.cost_tier} /></td>
      <td>
        <Switch
          checked={model.enabled}
          onChange={(enabled) => toggleModel(model.model_name, enabled)}
        />
      </td>
    </tr>
  ))}
</ModelTable>
```

## Benefits

1. **Dynamic Configuration** - Add/remove models without code changes
2. **Provider Flexibility** - Use native APIs for performance, OpenRouter for variety
3. **Cost Control** - Enable expensive models only when needed
4. **Environment Separation** - Different model sets for dev/staging/prod
5. **Graceful Degradation** - Fallback to legacy behavior if routing fails

## Migration from Legacy

The system maintains backward compatibility. Existing pipeline flavors continue working, but now benefit from:

- Automatic parameter validation based on model capabilities
- Dynamic provider routing
- Enhanced error handling

## Troubleshooting

### Model Not Available
- Check if model is enabled: `GET /api/enabled-models/{model_name}`
- Verify API key environment variable is set
- Check provider configuration

### Provider Routing Fails
- Service falls back to legacy OpenAI-only behavior
- Check logs for specific error messages
- Verify `enabled_models.json` format is valid

### Performance Considerations
- LLM instances are cached per model configuration
- Changing model settings clears cache automatically
- Provider routing adds minimal overhead (<1ms)

## Security

- API keys are loaded from environment variables only
- Configuration file contains no sensitive data
- Model names and providers are logged but not API keys
- Custom endpoints allow for secure proxy setups