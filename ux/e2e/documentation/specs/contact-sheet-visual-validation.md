# Test Plan: Contact Sheet Visual Validation

## Overview

This test validates the visual rendering of the Contact Sheet component gallery in both light and dark canvas modes. The Contact Sheet is a design system showcase page that displays all reusable UI components with various configurations. The test verifies that all named sections render correctly and that the dark/light mode toggle properly switches the canvas color theme without breaking component layouts.

## Scope

- **Entities involved**: None (Contact Sheet is a static gallery, no data model entities)
- **Pages involved**: `/app/contact-sheet`
- **External dependencies**: No API calls or external services required
- **Test Strategy**: Visual regression detection using Playwright screenshot comparisons

## Test Cases

### Test Case 1: Navigate to Contact Sheet and Verify Initial Light Mode Rendering

**Preconditions**: User is able to navigate to the app

**Steps**:

1. Navigate to `/app/contact-sheet`
2. Wait for page to load completely using `waitForLoadState("networkidle")`
3. Verify the page title "Contact Sheet" is visible

**Expected Result**:

- Page loads successfully
- Page title is visible
- All sections are rendered and visible
- Canvas is in light mode (initial state)

**Selectors Used**: (title is text-based for this step only, no action needed)

**Invariants Verified**:

- Contact Sheet page route is accessible
- Page renders without errors in light mode

---

### Test Case 2: Verify All 14 Named Sections Render in Light Mode

**Preconditions**: User is on `/app/contact-sheet` in light mode

**Steps**:

1. Verify visibility of `contact-sheet-buttons` section
2. Verify visibility of `contact-sheet-chips` section
3. Verify visibility of `contact-sheet-stat-tiles` section
4. Verify visibility of `contact-sheet-tabs` section
5. Verify visibility of `contact-sheet-form-inputs` section
6. Verify visibility of `contact-sheet-panel` section
7. Verify visibility of `contact-sheet-table` section
8. Verify visibility of `contact-sheet-hierarchy-tree` section
9. Verify visibility of `contact-sheet-pipeline-card` section
10. Verify visibility of `contact-sheet-toasts` section
11. Verify visibility of `contact-sheet-modal` section
12. Verify visibility of `contact-sheet-drawer` section
13. Verify visibility of `contact-sheet-schema-components` section
14. Verify visibility of `contact-sheet-intent-states` section

**Expected Result**:

- All 14 sections are visible on the page
- Each section renders without layout issues
- No visual corruption or overlapping elements
- All component variants within sections are properly displayed

**Selectors Used**: `contact-sheet-buttons`, `contact-sheet-chips`, `contact-sheet-stat-tiles`, `contact-sheet-tabs`, `contact-sheet-form-inputs`, `contact-sheet-panel`, `contact-sheet-table`, `contact-sheet-hierarchy-tree`, `contact-sheet-pipeline-card`, `contact-sheet-toasts`, `contact-sheet-modal`, `contact-sheet-drawer`, `contact-sheet-schema-components`, `contact-sheet-intent-states`

**Invariants Verified**:

- All component sections are present in the DOM
- All sections are in the viewport (scrollable to each)
- No console errors during rendering

---

### Test Case 3: Take Full-Page Screenshot in Light Mode

**Preconditions**: All sections verified as visible in Test Case 2

**Steps**:

1. Scroll to the top of the page
2. Capture a full-page screenshot with `page.screenshot({ fullPage: true })` or use Playwright's visual snapshot feature for the entire page
3. Store reference screenshot for light mode baseline

**Expected Result**:

- Full-page screenshot is captured successfully
- Screenshot shows all sections in light mode
- Visual baseline established for light mode regression detection

**Selectors Used**: (N/A - full page screenshot)

**Invariants Verified**:

- Screenshot captures the complete page layout
- Light mode colors are correctly applied (light backgrounds, dark text)

---

### Test Case 4: Capture Section-by-Section Screenshots in Light Mode

**Preconditions**: Page is in light mode, all sections are visible

**Steps**:

1. For each of the 14 named sections, capture a section-specific screenshot:
   - `contact-sheet-buttons` → screenshot of buttons section
   - `contact-sheet-chips` → screenshot of chips section
   - `contact-sheet-stat-tiles` → screenshot of stat tiles section
   - `contact-sheet-tabs` → screenshot of tabs section
   - `contact-sheet-form-inputs` → screenshot of form inputs section
   - `contact-sheet-panel` → screenshot of panel section
   - `contact-sheet-table` → screenshot of table section
   - `contact-sheet-hierarchy-tree` → screenshot of hierarchy tree section
   - `contact-sheet-pipeline-card` → screenshot of pipeline card section
   - `contact-sheet-toasts` → screenshot of toasts section
   - `contact-sheet-modal` → screenshot of modal section
   - `contact-sheet-drawer` → screenshot of drawer section
   - `contact-sheet-schema-components` → screenshot of schema components section
   - `contact-sheet-intent-states` → screenshot of intent states section

2. Use `page.locator('[data-testid="<section-id>"]').screenshot()` for each section

**Expected Result**:

- All 14 section screenshots are captured successfully
- Each screenshot shows the section with proper styling and layout
- No visual glitches or rendering artifacts

**Selectors Used**: All 14 contact-sheet-\* selectors (see step 1)

**Invariants Verified**:

- Each section is rendered with correct typography, spacing, and colors
- Component variants are properly displayed (different button states, chip colors, etc.)
- Light mode baseline established for each section

---

### Test Case 5: Toggle to Dark Canvas Mode

**Preconditions**: User is on `/app/contact-sheet` in light mode

**Steps**:

1. Locate the canvas mode toggle button with selector `contact-sheet-canvas-toggle`
2. Click the toggle button
3. Wait for animations/transitions to complete using `waitForTimeout(500)` or wait for visual change
4. Verify the button text changes from "Dark canvas" to "Light canvas" (or vice versa)

**Expected Result**:

- Canvas mode toggle is clickable
- Canvas switches to dark mode immediately
- Button text updates to reflect new mode
- No errors occur during mode transition

**Selectors Used**: `contact-sheet-canvas-toggle`

**Invariants Verified**:

- Toggle button is accessible and functional
- Dark mode CSS variables are applied to the page
- Mode change does not reload the page

---

### Test Case 6: Verify All Sections Still Render in Dark Mode

**Preconditions**: User is on `/app/contact-sheet` in dark mode (toggled from light mode in Test Case 5)

**Steps**:

1. Verify visibility of `contact-sheet-buttons` section in dark mode
2. Verify visibility of `contact-sheet-chips` section in dark mode
3. Verify visibility of `contact-sheet-stat-tiles` section in dark mode
4. Verify visibility of `contact-sheet-tabs` section in dark mode
5. Verify visibility of `contact-sheet-form-inputs` section in dark mode
6. Verify visibility of `contact-sheet-panel` section in dark mode
7. Verify visibility of `contact-sheet-table` section in dark mode
8. Verify visibility of `contact-sheet-hierarchy-tree` section in dark mode
9. Verify visibility of `contact-sheet-pipeline-card` section in dark mode
10. Verify visibility of `contact-sheet-toasts` section in dark mode
11. Verify visibility of `contact-sheet-modal` section in dark mode
12. Verify visibility of `contact-sheet-drawer` section in dark mode
13. Verify visibility of `contact-sheet-schema-components` section in dark mode
14. Verify visibility of `contact-sheet-intent-states` section in dark mode

**Expected Result**:

- All 14 sections are still visible in dark mode
- No sections are hidden or partially obscured
- Colors are inverted/adjusted correctly for dark theme
- All interactive components remain functional

**Selectors Used**: `contact-sheet-buttons`, `contact-sheet-chips`, `contact-sheet-stat-tiles`, `contact-sheet-tabs`, `contact-sheet-form-inputs`, `contact-sheet-panel`, `contact-sheet-table`, `contact-sheet-hierarchy-tree`, `contact-sheet-pipeline-card`, `contact-sheet-toasts`, `contact-sheet-modal`, `contact-sheet-drawer`, `contact-sheet-schema-components`, `contact-sheet-intent-states`

**Invariants Verified**:

- All sections remain visible in dark mode
- Contrast is sufficient for readability in dark mode
- Dark mode CSS variables are correctly applied
- No layout shift or reflow on mode toggle

---

### Test Case 7: Take Full-Page Screenshot in Dark Mode

**Preconditions**: User is on `/app/contact-sheet` in dark mode, all sections verified as visible

**Steps**:

1. Scroll to the top of the page
2. Capture a full-page screenshot with `page.screenshot({ fullPage: true })` or use Playwright's visual snapshot feature for the entire page
3. Store reference screenshot for dark mode baseline

**Expected Result**:

- Full-page screenshot is captured successfully in dark mode
- Screenshot shows all sections with dark mode colors
- Visual baseline established for dark mode regression detection

**Selectors Used**: (N/A - full page screenshot)

**Invariants Verified**:

- Screenshot captures the complete page layout in dark mode
- Dark mode colors are correctly applied (dark backgrounds, light text)

---

### Test Case 8: Capture Section-by-Section Screenshots in Dark Mode

**Preconditions**: Page is in dark mode, all sections are visible

**Steps**:

1. For each of the 14 named sections, capture a section-specific screenshot:
   - `contact-sheet-buttons` → screenshot of buttons section in dark mode
   - `contact-sheet-chips` → screenshot of chips section in dark mode
   - `contact-sheet-stat-tiles` → screenshot of stat tiles section in dark mode
   - `contact-sheet-tabs` → screenshot of tabs section in dark mode
   - `contact-sheet-form-inputs` → screenshot of form inputs section in dark mode
   - `contact-sheet-panel` → screenshot of panel section in dark mode
   - `contact-sheet-table` → screenshot of table section in dark mode
   - `contact-sheet-hierarchy-tree` → screenshot of hierarchy tree section in dark mode
   - `contact-sheet-pipeline-card` → screenshot of pipeline card section in dark mode
   - `contact-sheet-toasts` → screenshot of toasts section in dark mode
   - `contact-sheet-modal` → screenshot of modal section in dark mode
   - `contact-sheet-drawer` → screenshot of drawer section in dark mode
   - `contact-sheet-schema-components` → screenshot of schema components section in dark mode
   - `contact-sheet-intent-states` → screenshot of intent states section in dark mode

2. Use `page.locator('[data-testid="<section-id>"]').screenshot()` for each section

**Expected Result**:

- All 14 section screenshots are captured successfully in dark mode
- Each screenshot shows the section with proper dark mode styling and layout
- No visual glitches or rendering artifacts in dark mode
- Colors are inverted/adjusted correctly from light mode baseline

**Selectors Used**: All 14 contact-sheet-\* selectors (see step 1)

**Invariants Verified**:

- Each section is rendered with correct dark mode typography, spacing, and colors
- Component color schemes adapt correctly to dark theme
- Dark mode baseline established for each section

---

### Test Case 9: Toggle Back to Light Mode and Verify Consistency

**Preconditions**: User is on `/app/contact-sheet` in dark mode

**Steps**:

1. Click the canvas mode toggle button with selector `contact-sheet-canvas-toggle`
2. Wait for animations/transitions to complete
3. Verify the page returns to light mode
4. Verify button text changes back to "Dark canvas"

**Expected Result**:

- Canvas switches back to light mode
- Light mode styling is restored
- Button text reflects the new mode
- Page state is consistent with initial light mode (Test Case 1–2)

**Selectors Used**: `contact-sheet-canvas-toggle`

**Invariants Verified**:

- Mode toggle is bi-directional and repeatable
- No stale styles remain from dark mode
- Page returns to initial light mode state

---

## Coverage Analysis

### Visual Regression Coverage

- **Full-page light mode**: ✓ Test Case 3 captures baseline
- **Full-page dark mode**: ✓ Test Case 7 captures baseline
- **Section-by-section light mode**: ✓ Test Case 4 captures 14 section baselines
- **Section-by-section dark mode**: ✓ Test Case 8 captures 14 section baselines
- **Mode toggle functionality**: ✓ Test Cases 5 and 9 verify toggle behavior

### Component Coverage

All 14 sections and their components are tested:

1. Buttons — primary, accent, ghost, danger variants; sizes and disabled states
2. Chips — color variants (cyan, amber, violet, emerald, rose, gray, default)
3. Stat Tiles — colored tiles with labels, values, and sub-text
4. Tabs — tab navigation component with active state
5. Form Inputs — text input, mono input, textarea, select, error state
6. Panel — card with header, actions, and body content
7. Table — data table with headers, rows, chips, and actions
8. Hierarchy Tree — tree structure with depth levels and badges
9. Pipeline Card — flow diagram with source, extract, resolve, write nodes
10. Toasts — notification system (buttons to trigger success/error toasts)
11. Modal — dialog with title, subtitle, form fields, and footer
12. Drawer — side panel with title and key-value content display
13. Schema Components — FilterBar + SchemaTable + Drawer layout combo
14. Intent States — success, warning, failure, info banner states

### Edge Cases

- **Mode persistence**: Mode toggle state is tested for consistency across toggles
- **Visual regression**: Pixel-level comparison in both light and dark modes ensures no unintended styling changes
- **Accessibility**: All sections remain visually accessible in both modes (contrast, spacing)
- **Component layout stability**: Layout does not shift or reflow on mode toggle

### Anti-Pattern Validations

- ✓ No hardcoded UUIDs (Contact Sheet uses static mock data only)
- ✓ No invented selectors (all selectors verified in `ux/selector-registry.yaml`)
- ✓ No vacuous assertions (every visibility check validates meaningful rendering)
- ✓ No text-based selectors for dynamic content (use `data-testid` selectors only)
- ✓ Minimal use of `waitForTimeout()` — transitions use reasonable waits or `waitForLoadState()`
- ✓ No cleanup required (Contact Sheet is read-only, no test data created/modified)

---

## Open Questions

None. All required selectors are documented in `ux/selector-registry.yaml`:

- ✓ `contact-sheet-buttons` through `contact-sheet-intent-states` (14 sections)
- ✓ `contact-sheet-canvas-toggle` (mode toggle control)

---

## Factory Usage

**No factories required** — Contact Sheet is a static design system gallery with no external data dependencies. All content is hardcoded React components with mock data. Test setup is simply navigation to the page.

---

## Notes for Generator

- **Screenshot naming**: Use Playwright's snapshot naming convention (e.g., `contact-sheet-buttons-light.png`, `contact-sheet-buttons-dark.png`)
- **Viewport**: Use a consistent viewport size (e.g., 1280x720) for all screenshot comparisons to ensure visual consistency
- **Animations**: Use `waitForTimeout(500)` after canvas toggle to allow CSS transitions to complete before capturing screenshots
- **Full-page screenshots**: May require scrolling; ensure all sections are captured in the viewport or use `fullPage: true`
- **Section screenshots**: Use `locator.screenshot()` to capture only the relevant section element
- **Comparison strategy**: Store light mode baseline first (Test Cases 3–4), then dark mode baseline (Test Cases 7–8). The test generator should use Playwright's built-in `toHaveScreenshot()` for visual regression detection
- **Tolerance**: Set a reasonable pixel difference tolerance (e.g., 0.1% or 1% depending on CI environment variability)
- **No dynamic assertions**: All assertions are based on visibility and visual state, not on dynamic content or timing-dependent behaviors
