# Word Sense Selection API Documentation

## Overview

The Word Sense Selection API allows users to manage semantic word sense annotations on structure nodes. This feature enables precise disambiguation of multi-word titles by selecting specific WordNet senses for each word.

## Endpoints

### Get Word Senses

Retrieves the currently selected word senses for a structure node.

**Endpoint:** `GET /api/structure_nodes/{node_id}/word_senses`

**Parameters:**
- `node_id` (path, required): UUID of the structure node

**Response:** `200 OK`

```json
[
  {
    "term": "bank",
    "sense_type": "wordnet",
    "sense_id": "bank.n.01",
    "definition": "a financial institution that accepts deposits and channels the money into lending activities",
    "domain": "noun.group"
  },
  {
    "term": "account",
    "sense_type": "wordnet",
    "sense_id": "account.n.02",
    "definition": "a formal contractual relationship established to provide for regular banking or brokerage or business services",
    "domain": "noun.possession"
  }
]
```

**Error Responses:**
- `404 Not Found`: Structure node does not exist
- `422 Unprocessable Entity`: Invalid UUID format

---

### Update Word Senses

Updates the selected word senses for a structure node using conservative merge strategy. Only the senses for words in the request are updated; senses for other words are preserved.

**Endpoint:** `PUT /api/structure_nodes/{node_id}/word_senses`

**Parameters:**
- `node_id` (path, required): UUID of the structure node

**Request Body:**

```json
{
  "selected_senses": [
    {
      "term": "bank",
      "sense_type": "wordnet",
      "sense_id": "bank.n.02",
      "definition": "sloping land (especially the slope beside a body of water)",
      "domain": "noun.object"
    }
  ]
}
```

**Response:** `200 OK`

Returns the complete list of word senses after the update:

```json
[
  {
    "term": "bank",
    "sense_type": "wordnet",
    "sense_id": "bank.n.02",
    "definition": "sloping land (especially the slope beside a body of water)",
    "domain": "noun.object"
  },
  {
    "term": "account",
    "sense_type": "wordnet",
    "sense_id": "account.n.02",
    "definition": "a formal contractual relationship established to provide for regular banking or brokerage or business services",
    "domain": "noun.possession"
  }
]
```

**Error Responses:**
- `400 Bad Request`: Invalid sense_id format or validation error
- `404 Not Found`: Structure node does not exist
- `409 Conflict`: Version conflict (data modified by another user)
- `422 Unprocessable Entity`: Invalid request format

---

## Data Model

### WordSense

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| term | string | Yes | The word or term being annotated |
| sense_type | string | Yes | Type of sense annotation (currently "wordnet") |
| sense_id | string | Yes | WordNet sense identifier (e.g., "bank.n.01") |
| definition | string | Yes | Human-readable definition of the sense |
| domain | string | No | WordNet lexical domain (e.g., "noun.group") |

### Sense ID Format

WordNet sense IDs follow the pattern: `{lemma}.{pos}.{sense_number}`

- **lemma**: Base form of the word (e.g., "bank")
- **pos**: Part of speech (n=noun, v=verb, a=adjective, r=adverb)
- **sense_number**: 2-digit sense number (01, 02, etc.)

**Examples:**
- `bank.n.01` - financial institution
- `bank.n.02` - sloping land
- `run.v.01` - to move fast
- `good.a.01` - having desirable qualities

---

## Conservative Merge Behavior

The PUT endpoint uses a conservative merge strategy:

1. **Updating a word**: If a word appears in `selected_senses`, all previous senses for that word are replaced
2. **Preserving other words**: Senses for words not in `selected_senses` are kept unchanged
3. **Empty update**: Sending an empty array preserves all existing senses

**Example:**

Initial state:
```json
[
  {"term": "bank", "sense_id": "bank.n.01", ...},
  {"term": "account", "sense_id": "account.n.01", ...}
]
```

Update request:
```json
{
  "selected_senses": [
    {"term": "bank", "sense_id": "bank.n.02", ...}
  ]
}
```

Final state:
```json
[
  {"term": "bank", "sense_id": "bank.n.02", ...},
  {"term": "account", "sense_id": "account.n.01", ...}  // Preserved
]
```

---

## Validation Rules

1. **Sense ID Format**: Must match WordNet pattern `{word}.{pos}.{number}`
2. **Unique Terms**: Each term should appear only once in the update request
3. **Valid POS**: Part of speech must be n, v, a, or r
4. **Node Existence**: Structure node must exist before updating word senses
5. **Version Integrity**: Updates increment the node version for conflict detection

---

## Use Cases

### 1. Disambiguating Multi-Word Titles

For a term titled "bank account", users can select specific senses:
- "bank" → bank.n.01 (financial institution)
- "account" → account.n.02 (financial account)

This clarifies the meaning as a financial account, not a land description or narrative account.

### 2. Semantic Search Enhancement

Selected word senses can be used to:
- Improve semantic similarity calculations
- Enhance RAG (Retrieval-Augmented Generation) queries
- Build more accurate knowledge graphs
- Generate better definitions

### 3. Ontology Alignment

Map internal terms to external ontologies by recording precise WordNet senses, enabling:
- Cross-reference to other knowledge bases
- Alignment with standard vocabularies
- Interoperability with NLP tools

---

## Integration with Front-End

### React Query Hooks

```typescript
import { useWordSenses, useUpdateWordSenses } from '@/api/hooks/structure_nodes/useWordSenses';

// Fetch word senses
const { data: senses, isLoading } = useWordSenses(nodeId);

// Update word senses
const updateMutation = useUpdateWordSenses(nodeId, {
  onSuccess: () => {
    toast.success('Word senses saved successfully');
  }
});

// Save changes
updateMutation.mutate({
  selected_senses: [
    {
      term: 'bank',
      sense_type: 'wordnet',
      sense_id: 'bank.n.02',
      definition: 'sloping land',
      domain: 'noun.object'
    }
  ]
});
```

### WordSenseSelector Component

```typescript
import { WordSenseSelector } from '@/components/graphs/nlp_concept/WordSenseSelector';

<WordSenseSelector
  title="bank account"
  persistedSenses={senses}
  nodeId={nodeId}
  onSaveComplete={() => refetch()}
/>
```

**Features:**
- Interactive word selection with lazy NLP analysis
- Visual indication of selected senses
- Auto-save with optimistic updates
- Conflict resolution with automatic refetch
- Responsive grid layout (1-4 columns based on screen size)
- Full keyboard navigation support
- ARIA labels for screen readers

---

## Performance Considerations

### Lazy Loading

NLP analysis is triggered per-word only when a user expands that word's sense options. This prevents unnecessary API calls for large multi-word titles.

### Caching

- Word senses are cached using React Query with 5-minute stale time
- NLP analysis results are cached per word for 5 minutes
- Conservative merge prevents data loss during concurrent edits

### Optimization Tips

1. **Batch Updates**: Update multiple words in a single PUT request
2. **Version Tracking**: Node version increments on each update for conflict detection
3. **Optimistic Updates**: UI updates immediately before server confirmation
4. **Error Recovery**: Automatic rollback on failure with user notification

---

## Error Handling

### Network Errors

The client implements exponential backoff retry logic:
- Initial delay: 1 second
- Max delay: 30 seconds
- Max retries: 3
- Jitter: Random 0-1000ms to prevent thundering herd

### Conflict Resolution

On 409 Conflict error:
1. Automatically refetch latest data
2. Show user-friendly notification
3. Allow user to review changes and re-save
4. Preserve local changes in UI until dismissed

### Validation Errors

400 Bad Request errors show specific validation failures:
- Invalid sense ID format
- Missing required fields
- Malformed request body

---

## Testing

### Integration Tests

See `/local-server/tests/integration_tests/test_word_sense_update_integration.py` for comprehensive test coverage:

- ✓ Update word senses successfully
- ✓ Conservative merge preserves other words
- ✓ Replace all senses for a word
- ✓ Validate sense ID format
- ✓ Handle node not found errors
- ✓ Version increment on update
- ✓ Empty list handling

### Front-End Tests

See `/ux/test/integration/word_sense.integration.test.tsx` for UI workflow tests:

- ✓ Load persisted senses on mount
- ✓ Expand word and trigger NLP analysis
- ✓ Select/deselect senses
- ✓ Save with optimistic updates
- ✓ Handle API errors gracefully
- ✓ Multi-word lazy loading

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-11-08 | Initial release: GET and PUT endpoints for word sense management |

---

## Related Documentation

- [NLP Processing API](/documentation/features/backend/nlp-processing.md)
- [Structure Nodes API](/documentation/features/backend/knowledge-graph-management.md)
- [Reference Links API](/documentation/reference_link_api.md)
- [React Component Guide](/documentation/component_usage.md)
