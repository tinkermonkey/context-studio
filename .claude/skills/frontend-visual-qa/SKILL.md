---
name: frontend-visual-qa
description: Run visual QA on a completed frontend page or component. Takes screenshots in both canvas modes, verifies layout composition, form validation timing, and test assertion completeness. Use after implementing any new page, drawer, or form — before considering the work done.
user-invocable: true
---

You are performing visual QA on a Context Studio frontend implementation. Work through every section below in order. Stop and report any failure immediately rather than continuing.

The user will tell you which page or component to check. If they don't, ask.

---

## 0. Prerequisites

1. Confirm the Vite dev server is running (`lsof -i :3100` or check `/tmp/vite-dev.log`). Start it if not: `cd ux && npm run dev &> /tmp/vite-dev.log &`, then wait ~5s.
2. Confirm the backend is running: `lsof -i :8000`. The visual checks that require live data need it.
3. Navigate to the page under test in the browser and select a workspace if the workspace picker appears.
4. Save all screenshots to `/screenshots/` at the repo root (gitignored).

---

## 1. Light Canvas Screenshots

Take a screenshot of each state that applies to the page. Save with descriptive names (`<page>-empty.png`, `<page>-populated.png`, etc.).

**Required states to capture:**
- Empty state (no data)
- Loading state (if observable — add a network delay via DevTools if needed)
- Error state (if observable — block the API request via DevTools)
- Populated state (at least one real record)
- Populated state with drawer open (if the page has a detail drawer)
- Populated state with a modal open (if the page has a create/edit modal)

For each screenshot, verify visually:

- [ ] Page title is present and correctly sized (`var(--text-xl)`)
- [ ] Breadcrumb in topbar matches the route (e.g. "Data / Individuals")
- [ ] Empty state: title, description, and CTA buttons are centered and readable
- [ ] Table: ID column uses `font-family: var(--font-mono)`, name column is a cyan link, chips render correctly
- [ ] Drawer or modal: fields are readable, labels are present, submit button is labeled correctly

---

## 2. Dark Canvas Screenshots

Toggle dark canvas (the moon icon in the topbar) and re-take the same screenshots from section 1.

For each dark canvas screenshot, verify:

- [ ] Canvas background has switched to dark (`--canvas-bg`, approximately `#111827`)
- [ ] Table rows use dark surface colors — not white or hardcoded light values
- [ ] Chips use dark-tinted pastels (not the same hue as light mode)
- [ ] Primary button has flipped to cyan (`--cyan-500` background, dark text)
- [ ] Skeleton states use `--canvas-bg-2`, not hardcoded colors
- [ ] Cyan name links are still readable against the dark canvas

Toggle back to light canvas when done.

---

## 3. Layout Composition Check

This section enforces structural patterns. A wrong layout passes all unit tests but is visually broken.

### 3a. Pages with a detail drawer

Any page that opens a detail drawer when a row is selected **must** render the table and drawer side-by-side using the `split-2` CSS grid (`1fr 380px`), not stacked vertically.

To verify: select a row, then run in the browser console:
```js
document.querySelector('[data-testid="schema-page-layout"]') !== null
// or
document.querySelector('.split-2') !== null
```

Both must return `true`. If either returns `false`, the page is missing `SchemaPageLayout` and the drawer is stacking below the table. **This is a bug — fix before proceeding.**

The pattern to use:
```tsx
<SchemaPageLayout
  data={filteredData}
  selectedId={selectedId}
  renderDrawerContent={(entity) => (
    <MyDrawer ... />
  )}
>
  <MyTable ... />
</SchemaPageLayout>
```

### 3b. Sidebar remains dark in dark canvas

The shell sidebar must never adopt the canvas background color. Run:
```js
getComputedStyle(document.querySelector('aside')).backgroundColor
```
The result must be a dark value (~`rgb(11, 15, 20)`) in both canvas modes.

---

## 4. Form Validation Timing Check

Every form in the page must satisfy all three of these behaviors. Test each form (create modal, edit modal, inline form):

**4a. Error appears on failed submit**
1. Open the form
2. Leave required fields empty
3. Click the submit button
4. ✅ Error message appears immediately

**4b. Error clears on first keystroke (onChange)**
1. With the error visible from step 4a, type a single character into the invalid field
2. ✅ Error message disappears *before* the field loses focus
3. ❌ If the error only clears after tabbing away (onBlur), this is a bug

The fix is always the same — add error clearing to the `onChange` handler:
```tsx
onChange={(e) => {
  setValue(e.target.value);
  setFieldError(undefined);  // must be here, not only in onBlur
}}
```

**4c. Error reappears on blur when field is empty again**
1. Clear the field content
2. Click elsewhere (blur the field)
3. ✅ Error message reappears

---

## 5. Unit Test Assertion Completeness

After the visual checks, review the test file for the page or component. Verify these specific patterns:

### 5a. Layout assertion when drawer is used
If the page uses a drawer, the populated-state test suite must include:
```ts
// When a row is selected, the split-2 layout must be present
expect(container.querySelector('[data-testid="schema-page-layout"]')).toBeInTheDocument();
```

If this assertion is absent, add it.

### 5b. Validation error absence assertion
Every test named "clears [field] error" or "error disappears" must assert the *absence* of the error text, not just that the input value changed:
```ts
// After typing, both of these must be present:
expect(inputEl.value).toBe("expected value");                         // value changed ✓
expect(screen.queryByText("Field is required")).not.toBeInTheDocument(); // error gone ✓
```

If a test only checks the value but not the error absence, add the second assertion.

---

## 6. Typecheck

```bash
cd ux && npm run typecheck
```

Must exit 0. Report any errors.

---

## 7. Report

After completing all sections, report:

```
## Visual QA Report — <Page Name>

### Screenshots taken
- <list of files saved to /screenshots/>

### Light canvas
- [ ] Empty state: pass / fail / n/a
- [ ] Loading state: pass / fail / n/a
- [ ] Error state: pass / fail / n/a
- [ ] Populated state: pass / fail / n/a
- [ ] Drawer open: pass / fail / n/a
- [ ] Modal open: pass / fail / n/a

### Dark canvas
- [ ] Canvas background: pass / fail
- [ ] Table surfaces: pass / fail
- [ ] Chips: pass / fail
- [ ] Primary button: pass / fail
- [ ] Skeletons: pass / fail

### Layout composition
- [ ] split-2 grid present when drawer open: pass / fail / n/a

### Form validation timing
- [ ] Error appears on submit: pass / fail / n/a
- [ ] Error clears onChange: pass / fail / n/a
- [ ] Error reappears on blur: pass / fail / n/a

### Test assertions
- [ ] Layout assertion present: pass / fail / n/a
- [ ] Error absence assertion present: pass / fail / n/a

### Typecheck
- [ ] tsc --noEmit: pass / fail

### Bugs found
<list any failures above, or "None">
```
