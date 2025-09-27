# UX Migration Guide: Legacy LLM Endpoints to Pipeline Flavors

## Overview

This guide outlines the migration path from legacy LLM endpoints to the new unified pipeline flavor system. The new system provides better configurability, traceability, and consistency across all LLM operations.

## Legacy vs New Endpoints

### Legacy Endpoints (DEPRECATED)
- `suggest_term_definition`
- `suggest_layer_definition`
- `suggest_domain_integration`

### New Endpoints
- `/api/llm/execute_pipeline` - Execute any pipeline with full tracking
- `/api/llm/execute_pipeline/stream` - Execute any pipeline with streaming response
- `/api/pipeline-flavors` - Manage pipeline configurations

## Pipeline Types

The new system supports these pipeline types:
- `suggest_term_definition`
- `suggest_layer_definition`
- `suggest_domain_definition`

## Migration Steps

### 1. Update Generated TypeScript Types (CRITICAL FIRST STEP)

Before making any code changes, ensure your frontend has the latest API types:

```bash
# In the UX directory, run:
npm run generate-types
```

This updates the TypeScript definitions from the backend's OpenAPI specification. The error "pipeline_type is required" often indicates outdated generated types.

**Verify the generated types include:**
```typescript
// Should be in your generated API types file
export interface GenericPipelineExecutionRequest {
  pipeline_type: 'suggest_term_definition' | 'suggest_layer_definition' | 'suggest_domain_definition';
  flavor_id: string;
  context_data: Record<string, any>;
}
```

### 2. Update Endpoint URLs

**Before:**
```typescript
// Legacy endpoint calls
const response = await fetch('/api/suggest_term_definition', {
  method: 'POST',
  body: JSON.stringify(termData)
});
```

**After:**
```typescript
// New generic pipeline endpoint
const response = await fetch('/api/llm/execute_pipeline', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    pipeline_type: 'suggest_term_definition',
    flavor_id: 'default', // or specific flavor ID
    context_data: {
      term: termData.term,
      domain_title: termData.domain_title,
      // ... other context data
    }
  })
});
```

### 2. Update Request Format

The new system uses a standardized request format:

```typescript
interface GenericPipelineExecutionRequest {
  pipeline_type: 'suggest_term_definition' | 'suggest_layer_definition' | 'suggest_domain_definition';
  flavor_id: string; // 'default' or specific flavor ID
  context_data: Record<string, any>; // Flexible context data
}
```

### 3. Update Response Handling

**New Response Format:**
```typescript
interface GenericPipelineExecutionResponse {
  execution_id: string;
  pipeline_type: string;
  flavor_id: string;
  status: 'completed' | 'failed';
  result?: string;
  error?: string;
  metadata: {
    execution_time_ms: number;
    token_count?: number;
    model_used: string;
    timestamp: string;
  };
}
```

## Example Migrations

### Term Definition Migration

**Before:**
```typescript
const termDefinitionRequest = {
  term: "Knowledge Graph",
  domain_title: "Data Management",
  additional_context: "Used in enterprise settings"
};

const response = await fetch('/api/suggest_term_definition', {
  method: 'POST',
  body: JSON.stringify(termDefinitionRequest)
});
```

**After:**
```typescript
const termDefinitionRequest = {
  pipeline_type: 'suggest_term_definition',
  flavor_id: 'default',
  context_data: {
    term: "Knowledge Graph",
    domain_title: "Data Management",
    additional_context: "Used in enterprise settings"
  }
};

const response = await fetch('/api/llm/execute_pipeline', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(termDefinitionRequest)
});

const result = await response.json();
console.log('Execution ID:', result.execution_id);
console.log('Result:', result.result);
```

### Layer Definition Migration

**Before:**
```typescript
const layerRequest = {
  layer_name: "Data Access Layer",
  domain_context: "API Architecture"
};
```

**After:**
```typescript
const layerRequest = {
  pipeline_type: 'suggest_layer_definition',
  flavor_id: 'default',
  context_data: {
    layer_name: "Data Access Layer",
    domain_context: "API Architecture"
  }
};
```

### Domain Integration Migration

**Before:**
```typescript
const domainRequest = {
  domain_name: "User Management",
  integration_context: "OAuth Integration"
};
```

**After:**
```typescript
const domainRequest = {
  pipeline_type: 'suggest_domain_definition',
  flavor_id: 'default',
  context_data: {
    domain_name: "User Management",
    integration_context: "OAuth Integration"
  }
};
```

## Streaming Support

The new system includes streaming support for real-time responses:

```typescript
const streamResponse = await fetch('/api/llm/execute_pipeline/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(request)
});

const reader = streamResponse.body?.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      console.log('Streaming chunk:', data);

      if (data.done) {
        console.log('Streaming complete');
        break;
      }
    }
  }
}
```

## Pipeline Flavor Management

The new system allows managing different "flavors" of each pipeline type with different configurations:

### List Available Flavors

```typescript
// Get all flavors
const flavorsResponse = await fetch('/api/pipeline-flavors');
const { flavors, total_count } = await flavorsResponse.json();

// Get flavors for specific pipeline
const termFlavorsResponse = await fetch('/api/pipeline-flavors?pipeline=suggest_term_definition');
```

### Get Specific Flavor

```typescript
// Get default flavor for a pipeline
const defaultFlavor = await fetch('/api/pipeline-flavors/default?pipeline=suggest_term_definition');

// Get specific flavor by ID
const customFlavor = await fetch('/api/pipeline-flavors/flavor-uuid-here');
```

### Create Custom Flavors

```typescript
const newFlavor = {
  pipeline: 'suggest_term_definition',
  title: 'Technical Terms Specialist',
  llm_provider: 'openai',
  llm_model: 'gpt-4',
  llm_config: {
    temperature: 0.3,
    max_tokens: 1000
  },
  system_prompt: 'You are a technical terminology expert...',
  user_prompt: 'Define the term {term} in the context of {domain_title}...'
};

const response = await fetch('/api/pipeline-flavors', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(newFlavor)
});
```

## Error Handling

The new system provides consistent error responses:

```typescript
try {
  const response = await fetch('/api/llm/execute_pipeline', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const error = await response.json();
    console.error('Pipeline execution failed:', error.detail);
    return;
  }

  const result = await response.json();
  // Handle success
} catch (error) {
  console.error('Network error:', error);
}
```

## Benefits of Migration

1. **Unified Interface**: All pipeline types use the same endpoints
2. **Better Tracking**: Every execution gets a unique ID for monitoring
3. **Flexible Configuration**: Multiple flavors per pipeline type
4. **Streaming Support**: Real-time responses for better UX
5. **Enhanced Error Handling**: Consistent error responses
6. **Execution Metadata**: Detailed timing and usage information

## Migration Checklist

- [ ] Update all endpoint URLs to use `/api/llm/execute_pipeline`
- [ ] Modify request format to use `GenericPipelineExecutionRequest`
- [ ] Update response handling for new response format
- [ ] Test streaming functionality if needed
- [ ] Update error handling to use new error format
- [ ] Remove legacy endpoint references
- [ ] Update TypeScript types and interfaces
- [ ] Test all pipeline types (term, layer, domain definition)

## TypeScript Type Definitions

Update your types to match the new system:

```typescript
enum PipelineType {
  SUGGEST_TERM_DEFINITION = 'suggest_term_definition',
  SUGGEST_LAYER_DEFINITION = 'suggest_layer_definition',
  SUGGEST_DOMAIN_DEFINITION = 'suggest_domain_definition'
}

interface LLMConfig {
  temperature?: number;
  top_p?: number;
  top_k?: number;
  max_tokens?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
}

interface PipelineFlavor {
  id: string;
  pipeline: PipelineType;
  title: string;
  llm_provider: string;
  llm_model: string;
  llm_config: LLMConfig;
  system_prompt: string;
  user_prompt: string;
  version: number;
  enabled: boolean;
  last_updated: string;
  date_created: string;
}

interface GenericPipelineExecutionRequest {
  pipeline_type: PipelineType;
  flavor_id: string;
  context_data: Record<string, any>;
}

interface GenericPipelineExecutionResponse {
  execution_id: string;
  pipeline_type: string;
  flavor_id: string;
  status: 'completed' | 'failed';
  result?: string;
  error?: string;
  metadata: {
    execution_time_ms: number;
    token_count?: number;
    model_used: string;
    timestamp: string;
  };
}
```

## Common Issues and Troubleshooting

### "pipeline_type is required" Error (Client-Side)

If this error appears **without any network requests** being made, it's a client-side validation error. This typically occurs when:

1. **Frontend form validation**: Check if your form validation logic requires `pipeline_type` but it's not being set:
   ```typescript
   // Check if you have validation like this that's failing:
   if (!formData.pipeline_type) {
     throw new Error("pipeline_type is required");
   }
   ```

2. **TypeScript interface mismatch**: Your frontend types may not match the new API structure:
   ```typescript
   // Old interface (wrong)
   interface OldRequest {
     term: string;
     domain_title: string;
   }

   // New interface (correct)
   interface GenericPipelineExecutionRequest {
     pipeline_type: 'suggest_term_definition' | 'suggest_layer_definition' | 'suggest_domain_definition';
     flavor_id: string;
     context_data: Record<string, any>;
   }
   ```

3. **Missing pipeline_type in form state**: The component state or form might not include the `pipeline_type` field:
   ```typescript
   // Ensure your form state includes pipeline_type:
   const [formData, setFormData] = useState({
     pipeline_type: 'suggest_term_definition', // ← Must be set
     flavor_id: 'default',
     context_data: {
       term: '',
       domain_title: ''
     }
   });
   ```

4. **Validation schema mismatch**: If using validation libraries (Yup, Zod, etc.), the schema might require `pipeline_type`:
   ```typescript
   // Update validation schema to include pipeline_type
   const schema = z.object({
     pipeline_type: z.enum(['suggest_term_definition', 'suggest_layer_definition', 'suggest_domain_definition']),
     flavor_id: z.string(),
     context_data: z.object({}).passthrough()
   });
   ```

### Client-Side Debugging Steps

1. **Check component state**: Log the form data before submission:
   ```typescript
   console.log('Form data before submission:', formData);
   // Verify pipeline_type is present and not undefined
   ```

2. **Check form validation**: Look for validation functions that might be throwing this error:
   ```typescript
   // Search your codebase for validation like:
   // "pipeline_type is required"
   // validateForm()
   // validateRequest()
   ```

3. **Check TypeScript errors**: Look for TypeScript compilation errors about missing required properties.

4. **Temporarily bypass validation**: Comment out form validation to see if the request structure is correct:
   ```typescript
   // Temporarily skip validation to test API call
   // if (!isValid) return;
   makeApiCall(formData);
   ```

### Debugging Steps

1. **Check the request in browser dev tools**:
   - Open Network tab
   - Look at the actual request being sent
   - Verify the Content-Type header is `application/json`
   - Check that all required fields are present

2. **Test with curl**:
   ```bash
   curl -X POST http://localhost:8000/api/llm/execute_pipeline \
     -H "Content-Type: application/json" \
     -d '{
       "flavor_id": "default",
       "pipeline_type": "suggest_term_definition",
       "context_data": {
         "term": "test term",
         "domain_title": "test domain"
       }
     }'
   ```

3. **Check server logs**: Look for validation errors in `logs/context_studio.log`

### Context Data Flexibility

The new pipeline system is designed to handle **optional context variables**. You don't need to provide all possible template variables - missing variables will automatically be replaced with "Not specified".

**Minimal Working Example:**
```typescript
// This minimal request will work fine - missing template variables are handled gracefully
const minimalRequest = {
  pipeline_type: 'suggest_term_definition',
  flavor_id: 'default',
  context_data: {
    term: 'Knowledge Graph',
    domain_title: 'Data Management'
    // All other variables (parent_term_title, etc.) are optional
  }
};
```

**Template Variable Handling by Pipeline Type:**

**suggest_term_definition:**
- Required: `term`, `domain_title`
- Optional: `domain_definition`, `parent_term_title`, `parent_term_definition`, `parent_relationship_predicate`, `component_terms`, `current_definition`, `conceptnet_relations`, `wikidata_context`, `dbpedia_context`

**suggest_layer_definition:**
- Required: `layer_name` (or similar layer identifier)
- Optional: `domain_context`, `parent_layer_title`, `related_layers`, `current_definition`

**suggest_domain_definition:**
- Required: `domain_name` (or similar domain identifier)
- Optional: `integration_context`, `parent_domain`, `related_domains`, `current_definition`

**Important:** Missing variables automatically become "Not specified" in the prompt, so you only need to provide the data you have available.

### Working Example Request

Here's a complete working example that you can test:

```typescript
const testRequest = async () => {
  try {
    const response = await fetch('/api/llm/execute_pipeline', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        flavor_id: 'default',
        pipeline_type: 'suggest_term_definition',
        context_data: {
          term: 'Knowledge Graph',
          domain_title: 'Data Management',
          domain_definition: 'Systems for organizing and accessing data',
          parent_term_title: null,
          parent_term_definition: null,
          parent_relationship_predicate: null,
          component_terms: '',
          current_definition: null,
          conceptnet_relations: '',
          wikidata_context: 'Not specified',
          dbpedia_context: 'Not specified'
        }
      })
    });

    if (!response.ok) {
      const error = await response.json();
      console.error('API Error:', error);
      return;
    }

    const result = await response.json();
    console.log('Success:', result);
  } catch (error) {
    console.error('Network Error:', error);
  }
};
```

## Need Help?

If you encounter issues during migration:
1. Check the OpenAPI documentation at `/documentation/openapi.json`
2. Review integration tests in `tests/integration_tests/test_pipeline_flavors_integration.py`
3. Test endpoints using the pipeline flavor management UI
4. Use the debugging steps above to identify request issues
5. Consult the backend team for complex migration scenarios