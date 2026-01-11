# Word Sense Selection User Guide

## What is Word Sense Selection?

Word sense selection allows you to disambiguate the meaning of words in multi-word terms by choosing specific dictionary definitions. This helps Context Studio understand precisely what you mean when using words that have multiple meanings.

### Why is this important?

Many words have multiple meanings. For example:
- **"bank"** could mean a financial institution OR the side of a river
- **"spring"** could mean a season OR a coiled metal object OR a source of water
- **"mouse"** could mean a computer device OR a small rodent

By selecting the correct word sense, you help Context Studio:
- Generate more accurate definitions
- Improve semantic search results
- Build better knowledge graphs
- Align with external knowledge bases

---

## Getting Started

### Accessing Word Sense Selection

1. Navigate to any term in your knowledge graph
2. Scroll to the **Word Sense Analysis** section
3. You'll see each word in the term's title displayed as a separate card

### Understanding the Interface

**Word Cards**
- Each word appears in its own card
- Cards with blue backgrounds have selected senses
- Cards with gray backgrounds have no selection yet
- Click any word to expand and view sense options

**Save Button**
- Appears only when you've made changes
- Blue button in the top-right corner
- Saves all word sense selections for the current term

**Helper Text**
- Bottom of the screen
- Provides keyboard shortcuts and usage tips

---

## Selecting Word Senses

### Step-by-Step Guide

**1. Click a word to expand**

Click on any word card (e.g., "bank") to view available senses.

The system will:
- Analyze the word using NLP (Natural Language Processing)
- Fetch definitions from WordNet
- Display all possible meanings

**2. Review the sense options**

Each sense shows:
- **Sense ID**: Technical identifier (e.g., "bank.n.01")
- **Definition**: Clear explanation of the meaning
- **Part of Speech**: Noun, verb, adjective, etc.
- **Domain**: Semantic category (e.g., "noun.group", "noun.object")

Example for "bank":
- `bank.n.01` - a financial institution that accepts deposits
- `bank.n.02` - sloping land beside a body of water
- `bank.n.03` - a supply or stock held in reserve
- `bank.v.01` - to have confidence or faith in
- `bank.v.02` - to enclose with a bank

**3. Click a sense to select it**

- Click on any sense definition to select it
- The word card will turn blue to indicate selection
- The sense ID will appear as a badge on the word

**4. Save your selections**

- Click the **"Save Word Senses"** button
- You'll see a success message
- Changes are saved to the database

---

## Practical Examples

### Example 1: Financial Term

**Term:** "bank account"

**Steps:**
1. Click "bank" → Select `bank.n.01` (financial institution)
2. Click "account" → Select `account.n.02` (financial account)
3. Click "Save Word Senses"

**Result:** Context Studio now knows you're talking about a financial account, not a land description or narrative account.

---

### Example 2: Technical Term

**Term:** "memory cache"

**Steps:**
1. Click "memory" → Select `memory.n.04` (computer memory)
   - NOT `memory.n.01` (human memory/recall)
2. Click "cache" → Select `cache.n.02` (computer cache)
   - NOT `cache.n.01` (hiding place)
3. Click "Save Word Senses"

**Result:** Disambiguated as a computer science term, not general vocabulary.

---

### Example 3: Scientific Term

**Term:** "gene expression"

**Steps:**
1. Click "gene" → Select `gene.n.01` (biological hereditary unit)
2. Click "expression" → Select `expression.n.03` (manifestation)
   - NOT `expression.n.01` (facial expression)
   - NOT `expression.n.04` (mathematical expression)
3. Click "Save Word Senses"

**Result:** Clarified as a biological process, not mathematics or communication.

---

## Advanced Features

### Lazy Loading

To improve performance, word analysis happens on-demand:

- Words are only analyzed when you click to expand them
- Analysis results are cached for the session
- No unnecessary API calls for words you don't expand

**Tip:** You don't need to expand every word. Only disambiguate words that have multiple common meanings.

---

### Conservative Merging

When you save word senses:

- Only the words you've selected are updated
- Other words keep their previous selections
- You can update senses for individual words without affecting others

**Example:**

Initial state:
- "bank" → `bank.n.01` (financial institution)
- "account" → `account.n.01` (narrative)

Update only "account":
- Select `account.n.02` (financial account)
- Click Save

Final state:
- "bank" → `bank.n.01` (unchanged)
- "account" → `account.n.02` (updated)

---

### Deselecting a Sense

To remove a word sense selection:

1. Click the word to expand
2. Click the currently selected sense again
3. The selection will be cleared (card turns gray)
4. Click "Save Word Senses" to persist

---

### Handling Conflicts

If another user modifies the word senses while you're editing:

1. You'll see a warning message when you try to save
2. The system automatically refreshes to show the latest data
3. Your unsaved changes remain visible
4. Review the updated data and save again if needed

**Message:** "Word senses were modified elsewhere. Your changes were not saved. Please review the current values and try again."

---

## Keyboard Navigation

For efficient navigation without a mouse:

| Key | Action |
|-----|--------|
| Tab | Move between word cards |
| Shift + Tab | Move backwards |
| Enter | Expand/collapse word |
| Space | Expand/collapse word |
| Esc | Collapse expanded word |

**Focus Management:**
- After saving, focus returns to the main container
- On error, focus returns to the Save button
- Clear visual focus indicators show your position

---

## Screen Reader Support

Context Studio is fully accessible with screen readers:

- **Word Cards:** Announced as "Word sense for {word}"
- **Expand Buttons:** Announced as "Expand sense options for {word}" or "Collapse sense options for {word}"
- **Selected Senses:** Announced with sense ID
- **Save Button:** Announced as "Save word senses" or "Saving word senses"
- **Loading States:** Announced as "Loading word sense analysis"
- **Errors:** Announced with alert role

---

## Mobile and Tablet Support

The interface adapts to your screen size:

| Screen Size | Columns | Description |
|------------|---------|-------------|
| Mobile (< 640px) | 1 | Single column, full width |
| Tablet (640px - 1024px) | 2 | Two columns side-by-side |
| Desktop (1024px - 1280px) | 3 | Three columns |
| Large Desktop (> 1280px) | 4 | Four columns |

**Touch Support:**
- Tap any word to expand
- Tap a sense to select
- Tap outside to collapse
- All interactions work with touch and mouse

---

## Troubleshooting

### Problem: Word won't expand

**Possible causes:**
- Network connectivity issue
- NLP service temporarily unavailable

**Solutions:**
1. Check your internet connection
2. Wait a few seconds and try again
3. Refresh the page if the problem persists

---

### Problem: Can't save changes

**Possible causes:**
- Invalid word sense format
- Network error
- Concurrent edit conflict

**Solutions:**
1. Check for error messages
2. Ensure you're connected to the internet
3. If conflict detected, review the refreshed data and save again

---

### Problem: Analysis takes too long

**Expected behavior:**
- First analysis per word: 1-3 seconds
- Cached analysis: Instant

**If slower:**
1. Check network connection
2. Large multi-word titles may take longer
3. Contact support if consistently slow

---

### Problem: Selected sense disappeared

**Possible causes:**
- Changes weren't saved
- Another user modified the term
- Page was refreshed before saving

**Solutions:**
1. Always click "Save Word Senses" after making selections
2. Look for the save button - if visible, changes aren't saved yet
3. Check for any error notifications

---

## Best Practices

### 1. Only disambiguate ambiguous words

Not every word needs a sense selection:
- **Disambiguate:** Words with common multiple meanings (e.g., "bank", "spring", "light")
- **Skip:** Unambiguous words (e.g., "specific", "particular", "unique")

### 2. Consider context

Choose senses that match your domain:
- Financial domain: "bank" → financial institution
- Geography domain: "bank" → land beside water
- Aviation domain: "bank" → tilting maneuver

### 3. Check parent/child relationships

Ensure word senses align with related terms:
- Parent domain: "Finance"
- Child term: "bank account"
- Select financial senses for consistency

### 4. Save frequently

Don't wait to save all selections:
- Save after completing each term
- Avoid losing work due to conflicts or disconnects
- Saves are fast and non-disruptive

### 5. Review generated definitions

After saving word senses:
- Check if the generated definition improved
- If not, consider different sense selections
- Iterate to find the best combinations

---

## Integration with Other Features

### Definition Generation

Word senses improve AI-generated definitions:
- LLM uses selected senses as context
- Definitions become more precise
- Fewer revisions needed

### Semantic Search

Better search results:
- Queries match conceptual meaning, not just keywords
- Find related terms even with different wording
- Cross-reference with external knowledge bases

### RAG (Retrieval-Augmented Generation)

Enhanced retrieval:
- Context Studio understands query intent
- Retrieves relevant documents based on meaning
- Generates more accurate responses

---

## Frequently Asked Questions

**Q: Do I need to select senses for all words?**

A: No. Only disambiguate words with multiple common meanings. Single-meaning words don't need selection.

**Q: What if the correct sense isn't listed?**

A: WordNet covers most common English words. If a sense is missing:
1. Choose the closest available sense
2. Provide feedback to help us improve coverage
3. Use the definition field to clarify meaning

**Q: Can I change word senses later?**

A: Yes. You can update word sense selections at any time. Simply:
1. Navigate to the term
2. Change the selections
3. Click "Save Word Senses"

**Q: Will changing word senses affect other terms?**

A: No. Word sense selections are specific to each term. Changing one term doesn't affect others.

**Q: What happens if I select the wrong sense?**

A: No problem. You can:
1. Click the word again to expand
2. Select a different sense
3. Save the new selection

Your previous selection is replaced with the new one.

**Q: How do word senses relate to external ontologies?**

A: WordNet sense IDs can be mapped to:
- Schema.org types
- Wikidata entities
- DBpedia resources
- Other standard vocabularies

This enables interoperability and knowledge graph alignment.

---

## Getting Help

If you encounter issues or have questions:

1. **Check this guide** for common solutions
2. **Review error messages** for specific guidance
3. **Contact support** with:
   - Term ID or title
   - Screenshot of the issue
   - Steps to reproduce
4. **Provide feedback** to help improve the feature

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-11-08 | Initial user guide for word sense selection |

---

## Related Resources

- [Word Sense API Documentation](/documentation/word_sense_api.md)
- [Component Usage Guide](/documentation/component_usage.md)
- [Knowledge Graph Management](/documentation/features/backend/knowledge-graph-management.md)
- [NLP Processing](/documentation/features/backend/nlp-processing.md)
