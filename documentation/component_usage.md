# Component Usage Guide

## Overview

This guide provides examples and best practices for using the word sense selection and reference node components in Context Studio.

---

## Word Sense Selection Components

### WordSenseSelector

The `WordSenseSelector` component provides an interactive interface for selecting WordNet senses for each word in a multi-word title.

#### Basic Usage

```typescript
import { WordSenseSelector } from '@/components/graphs/nlp_concept/WordSenseSelector';
import { useWordSenses } from '@/api/hooks/structure_nodes/useWordSenses';

function TermDetailsPage({ termId }: { termId: string }) {
  const { data: wordSenses = [], refetch } = useWordSenses(termId);

  return (
    <WordSenseSelector
      title="bank account"
      persistedSenses={wordSenses}
      nodeId={termId}
      onSaveComplete={() => refetch()}
    />
  );
}
```

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| title | string | Yes | The multi-word title to analyze |
| persistedSenses | WordSense[] | Yes | Initially selected senses from database |
| nodeId | string | Yes | UUID of the structure node |
| onSaveComplete | () => void | No | Callback executed after successful save |

#### Features

**Lazy Loading**
- NLP analysis is triggered only when a user clicks to expand a word
- Previously analyzed words are cached in component state
- Prevents unnecessary API calls for large titles

**Keyboard Navigation**
- Tab: Navigate between word cards
- Enter/Space: Expand/collapse word analysis
- Focus returns to save button after save operation

**Responsive Layout**
- 1 column on mobile (< 640px)
- 2 columns on small screens (≥ 640px)
- 3 columns on large screens (≥ 1024px)
- 4 columns on extra-large screens (≥ 1280px)

**Accessibility**
- Full ARIA labels for screen readers
- Semantic HTML with proper roles
- Live regions for dynamic content
- Focus management for optimal UX

#### Example: Custom Success Handler

```typescript
import { toast } from '@/utils/toast';
import { useQueryClient } from '@tanstack/react-query';

function MyComponent({ nodeId }: { nodeId: string }) {
  const queryClient = useQueryClient();
  const { data: wordSenses = [] } = useWordSenses(nodeId);

  const handleSaveComplete = () => {
    // Invalidate related queries
    queryClient.invalidateQueries(['structure_nodes', nodeId]);

    // Custom success notification
    toast.success('Word senses updated! Definition will be regenerated.', {
      duration: 5000
    });

    // Trigger any dependent workflows
    generateDefinition(nodeId);
  };

  return (
    <WordSenseSelector
      title="machine learning model"
      persistedSenses={wordSenses}
      nodeId={nodeId}
      onSaveComplete={handleSaveComplete}
    />
  );
}
```

---

### useWordSenses Hook

React Query hook for fetching word senses.

#### Usage

```typescript
import { useWordSenses } from '@/api/hooks/structure_nodes/useWordSenses';

const {
  data: wordSenses,
  isLoading,
  error,
  refetch
} = useWordSenses(nodeId, {
  enabled: !!nodeId,  // Only fetch when nodeId exists
  staleTime: 5 * 60 * 1000  // Cache for 5 minutes
});
```

#### Return Values

| Property | Type | Description |
|----------|------|-------------|
| data | WordSense[] \| undefined | Array of word senses or undefined if loading |
| isLoading | boolean | True while initial fetch is in progress |
| error | Error \| null | Error object if fetch failed |
| refetch | () => Promise | Function to manually refetch data |

---

### useUpdateWordSenses Hook

React Query mutation hook for updating word senses.

#### Usage

```typescript
import { useUpdateWordSenses } from '@/api/hooks/structure_nodes/useWordSenses';

const updateMutation = useUpdateWordSenses(nodeId, {
  onSuccess: (data) => {
    toast.success('Saved successfully');
    console.log('Updated senses:', data);
  },
  onError: (error) => {
    toast.error(`Save failed: ${error.message}`);
  }
});

// Trigger update
updateMutation.mutate({
  selected_senses: [
    {
      term: 'bank',
      sense_type: 'wordnet',
      sense_id: 'bank.n.01',
      definition: 'financial institution',
      domain: 'noun.group'
    }
  ]
});
```

#### Features

**Optimistic Updates**
- UI updates immediately before server confirmation
- Automatic rollback on error
- Snapshot of previous state for recovery

**Conflict Resolution**
- Detects version conflicts (409 errors)
- Automatically refetches latest data
- Shows user-friendly conflict message
- Preserves user's local changes for review

**Error Handling**
- Network errors: Automatic retry with exponential backoff
- Validation errors: User-friendly messages
- Conflict errors: Automatic refresh + notification

#### Example: With Conflict Handling

```typescript
const updateMutation = useUpdateWordSenses(nodeId, {
  onSuccess: (freshData) => {
    toast.success('Word senses saved');
    // Fresh data from server is already in cache
  },
  onError: async (error) => {
    if (error.message.includes('conflict')) {
      // Conflict resolution happens automatically
      // User sees notification and data refetches
      toast.warning('Data was updated elsewhere. Please review and save again.');
    } else {
      toast.error(`Failed to save: ${error.message}`);
    }
  }
});
```

---

## Reference Node Components

### ReferenceNodePanel

Container component for searching, selecting, and managing reference node associations.

#### Basic Usage

```typescript
import { ReferenceNodePanel } from '@/components/reference_nodes/ReferenceNodePanel';

function StructureNodeDetails({ nodeId }: { nodeId: string }) {
  return (
    <div className="space-y-6">
      {/* Other sections */}

      <ReferenceNodePanel nodeId={nodeId} />
    </div>
  );
}
```

#### Features

**State Management**
- Automatically fetches persisted reference links
- Manages search active/inactive states
- Coordinates selection list and display
- Handles UUID validation

**Search Interface**
- Unified search across multiple sources (Schema.org, Wikidata, ConceptNet)
- Streaming results for responsive UX
- Source status indicators
- Selection checkboxes for multi-select

**Error Handling**
- Invalid UUID validation
- API error messages
- Loading states
- Empty states

#### Example: Custom Integration

```typescript
import { ReferenceNodePanel } from '@/components/reference_nodes/ReferenceNodePanel';
import { useStructureNode } from '@/api/hooks/structure_nodes/useStructureNodes';

function EnhancedNodeDetails({ nodeId }: { nodeId: string }) {
  const { data: node } = useStructureNode(nodeId);

  if (!node) {
    return <LoadingSkeleton />;
  }

  return (
    <div className="space-y-6">
      <h1>{node.title}</h1>
      <p>{node.definition}</p>

      {/* Reference associations */}
      <section aria-label="External References">
        <ReferenceNodePanel nodeId={nodeId} />
      </section>
    </div>
  );
}
```

---

### useReferenceLinks Hook

React Query hook for managing reference links.

#### Usage

```typescript
import {
  useReferenceLinks,
  useAddReferenceLinks,
  useRemoveReferenceLink
} from '@/api/hooks/structure_nodes/useReferenceLinks';

function ReferenceManager({ nodeId }: { nodeId: string }) {
  // Fetch existing links
  const { data: links = [], isLoading } = useReferenceLinks(nodeId);

  // Add new links
  const addMutation = useAddReferenceLinks(nodeId, {
    onSuccess: (updatedLinks) => {
      toast.success(`Added ${updatedLinks.length} reference links`);
    }
  });

  // Remove a link
  const removeMutation = useRemoveReferenceLink(nodeId, {
    onSuccess: () => {
      toast.success('Reference link removed');
    }
  });

  const handleAdd = () => {
    addMutation.mutate([
      {
        source: 'schema.org',
        external_id: 'Person'
      }
    ]);
  };

  const handleRemove = (link: ReferenceLink) => {
    removeMutation.mutate([link]);
  };

  return (
    <div>
      {links.map(link => (
        <div key={`${link.source}-${link.external_id}`}>
          <span>{link.source}: {link.external_id}</span>
          <button onClick={() => handleRemove(link)}>Remove</button>
        </div>
      ))}
      <button onClick={handleAdd}>Add Reference</button>
    </div>
  );
}
```

---

## Loading States & Skeletons

### WordSenseCardSkeleton

Display loading placeholder while word senses are being fetched.

```typescript
import { WordSenseCardSkeleton } from '@/components/ui/LoadingSkeleton';

function WordSenseDisplay({ nodeId }: { nodeId: string }) {
  const { data: wordSenses, isLoading } = useWordSenses(nodeId);

  if (isLoading) {
    return <WordSenseCardSkeleton count={3} />;
  }

  return (
    <WordSenseSelector
      title="example title"
      persistedSenses={wordSenses}
      nodeId={nodeId}
    />
  );
}
```

### ReferenceNodeSkeleton

Display loading placeholder for reference links.

```typescript
import { ReferenceNodeSkeleton } from '@/components/ui/LoadingSkeleton';

function ReferenceDisplay({ nodeId }: { nodeId: string }) {
  const { data: links, isLoading } = useReferenceLinks(nodeId);

  if (isLoading) {
    return <ReferenceNodeSkeleton count={5} />;
  }

  return <ReferenceNodeDisplay nodeId={nodeId} referenceLinks={links} />;
}
```

---

## Error Handling Patterns

### Global Error Handler

```typescript
import { handleApiError } from '@/api/errors/errorHandlers';

try {
  await someMutation.mutateAsync(data);
} catch (error) {
  handleApiError(error, {
    context: 'Saving word senses',
    showToast: true,
    logError: true
  });
}
```

### Specific Error Types

```typescript
import {
  isNetworkError,
  isValidationError,
  isConflictError
} from '@/api/errors/errorHandlers';

const mutation = useMutation({
  onError: (error) => {
    if (isNetworkError(error)) {
      toast.error('Network error. Please check your connection.');
    } else if (isValidationError(error)) {
      toast.error('Invalid data. Please check your input.');
    } else if (isConflictError(error)) {
      toast.warning('Data was modified elsewhere. Refreshing...');
    }
  }
});
```

---

## Performance Best Practices

### 1. Lazy Loading

Always use lazy loading for expensive operations:

```typescript
// Good: Lazy load NLP analysis
const [shouldAnalyze, setShouldAnalyze] = useState(false);

<button onClick={() => setShouldAnalyze(true)}>
  Analyze Word
</button>

{shouldAnalyze && <NlpAnalysis word="example" />}
```

### 2. Memoization

Memoize expensive computations:

```typescript
const words = useMemo(() => {
  return title.split(/\s+/).filter(w => w.length > 0);
}, [title]);

const isDirty = useMemo(() => {
  return !isEqual(currentSenses, persistedSenses);
}, [currentSenses, persistedSenses]);
```

### 3. Virtualization

For large lists, use virtualization:

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

function LargeReferenceList({ items }: { items: ReferenceLink[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 60
  });

  return (
    <div ref={parentRef} style={{ height: '400px', overflow: 'auto' }}>
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
        {virtualizer.getVirtualItems().map(virtualItem => (
          <div
            key={virtualItem.index}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${virtualItem.start}px)`
            }}
          >
            <ReferenceItem item={items[virtualItem.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 4. Debouncing

Debounce search inputs:

```typescript
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

function ReferenceSearch() {
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearch = useDebouncedValue(searchTerm, 300);

  const { data } = useReferenceSearch(debouncedSearch);

  return (
    <input
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      placeholder="Search references..."
    />
  );
}
```

---

## Testing Components

### Unit Testing

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WordSenseSelector } from '@/components/graphs/nlp_concept/WordSenseSelector';

describe('WordSenseSelector', () => {
  it('should load persisted senses', async () => {
    const mockSenses = [
      {
        term: 'bank',
        sense_type: 'wordnet',
        sense_id: 'bank.n.01',
        definition: 'financial institution',
        domain: 'noun.group'
      }
    ];

    render(
      <QueryClientProvider client={new QueryClient()}>
        <WordSenseSelector
          title="bank"
          persistedSenses={mockSenses}
          nodeId="test-id"
        />
      </QueryClientProvider>
    );

    expect(await screen.findByText('bank.n.01')).toBeInTheDocument();
  });

  it('should trigger analysis on expand', async () => {
    const user = userEvent.setup();

    render(
      <QueryClientProvider client={new QueryClient()}>
        <WordSenseSelector
          title="bank"
          persistedSenses={[]}
          nodeId="test-id"
        />
      </QueryClientProvider>
    );

    const wordButton = screen.getByRole('button', { name: /expand.*bank/i });
    await user.click(wordButton);

    expect(await screen.findByText(/analyzing/i)).toBeInTheDocument();
  });
});
```

---

## Accessibility Checklist

- ✅ Semantic HTML elements (`<button>`, `<form>`, etc.)
- ✅ ARIA labels on interactive elements
- ✅ ARIA live regions for dynamic content
- ✅ Keyboard navigation support (Tab, Enter, Space)
- ✅ Focus management after async operations
- ✅ Color contrast ratio ≥ 4.5:1
- ✅ Screen reader announcements for state changes
- ✅ Skip links for keyboard navigation
- ✅ Visible focus indicators
- ✅ Alt text for images/icons

---

## Common Pitfalls

### ❌ Don't: Block UI during analysis

```typescript
// Bad: Blocking entire UI
const analysis = await fetchAnalysis(word);
return <WordChart data={analysis} />;
```

### ✅ Do: Show loading state

```typescript
// Good: Progressive loading with skeleton
if (isAnalyzing) {
  return <Skeleton className="h-40" />;
}
return <WordChart data={analysis} />;
```

### ❌ Don't: Fetch all word analyses upfront

```typescript
// Bad: Fetch analysis for all words immediately
words.forEach(word => fetchAnalysis(word));
```

### ✅ Do: Lazy load per word

```typescript
// Good: Fetch only when user expands
<button onClick={() => analyzeWord(word)}>
  Expand {word}
</button>
```

### ❌ Don't: Ignore error states

```typescript
// Bad: No error handling
const { data } = useWordSenses(nodeId);
```

### ✅ Do: Handle errors gracefully

```typescript
// Good: Comprehensive error handling
const { data, error, isLoading } = useWordSenses(nodeId);

if (isLoading) return <Skeleton />;
if (error) return <ErrorMessage error={error} />;
return <WordSenseDisplay data={data} />;
```

---

## Further Reading

- [Word Sense API Documentation](/documentation/word_sense_api.md)
- [Reference Link API Documentation](/documentation/reference_link_api.md)
- [NLP Processing Guide](/documentation/features/backend/nlp-processing.md)
- [Testing Strategy](/documentation/features/testing/strategy.md)
