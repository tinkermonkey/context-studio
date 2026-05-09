# Configuration Management UX Guide

This guide provides comprehensive recommendations for building user interfaces to manage Context Studio's configuration system, including the new dynamic LLM model management.

## Overview

Context Studio has a two-tier configuration system:

1. **Static Configuration** (`config.json`) - Server settings, defaults, and operational parameters
2. **Dynamic Model Configuration** (`enabled_models.json`) - User-managed LLM model selection and routing

Both are accessible via REST APIs and should be presented in an organized, user-friendly interface.

## Configuration Architecture

### Static Configuration Sections
- **Server Settings** - Host, port, CORS, logging levels
- **Database Configuration** - File paths, connection settings
- **LLM Defaults** - Default model settings for new pipeline flavors
- **NLP Configuration** - spaCy models, processing settings
- **Reference Sources** - External API configurations (ConceptNet, DBpedia, etc.)
- **Proxy Server** - Caching proxy settings
- **Security** - Authentication and access control

### Dynamic Configuration
- **Enabled Models** - User's active LLM model selection and provider routing

## Recommended UX Organization

### Primary Navigation Structure

```
Settings
├── LLM Models ⭐ (Most Important)
│   ├── Available Models
│   ├── Provider Configuration
│   └── Model Capabilities
├── Data Sources
│   ├── Reference APIs
│   └── Database Settings
├── Processing
│   ├── NLP Configuration
│   └── Pipeline Defaults
├── System
│   ├── Server Settings
│   ├── Logging
│   └── Security
└── Advanced
    ├── Proxy Configuration
    └── Raw Configuration
```

## Detailed UX Recommendations

### 1. LLM Models Section ⭐ **PRIORITY**

This should be the most prominent and user-friendly section.

#### 1.1 Available Models Tab

**Layout**: Card-based grid with provider grouping

```typescript
interface ModelCard {
  model_name: string;
  display_name: string;
  provider_type: 'native_openai' | 'native_anthropic' | 'native_google' | 'openrouter';
  enabled: boolean;
  cost_tier: 'low' | 'medium' | 'high';
  description: string;
  tags: string[];
}

// Group models by provider
const providerGroups = {
  'Native Providers': models.filter(m => m.provider_type.startsWith('native_')),
  'OpenRouter': models.filter(m => m.provider_type === 'openrouter'),
  'Disabled': models.filter(m => !m.enabled)
};
```

**Features**:
- Toggle switches for enable/disable
- Cost indicators (color-coded badges)
- Provider icons and labels
- Quick enable/disable for entire provider groups
- Search and tag filtering

#### 1.2 Provider Configuration Tab

**API Key Management**:
```typescript
interface ProviderConfig {
  provider: string;
  api_key_status: 'configured' | 'missing' | 'invalid';
  api_key_env_var: string;
  enabled_models_count: number;
  total_models_count: number;
}
```

**Features**:
- API key status indicators (green/yellow/red)
- Environment variable name display
- Test connection buttons
- Model count summaries
- Custom endpoint configuration for advanced users

#### 1.3 Model Capabilities Tab

**Read-only reference showing**:
- Parameter support matrix (temperature, top_k, etc.)
- Context window sizes
- Token limits
- Special features (structured output, function calling)

### 2. Data Sources Section

#### 2.1 Reference APIs Tab

**Endpoint**: `GET /api/config/reference-sources/status`

```typescript
interface ReferenceSource {
  name: string;
  enabled: boolean;
  upstream_url: string;
  use_proxy: boolean;
  timeout: number;
  status: 'healthy' | 'error' | 'disabled';
  last_check?: Date;
}
```

**Features**:
- Status indicators with health checks
- Enable/disable toggles
- Timeout configuration sliders
- Proxy routing toggles
- Test connection buttons

#### 2.2 Database Settings Tab

**Low-priority, advanced users only**:
- File path configurations
- Connection pool settings
- Migration status

### 3. Processing Section

#### 3.1 NLP Configuration Tab

**Endpoint**: `GET /api/config/nlp`

**Features**:
- spaCy model selection dropdown
- Text length limits
- Download missing models button
- Processing timeout settings

#### 3.2 Pipeline Defaults Tab

**Integration with LLM Models**:
- Default model selection (from enabled models only)
- Default temperature/parameters
- Structured output preferences

### 4. System Section

#### 4.1 Server Settings Tab

**Endpoint**: `GET /api/config/server`

**Caution**: Changes require restart
- Host/port configuration
- CORS settings
- Access logging toggles

#### 4.2 Logging Tab

**Endpoint**: `GET /api/config/logging`

- Log level dropdown
- File vs console output
- Log rotation settings

#### 4.3 Security Tab

**Restricted access**:
- API key requirements
- Security logging

### 5. Advanced Section

#### 5.1 Proxy Configuration Tab

**For advanced users**:
- Proxy server enable/disable
- Cache settings
- Rate limiting

#### 5.2 Raw Configuration Tab

**Developer tool**:
- JSON editor with validation
- Import/export functionality
- Reset to defaults

## Implementation Guidelines

### API Integration Patterns

#### 1. Configuration Reading
```typescript
// Get specific configuration section
const response = await fetch('/api/config/reference-sources');
const config = response.json();

// Get individual values
const timeout = await fetch('/api/config/nlp.timeout');
```

#### 2. Configuration Updates
```typescript
// Update specific values
await fetch('/api/config/', {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    path: 'nlp.timeout',
    value: 60
  })
});

// Update reference source
await fetch('/api/config/reference-sources/conceptnet', {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    path: 'enabled',
    value: true
  })
});
```

#### 3. LLM Model Management
```typescript
// Get enabled models
const models = await fetch('/api/enabled-models?enabled_only=true');

// Toggle model
await fetch(`/api/enabled-models/${modelName}/enable`, {
  method: 'POST'
});

// Add new model
await fetch('/api/enabled-models', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model_name: 'gpt-4',
    provider_type: 'native_openai',
    display_name: 'GPT-4',
    enabled: true,
    api_key_env_var: 'OPENAI_API_KEY'
  })
});
```

### UI Components

#### 1. Provider Status Card
```tsx
interface ProviderStatusProps {
  provider: string;
  status: 'healthy' | 'error' | 'disabled';
  enabledModels: number;
  totalModels: number;
}

const ProviderStatusCard: React.FC<ProviderStatusProps> = ({
  provider, status, enabledModels, totalModels
}) => (
  <Card className="provider-status">
    <CardHeader>
      <div className="flex items-center gap-2">
        <ProviderIcon provider={provider} />
        <h3>{provider.replace('_', ' ').toUpperCase()}</h3>
        <StatusBadge status={status} />
      </div>
    </CardHeader>
    <CardContent>
      <div className="stats">
        <span>{enabledModels} of {totalModels} models enabled</span>
      </div>
      <div className="actions">
        <Button variant="outline" size="sm">Configure</Button>
        <Button variant="outline" size="sm">Test Connection</Button>
      </div>
    </CardContent>
  </Card>
);
```

#### 2. Model Toggle Card
```tsx
interface ModelToggleProps {
  model: EnabledModelConfig;
  onToggle: (modelName: string, enabled: boolean) => void;
}

const ModelToggleCard: React.FC<ModelToggleProps> = ({ model, onToggle }) => (
  <Card className={`model-card ${model.enabled ? 'enabled' : 'disabled'}`}>
    <CardHeader>
      <div className="flex items-center justify-between">
        <div>
          <h4>{model.display_name}</h4>
          <p className="text-sm text-gray-600">{model.description}</p>
        </div>
        <Switch
          checked={model.enabled}
          onCheckedChange={(enabled) => onToggle(model.model_name, enabled)}
        />
      </div>
    </CardHeader>
    <CardContent>
      <div className="flex gap-2">
        <ProviderBadge type={model.provider_type} />
        <CostBadge tier={model.cost_tier} />
        {model.tags.map(tag => (
          <Badge key={tag} variant="secondary" size="sm">{tag}</Badge>
        ))}
      </div>
    </CardContent>
  </Card>
);
```

#### 3. Configuration Form Field
```tsx
interface ConfigFieldProps {
  path: string;
  label: string;
  description?: string;
  type: 'string' | 'number' | 'boolean' | 'enum';
  value: any;
  options?: string[]; // For enum type
  onChange: (path: string, value: any) => void;
}

const ConfigField: React.FC<ConfigFieldProps> = ({
  path, label, description, type, value, options, onChange
}) => {
  const handleChange = (newValue: any) => {
    onChange(path, newValue);
  };

  return (
    <FormField>
      <Label htmlFor={path}>{label}</Label>
      {description && (
        <p className="text-sm text-gray-600">{description}</p>
      )}

      {type === 'boolean' && (
        <Switch
          id={path}
          checked={value}
          onCheckedChange={handleChange}
        />
      )}

      {type === 'string' && (
        <Input
          id={path}
          value={value || ''}
          onChange={(e) => handleChange(e.target.value)}
        />
      )}

      {type === 'number' && (
        <Input
          id={path}
          type="number"
          value={value || 0}
          onChange={(e) => handleChange(Number(e.target.value))}
        />
      )}

      {type === 'enum' && options && (
        <Select value={value} onValueChange={handleChange}>
          {options.map(option => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </Select>
      )}
    </FormField>
  );
};
```

### State Management

#### Configuration Store
```typescript
interface ConfigState {
  // Static configuration
  server: ServerConfig;
  database: DatabaseConfig;
  llm: LLMConfig;
  nlp: NLPConfig;
  referenceSources: ReferenceSourcesConfig;
  logging: LoggingConfig;

  // Dynamic model configuration
  enabledModels: EnabledModelConfig[];

  // UI state
  loading: boolean;
  hasUnsavedChanges: boolean;
  lastSaved: Date | null;
}

// Actions
interface ConfigActions {
  loadConfig: () => Promise<void>;
  updateConfigValue: (path: string, value: any) => Promise<void>;
  toggleModel: (modelName: string, enabled: boolean) => Promise<void>;
  addModel: (config: EnabledModelConfig) => Promise<void>;
  removeModel: (modelName: string) => Promise<void>;
  resetToDefaults: () => Promise<void>;
  saveChanges: () => Promise<void>;
}
```

### Validation and Error Handling

#### 1. Real-time Validation
```typescript
const validateConfigValue = (path: string, value: any): string | null => {
  // Get schema for validation
  const schema = getConfigSchema();
  const fieldSchema = getNestedProperty(schema, path);

  if (!fieldSchema) return 'Invalid configuration path';

  // Type validation
  if (fieldSchema.type === 'number' && typeof value !== 'number') {
    return 'Must be a number';
  }

  // Range validation
  if (fieldSchema.minimum && value < fieldSchema.minimum) {
    return `Must be at least ${fieldSchema.minimum}`;
  }

  return null;
};
```

#### 2. Connection Testing
```typescript
const testApiConnection = async (provider: string): Promise<boolean> => {
  try {
    // This would be implemented in the backend
    const response = await fetch(`/api/test-connection/${provider}`, {
      method: 'POST'
    });
    return response.ok;
  } catch (error) {
    return false;
  }
};
```

### Security Considerations

#### 1. Sensitive Data Display
- Never display actual API keys (show masked values or status only)
- Hide advanced settings from regular users
- Audit configuration changes

#### 2. Environment Variable Management
```typescript
const ApiKeyStatus: React.FC<{ envVar: string }> = ({ envVar }) => {
  const [status, setStatus] = useState<'checking' | 'configured' | 'missing'>('checking');

  useEffect(() => {
    // Check if environment variable is configured
    fetch(`/api/env-status/${envVar}`)
      .then(response => response.json())
      .then(data => setStatus(data.configured ? 'configured' : 'missing'))
      .catch(() => setStatus('missing'));
  }, [envVar]);

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-mono">{envVar}</span>
      <StatusIndicator status={status} />
      {status === 'missing' && (
        <Alert variant="warning">
          <AlertIcon />
          <AlertTitle>API Key Required</AlertTitle>
          <AlertDescription>
            Set the {envVar} environment variable to use this provider.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
};
```

## User Experience Flows

### 1. First-Time Setup Flow
1. **Welcome Screen** - Brief explanation of configuration
2. **API Key Setup** - Guide through setting up at least one LLM provider
3. **Model Selection** - Enable recommended models based on use case
4. **Test Configuration** - Run a simple test to verify setup

### 2. Model Management Flow
1. **Browse Available Models** - Provider-grouped model cards
2. **Enable Models** - Simple toggle interface
3. **Configure Providers** - API key status and settings
4. **Test Models** - Quick test functionality

### 3. Configuration Backup/Restore Flow
1. **Export Configuration** - Download current settings
2. **Import Configuration** - Upload and validate settings
3. **Reset to Defaults** - Confirmation dialog with backup option

## Performance Considerations

- **Lazy Loading**: Load configuration sections on demand
- **Debounced Updates**: Batch configuration changes
- **Optimistic Updates**: Update UI immediately, sync with server
- **Caching**: Cache configuration data with invalidation
- **Real-time Status**: WebSocket connection for live status updates

## Testing Strategy

### 1. Unit Tests
- Configuration validation functions
- State management logic
- Component rendering with different configurations

### 2. Integration Tests
- API communication
- Configuration persistence
- Provider connection testing

### 3. User Testing
- First-time setup usability
- Model management workflows
- Error recovery scenarios

This comprehensive approach will provide users with a powerful yet approachable configuration interface that scales from basic model selection to advanced system administration.