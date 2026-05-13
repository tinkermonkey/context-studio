# Test Plan: Command Palette (⌘K)

## Overview

This test plan covers the Command Palette user flow from § 2.5 of the UX specification. The Command Palette is a keyboard-accessible overlay that allows users to run ad-hoc commands and navigate to pages via fuzzy search. The feature is triggered via ⌘K, supports arrow-key navigation, filtering by partial queries, and executing commands via Enter or mouse click.

## Scope

- **Entities involved**: None (palette is a pure navigation/command flow, not data-model related)
- **Pages involved**: All pages (palette is global shell component)
- **External dependencies**: Command Palette Zustand store (`useCommandPaletteStore`), Topbar component, keyboard event handling

## Test Cases

### Test Case 1: Open Palette via ⌘K and Assert Focus

- **Preconditions**: User is on any page (/app or subpage). No factories needed.
- **Steps**:
  1. Press ⌘K
  2. Assert the palette overlay appears
  3. Assert the search input has keyboard focus
  4. Assert the first result in the filtered list (if any exist) is highlighted/active
- **Expected Result**: Palette opens, input focused, first result pre-highlighted
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Palette renders on ⌘K trigger; input auto-focuses; first result receives focus indicator

### Test Case 2: Fuzzy Filter on Typed Query

- **Preconditions**: Palette is open. At least one action is registered in the command palette store.
- **Steps**:
  1. Type a partial query (e.g., "class" to match "New class")
  2. Assert the results list updates to show only matching actions
  3. Assert matching is case-insensitive against both label and description
  4. Type additional characters to narrow results further
  5. Assert results update on each keystroke
- **Expected Result**: Results filter in real-time; non-matching actions are hidden
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Fuzzy search works; active index resets to 0 on query change

### Test Case 3: Keyboard Navigation (↓ Arrow Key)

- **Preconditions**: Palette is open with ≥2 results visible.
- **Steps**:
  1. Assert first result is active (highlighted) initially
  2. Press ↓ (arrow down)
  3. Assert focus moves to second result; second result is now highlighted
  4. Press ↓ again
  5. Assert focus moves to third result
  6. Press ↓ repeatedly until reaching last result
  7. Press ↓ once more
  8. Assert focus does not move beyond the last result (no wrapping)
- **Expected Result**: Down arrow navigates forward through results; focus stops at last item
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Arrow navigation is bounded; active index increments correctly

### Test Case 4: Keyboard Navigation (↑ Arrow Key)

- **Preconditions**: Palette is open with ≥2 results visible. Focus is on result 2 or later.
- **Steps**:
  1. Press ↑ (arrow up)
  2. Assert focus moves backward by one result
  3. Press ↑ repeatedly until reaching first result
  4. Press ↑ once more
  5. Assert focus does not move above first result (no wrapping)
- **Expected Result**: Up arrow navigates backward; focus stops at first item
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Arrow navigation is bounded; active index decrements correctly

### Test Case 5: Execute Command via Enter Key

- **Preconditions**: Palette is open. One result is highlighted. The highlighted action's `onSelect` callback is wired to navigate to a page (e.g., "Go to Classes" → `/app/schema/classes`).
- **Steps**:
  1. Focus a result via arrow keys or filter
  2. Press ↵ (Enter)
  3. Assert the palette closes
  4. Assert the action's `onSelect()` fires (page navigation occurs)
  5. Verify the new page has loaded (URL changes, expected content visible)
- **Expected Result**: Pressing Enter executes the highlighted action and closes the palette
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Enter key triggers action; palette closes on execution

### Test Case 6: Execute Command via Mouse Click

- **Preconditions**: Palette is open with visible results.
- **Steps**:
  1. Click on a result item (not the first one, to test arbitrary selection)
  2. Assert the palette closes
  3. Assert the clicked action's `onSelect()` fires
- **Expected Result**: Click executes the action and closes the palette
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Mouse click on results executes action and closes palette

### Test Case 7: Close Palette via Escape Key

- **Preconditions**: Palette is open.
- **Steps**:
  1. Press Esc
  2. Assert the palette overlay and all contents are hidden
  3. Assert the underlying page is still visible and interactive
- **Expected Result**: Palette closes on Esc; underlying page is accessible
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Esc closes palette; no page navigation occurs

### Test Case 8: Close Palette via Backdrop Click

- **Preconditions**: Palette is open.
- **Steps**:
  1. Click on the backdrop area (semi-transparent overlay, not on the palette dialog itself)
  2. Assert the palette closes
  3. Assert clicking on the palette dialog itself (e.g., the input row) does NOT close the palette
- **Expected Result**: Click outside the dialog closes palette; click inside does not
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Backdrop has stop-propagation; event delegation works correctly

### Test Case 9: Reopen Palette After Close

- **Preconditions**: Palette was previously opened and closed.
- **Steps**:
  1. Press ⌘K to close the open palette (toggle off)
  2. Assert palette is hidden
  3. Press ⌘K again to reopen
  4. Assert palette opens again
  5. Assert input is focused; first result is highlighted
  6. Assert query from previous session is cleared
- **Expected Result**: Palette can be reopened; state resets (empty query, first result active)
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Toggle works both directions; state resets on each open

### Test Case 10: Reopen via Topbar ⌘K Chip

- **Preconditions**: Palette is closed. Topbar is visible with the ⌘K chip button.
- **Steps**:
  1. Click the ⌘K chip button in the Topbar
  2. Assert the palette opens
  3. Assert input is focused; first result is highlighted
- **Expected Result**: Click on Topbar chip opens palette
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Topbar button is wired to `openPalette()` store action

### Test Case 11: Empty State (No Results Match Query)

- **Preconditions**: Palette is open with some actions registered.
- **Steps**:
  1. Type a query that matches no registered actions (e.g., "xyzzzzzz")
  2. Assert the results area is replaced with an empty state message
  3. Assert the message reads: `No results for "{query}"` (query is shown)
  4. Assert the palette remains open (does not auto-close)
  5. Type additional characters or backspace to change the query
  6. If a new query matches results, assert results re-appear
- **Expected Result**: No-match state shows user-friendly message; palette stays open
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Empty state is rendered; message reflects the typed query

### Test Case 12: Esc Button in Palette Input Row

- **Preconditions**: Palette is open.
- **Steps**:
  1. Locate the "esc" button/kbd in the input row (shown as a visual hint)
  2. Click on it
  3. Assert the palette closes
- **Expected Result**: Clicking the Esc kbd button closes the palette
- **Selectors Used**: TBD (see Open Questions)
- **Invariants Verified**: Esc button is clickable and functional

## Coverage Analysis

### CRUD Coverage

- **Create**: Not applicable (palette is a navigation and command surface, not a data editor)
- **Read**: Palette reads registered actions from the command palette store
- **Update**: Not applicable
- **Delete**: Not applicable

### Edge Cases

- **Concurrency**: Multiple ⌘K presses while palette is opening (debounce not critical for this surface)
- **Empty actions list**: Palette should render with empty results state if no actions are registered
- **Very long action labels**: Should wrap or truncate gracefully within palette-item width
- **Many results**: Scroll behavior (palette-results is scrollable)
- **Rapid filter changes**: Typing quickly should not cause jank; active index should reset on each query change

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions (component uses `setTimeout(..., 0)` for focus, which is acceptable for browser task scheduling, not a test timeout)
- ✓ No hardcoded UUIDs (palette uses store-provided action IDs, not generated IDs)
- ✓ No vacuous assertions (all assertions check observable DOM state or user-facing behavior)
- ✓ All selectors listed must exist in the registry OR be pattern-based (awaiting resolution)
- ✓ No invented field names (palette does not use entity fields from types.ts; it works with PaletteAction interface from the store)

## Open Questions

**BLOCKING: The Command Palette component is not instrumented with `data-testid` selectors.** The following selectors are needed but do not exist in `/workspace/ux/selector-registry.yaml`:

1. **`command-palette`** — Root container for the entire palette dialog (the `.palette` div with `role="dialog"`)
2. **`command-palette-backdrop`** — The semi-transparent backdrop (`.palette-backdrop` div) that, when clicked, closes the palette
3. **`command-palette-input`** — The search input field where the user types the query
4. **`command-palette-results`** — Container for the results list (`.palette-results` div)
5. **`command-palette-empty-state`** — The "No results" message container (`.palette-empty` div)
6. **`command-palette-item-*`** — Individual result button items (pattern matches `command-palette-item-{actionId}` for each palette action; the action's ID from the store)
7. **`command-palette-item-active`** — CSS class or state indicator that marks the currently focused/highlighted result (could be implemented as `[data-testid^="command-palette-item-"][aria-selected="true"]` or a dedicated testid)
8. **`topbar-palette-button`** — The ⌘K chip button in the Topbar that opens the palette (button with Search icon and "⌘K" label in Topbar)
9. **`command-palette-esc-button`** — The "esc" button/kbd in the palette input row

**Action required**: Before test generation can proceed, the following must be done:

1. Add the above `data-testid` attributes to the CommandPalette component (`/workspace/ux/src/components/shell/CommandPalette.tsx`)
2. Add the `topbar-palette-button` testid to the Topbar component (`/workspace/ux/src/components/shell/Topbar.tsx`)
3. Register all nine selectors in `/workspace/ux/selector-registry.yaml` with appropriate descriptions
4. Run `npm run validate-selectors` to verify the contract is satisfied
5. Once selectors are in place, resume test generation with this plan

**Note**: The component implementation is complete and functional. Only the test instrumentation (data-testid attributes) is missing. No application code changes are required beyond adding `data-testid` attributes.

## Factory Usage

No factories are required for this test plan. The Command Palette is a shell component that does not create, read, update, or delete domain entities. It consumes a list of PaletteAction objects from the Zustand command palette store, which are registered by various parts of the application (e.g., navigation routes).

**Cleanup**: No `clearTestData()` call is needed after Command Palette tests, as the palette does not modify any persisted state.

