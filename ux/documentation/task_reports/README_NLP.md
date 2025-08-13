# NLP Analysis API Integration

This document describes the newly integrated NLP Analysis API endpoint and how to use it in the Context Studio UX.

## Overview

The NLP Analysis API (`/api/nlp_analysis`) provides natural language processing capabilities including:
- Text tokenization with linguistic features
- Named entity recognition
- POS tagging
- Lemmatization
- Integration with external knowledge bases (DBpedia, WordNet, etc.)

## API Endpoint

**POST** `/api/nlp_analysis`

### Request
```typescript
{
  text: string  // The text to analyze
}
```

### Response
```typescript
{
  success: boolean,
  data: {
    text: string,           // Original analyzed text
    tokens?: TokenData[],   // Array of token analysis
    entities?: EntityData[] // Array of recognized entities
  }
}
```

### Error Response
```typescript
{
  success: boolean,  // false
  error: string      // Error message
}
```

## Service Layer

### NLPService

The `NLPService` class provides methods for interacting with the NLP API:

```typescript
import { nlpService } from '@/api';

// Comprehensive analysis
const analysis = await nlpService.analyzeText("Your text here");

// Extract only tokens
const tokens = await nlpService.extractTokens("Your text here");

// Extract only entities
const entities = await nlpService.extractEntities("Your text here");
```

## React Hooks

### Query Hooks (Auto-triggered)

Use these hooks for automatic analysis when text changes:

```typescript
import { 
  useNLPAnalysis, 
  useTokenExtraction, 
  useEntityExtraction,
  useComprehensiveNLPAnalysis 
} from '@/api';

// Full analysis
const { data, isLoading, error } = useNLPAnalysis(text);

// Token extraction only
const { data: tokens } = useTokenExtraction(text);

// Entity extraction only  
const { data: entities } = useEntityExtraction(text);

// Comprehensive analysis (same as useNLPAnalysis)
const { data: fullAnalysis } = useComprehensiveNLPAnalysis(text);
```

### Mutation Hooks (Manual triggering)

Use these hooks for manual analysis triggering:

```typescript
import { 
  useAnalyzeTextMutation,
  useExtractTokensMutation,
  useExtractEntitiesMutation,
  useComprehensiveAnalysisMutation
} from '@/api';

// Manual analysis trigger
const analyzeText = useAnalyzeTextMutation({
  onSuccess: (data) => console.log('Analysis complete:', data),
  onError: (error) => console.error('Analysis failed:', error)
});

// Trigger analysis
analyzeText.mutate("Text to analyze");
```

## Data Types

### TokenData
```typescript
interface TokenData {
  text: string;           // Token text
  lemma?: string;         // Base form
  pos?: string;           // Part of speech
  tag?: string;           // Detailed POS tag
  start?: number;         // Start position
  end?: number;           // End position
  concepcy?: ConcepcyData;    // Concepcy knowledge base data
  wordnet?: WordNetData;      // WordNet data
  sense2vec?: Sense2VecData;  // Sense2vec data
}
```

### EntityData
```typescript
interface EntityData {
  text: string;           // Entity text
  label?: string;         // Entity type/label
  kb_id?: string;         // Knowledge base ID
  dbpedia?: DBpediaData;  // DBpedia data
}
```

### ConcepcyData
```typescript
interface ConcepcyData {
  related_terms?: string[];  // Related terms from ConceptNet
  score?: number;            // ConceptNet similarity score
}
```

### WordNetData
```typescript
interface WordNetData {
  synsets?: object[];      // WordNet synsets with attributes
  lemmas?: object[];       // WordNet lemmas with attributes  
  definitions?: string[];  // WordNet definitions
}
```

### Sense2VecData
```typescript
interface Sense2VecData {
  in_s2v?: boolean;        // Whether token is in sense2vec model
  key?: string;            // Sense2vec key (e.g., 'duck NOUN')
  freq?: number;           // Frequency in sense2vec corpus
  other_senses?: string[]; // Other senses for this word
  most_similar?: object[]; // Most similar words with scores
}
```

### DBpediaData
```typescript
interface DBpediaData {
  uri?: string;           // DBpedia URI
  label?: string;         // DBpedia label
  similarity?: number;    // DBpedia similarity score
  raw_result?: unknown;   // Raw DBpedia result
}
```

## Usage Examples

### Basic Analysis Component

```tsx
import React, { useState } from 'react';
import { useNLPAnalysis } from '@/api';

export const TextAnalyzer: React.FC = () => {
  const [text, setText] = useState('');
  
  const { data: analysis, isLoading, error } = useNLPAnalysis(
    text.length > 3 ? text : null // Only analyze if text is longer than 3 chars
  );

  return (
    <div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Enter text to analyze..."
      />
      
      {isLoading && <div>Analyzing...</div>}
      {error && <div>Error: {error.message}</div>}
      
      {analysis && (
        <div>
          <h3>Tokens: {analysis.tokens?.length || 0}</h3>
          <h3>Entities: {analysis.entities?.length || 0}</h3>
        </div>
      )}
    </div>
  );
};
```

### Manual Analysis Component

```tsx
import React, { useState } from 'react';
import { useAnalyzeTextMutation } from '@/api';

export const ManualAnalyzer: React.FC = () => {
  const [text, setText] = useState('');
  
  const analyzeText = useAnalyzeTextMutation({
    onSuccess: (data) => {
      console.log('Analysis complete:', data);
    }
  });

  const handleAnalyze = () => {
    if (text.trim()) {
      analyzeText.mutate(text);
    }
  };

  return (
    <div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Enter text to analyze..."
      />
      
      <button 
        onClick={handleAnalyze}
        disabled={analyzeText.isPending}
      >
        {analyzeText.isPending ? 'Analyzing...' : 'Analyze'}
      </button>
      
      {analyzeText.data && (
        <pre>{JSON.stringify(analyzeText.data, null, 2)}</pre>
      )}
    </div>
  );
};
```

## Configuration

The NLP API configuration is automatically included in:

- **ENDPOINTS.NLP**: `/api/nlp_analysis`
- **QUERY_KEYS.NLP**: `'nlp'`

## Error Handling

Errors are automatically handled by the global error handler configured in the query client. For custom error handling, use the mutation hooks with `onError` callbacks or handle errors in your components.

## Caching

- **Stale Time**: 5 minutes (results are cached for 5 minutes)
- **GC Time**: 10 minutes (cached data is garbage collected after 10 minutes)
- **Query Keys**: Include the text content for proper cache invalidation

## Notes

- Analysis is only triggered when text is provided and non-empty
- The service includes input validation and sanitization
- All network requests include retry logic and timeout handling
- Types are manually defined pending OpenAPI schema updates
