---
name: heimdall-inputs
description: Heimdall component guide for Inputs: TextInput, TextArea, NumberInput, Select, TriState, Field, FilterDropdown, EntityPicker, KeyValueEditor, OrderedList, RelationshipBuilder
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## TextInput

Single-line text input with optional monospace font and error state.

```tsx
import { TextInput } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mono` | `boolean` | `false` | Use JetBrains Mono, for identifiers |
| `error` | `boolean` | `false` | Rose border and focus ring |
| `...inputProps` | | | Remaining props spread onto the `<input>` |

### Usage

```tsx
<TextInput placeholder="Enter value…" />
```

```tsx
<TextInput value={name} onChange={(e) => setName(e.target.value)} />
<TextInput placeholder="cls_4f3a" mono />
<TextInput value={name} onChange={(e) => setName(e.target.value)} error aria-invalid />
<TextInput placeholder="user@example.com" type="email" />
```

### Gotchas

- Renders `type="text"` by default; a `type` prop overrides it (`email`, `password`, `search`).
- `error` is visual only. Set `aria-invalid` yourself; it is not added automatically.
- Forwards `ref` to the `<input>`.
- Wrap in `<Field>` for a label, hint and error message.

---

## TextArea

Multi-line text input with optional monospace font and error state.

```tsx
import { TextArea } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mono` | `boolean` | `false` | Use JetBrains Mono, for code and identifiers |
| `error` | `boolean` | `false` | Rose border and focus ring |
| `...textareaProps` | | | Remaining props spread onto the `<textarea>` |

### Usage

```tsx
<TextArea placeholder="Enter notes…" rows={3} />
```

```tsx
<TextArea
  value={query}
  onChange={(e) => setQuery(e.target.value)}
  placeholder="SELECT * FROM entities"
  mono
  rows={4}
/>
```

### Gotchas

- `error` is visual only; set `aria-invalid` yourself.
- Forwards `ref` to the `<textarea>`.

---

## NumberInput

Numeric input rendered as `<input type="number">`.

```tsx
import { NumberInput } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mono` | `boolean` | `false` | Use JetBrains Mono, for tabular numbers |
| `error` | `boolean` | `false` | Rose border and focus ring |
| `...inputProps` | | | Remaining props (`min`, `max`, `step`, …) spread onto the `<input>` |

### Usage

```tsx
<NumberInput placeholder="0" />
```

```tsx
<NumberInput
  value={retries}
  onChange={(e) => setRetries(e.target.valueAsNumber)}
  step={1}
  min={0}
  max={10}
  mono
/>
```

### Gotchas

- `onChange` receives a native change event; the value is a string (`e.target.value`). Use `e.target.valueAsNumber` for a number (it is `NaN` when the field is empty).
- `min` / `max` only constrain the spinner and native validation; typed values are not clamped.
- `error` is visual only; set `aria-invalid` yourself.

---

## Select

Custom dropdown (not a native `<select>`) with single and multi-select modes, compound item children, icons, descriptions, separators and section titles.

```tsx
import { Select } from '@tinkermonkey/heimdall-ui'
import type { DropdownPlacement } from '@tinkermonkey/heimdall-ui'
```

### Props

Single mode is the default. `value` / `defaultValue` / `onChange` apply only to single mode; `values` / `defaultValues` / `onValuesChange` apply only when `multiple` is set. The types reject mixing them.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `multiple` | `boolean` | `false` | Enable multi-select mode |
| `value` | `string` | — | Controlled value (single mode) |
| `defaultValue` | `string` | `''` | Initial value, uncontrolled (single mode) |
| `onChange` | `(value: string) => void` | — | Called with the picked value (single mode) |
| `values` | `string[]` | — | Controlled values (multi mode) |
| `defaultValues` | `string[]` | `[]` | Initial values, uncontrolled (multi mode) |
| `onValuesChange` | `(values: string[]) => void` | — | Called with the full selection (multi mode) |
| `placeholder` | `string` | `'Select…'` | Trigger text when nothing is selected |
| `error` | `boolean` | `false` | Rose border; sets `aria-invalid` on the trigger |
| `disabled` | `boolean` | `false` | Disable the trigger; panel cannot open |
| `id` | `string` | — | id on the trigger button (pair with `Field htmlFor`) |
| `name` | `string` | — | Emits hidden inputs for native form submission |
| `className` | `string` | `''` | Extra class on the root `<div>` |
| `ariaLabel` | `string` | — | `aria-label` on the trigger button |
| `children` | `ReactNode` | required | `Select.Item`, `Select.CheckboxItem`, etc. |
| `data-testid` | `string` | — | Test id on the root `<div>` |
| `placement` | `DropdownPlacement` | `'bottom-start'` | Panel side and edge alignment |

`DropdownPlacement` is `'bottom-start' | 'bottom-end' | 'top-start' | 'top-end'`: `top`/`bottom` is the side the panel opens to, `start`/`end` is the trigger edge it aligns with.

### Usage

```tsx
// Uncontrolled single select
<Select placeholder="Choose…" defaultValue="ok">
  <Select.Item value="ok">Healthy</Select.Item>
  <Select.Item value="warn">Warning</Select.Item>
  <Select.Item value="err">Failed</Select.Item>
</Select>
```

```tsx
// Controlled single select with icons, descriptions, sections and a disabled item
<Field label="Action" htmlFor="action-select">
  <Select
    id="action-select"
    value={action}
    onChange={setAction}
    placeholder="Choose action"
    placement="bottom-end"
  >
    <Select.SectionTitle>Recent</Select.SectionTitle>
    <Select.Item value="open" icon="folder" description="Open an existing project">
      Open project
    </Select.Item>
    <Select.Item value="recent" icon="clock">Recent</Select.Item>
    <Select.Separator />
    <Select.SectionTitle>Other</Select.SectionTitle>
    <Select.Item value="settings" icon="settings">Settings</Select.Item>
    <Select.Item value="archive" icon="hardDrive" disabled>Archive</Select.Item>
  </Select>
</Field>
```

```tsx
// Controlled multi select
<Select
  multiple
  values={domains}
  onValuesChange={setDomains}
  placeholder="No domains"
  name="domains"
>
  <Select.CheckboxItem value="life">life</Select.CheckboxItem>
  <Select.CheckboxItem value="physics">physics</Select.CheckboxItem>
  <Select.CheckboxItem value="chemistry" description="Includes materials">
    chemistry
  </Select.CheckboxItem>
</Select>
```

### Compound subcomponents

All subcomponents throw if rendered outside a `<Select>`.

#### Select.Item

Option row. Shows a trailing check when selected in single mode. Use in single mode.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `string` | required | Value reported on selection |
| `icon` | `IconName` | — | Leading icon (any key of `ICONS`) |
| `description` | `ReactNode` | — | Secondary line under the label |
| `disabled` | `boolean` | `false` | Not selectable; skipped by arrow keys |
| `children` | `ReactNode` | required | Label; also shown in the trigger when selected |

#### Select.CheckboxItem

Option row with a leading checkbox. Use with `multiple`.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `string` | required | Value toggled on click |
| `description` | `ReactNode` | — | Secondary line under the label |
| `disabled` | `boolean` | `false` | Not selectable; skipped by arrow keys |
| `children` | `ReactNode` | required | Label; also shown in the trigger when selected |

#### Select.Separator

Horizontal divider between groups of items. Takes no props.

#### Select.SectionTitle

Monospace uppercase eyebrow heading inside the panel.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | Heading text (rendered uppercase) |

### Gotchas

- Not a native `<select>`: `onChange` receives the value string, not an event. Do not write `e.target.value`.
- Native `<option>` children do nothing. Use `Select.Item` / `Select.CheckboxItem`.
- Remaining HTML attributes are not spread anywhere; only the props listed above are accepted. Use `ariaLabel` (camelCase), not `aria-label`.
- Single mode closes the panel on pick and cannot be cleared from the UI; re-picking the selected item fires `onChange` again with the same value. Provide an explicit "none" item if clearing is needed.
- Multi mode keeps the panel open and toggles values. The trigger shows the first selected label plus `+N`.
- The trigger shows the selected item's `children`; a value with no matching item shows the raw value string.
- Controlled mode (`value` / `values` defined) ignores internal state; update it in the change handler or the selection will not move.
- `name` renders one `<input type="hidden">` per selected value, and nothing when the selection is empty.
- The `ref` is forwarded to the trigger `<button>`.
- Keyboard: ArrowUp/ArrowDown/Enter/Space on the trigger opens the panel; arrows, Home, End and Tab move between items; Escape or an outside click closes and returns focus to the trigger.
- The panel is absolutely positioned inside the root (not portaled), max 320px tall, `z-index: 1000`. An ancestor with `overflow: hidden` clips it; near the bottom of a scroll container use `placement="top-start"`. There is no automatic flip.

---

## TriState

Checkbox with three visual states: unchecked, indeterminate (dash) and checked. Used for select-all rows.

```tsx
import { TriState } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `indeterminate` | `boolean` | `false` | Show the dash state; sets `aria-checked="mixed"` |
| `...inputProps` | | | Remaining props spread onto the `<input type="checkbox">` (`type` is omitted) |

### Usage

```tsx
<TriState checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
```

```tsx
// Select-all checkbox over a list of rows
<label>
  <TriState
    checked={selectedIds.length === rowIds.length}
    indeterminate={selectedIds.length > 0 && selectedIds.length < rowIds.length}
    onChange={(e) => setSelectedIds(e.target.checked ? rowIds : [])}
    aria-label="Select all rows"
  />
</label>
```

### Gotchas

- `indeterminate` sets the native `input.indeterminate` DOM property in an effect; the dash is styled with `:indeterminate`.
- Clicking clears the native indeterminate flag, but the effect only re-applies it when the prop changes. Derive `indeterminate` from data (as above) or reset it in `onChange`, otherwise the dash and the prop disagree.
- `aria-checked` is computed (`mixed` when indeterminate, otherwise from `checked`); pass `aria-checked` to override.
- `type` cannot be changed. Forwards `ref` to the `<input>`.
- Renders no label text; wrap it in a `<label>` or pass `aria-label`.

---

## Field

Layout wrapper that adds a label, required marker, inline hint and error message around any input.

```tsx
import { Field } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `ReactNode` | — | Label above the input; omitted when empty |
| `htmlFor` | `string` | — | `for` on the label; match the input `id` |
| `required` | `boolean` | `false` | Rose asterisk after the label |
| `disabled` | `boolean` | `false` | Dims label, hint and error to 45% |
| `error` | `ReactNode` | — | Rose message below the input |
| `errorId` | `string` | — | `id` on the error element |
| `hint` | `ReactNode` | — | Secondary text right-aligned in the label row |
| `children` | `ReactNode` | required | The input element(s) |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<Field label="Display name">
  <TextInput placeholder="Enter name…" />
</Field>
```

```tsx
<Field
  label="Identifier"
  htmlFor="class-id"
  hint="Cannot be changed after creation"
  required
  error={idError}
  errorId="class-id-error"
>
  <TextInput
    id="class-id"
    placeholder="cls_organism"
    mono
    error={Boolean(idError)}
    aria-invalid={Boolean(idError)}
    aria-describedby={idError ? 'class-id-error' : undefined}
  />
</Field>
```

### Gotchas

- `Field` does not generate ids or wire ARIA. Pass matching `htmlFor` / `id`, and set `aria-describedby={errorId}` on the input yourself.
- `disabled` only dims the text. Set `disabled` on the child input too.
- `hint` renders only when `label` is set, because it lives inside the label row.
- `error` on `Field` does not style the child; also pass `error` to the input.
- With `Select`, pass `id` to the `Select` so `htmlFor` targets its trigger button.

---

## FilterDropdown

Compound dropdown for filter bars: a trigger with an eyebrow label and summary, and a panel of checkbox (multi) or radio (single) options.

```tsx
import { FilterDropdown } from '@tinkermonkey/heimdall-ui'
import type { DropdownPlacement } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mode` | `'checkbox' \| 'radio'` | `'checkbox'` | Multi-select or single-select |
| `value` | `string[]` | — | Controlled selected values |
| `defaultValue` | `string[]` | `[]` | Initial values (uncontrolled) |
| `onChange` | `(selectedValues: string[]) => void` | — | Called with the full selection |
| `className` | `string` | `''` | Extra class on the root `<div>` |
| `placement` | `DropdownPlacement` | `'bottom-start'` | Panel side and edge alignment |
| `children` | `ReactNode` | required | `FilterDropdown.Trigger` and `FilterDropdown.Panel` |

### Usage

```tsx
// Uncontrolled checkbox filter
<FilterDropdown defaultValue={['running']} onChange={setStatuses}>
  <FilterDropdown.Trigger
    label="Status"
    summary={statuses.length > 0 ? `${statuses.length} selected` : 'All'}
  />
  <FilterDropdown.Panel>
    <FilterDropdown.Section>
      <FilterDropdown.Checkbox value="running" label="running" />
      <FilterDropdown.Checkbox value="stopped" label="stopped" />
    </FilterDropdown.Section>
  </FilterDropdown.Panel>
</FilterDropdown>
```

```tsx
// Controlled radio filter with sections, right-aligned panel
<FilterDropdown
  mode="radio"
  value={nodeType ? [nodeType] : []}
  onChange={(values) => setNodeType(values[0] ?? null)}
  placement="bottom-end"
>
  <FilterDropdown.Trigger label="Node type" summary={nodeType ?? 'Any'} />
  <FilterDropdown.Panel style={{ minWidth: 240 }}>
    <FilterDropdown.Section title="Structural">
      <FilterDropdown.Radio value="graph" label="graph" description="Top-level graph node" />
      <FilterDropdown.Radio value="entity" label="entity" />
    </FilterDropdown.Section>
    <FilterDropdown.Section title="Links">
      <FilterDropdown.Radio value="relationship" label="relationship" />
      <FilterDropdown.Radio value="attribute" label="attribute" />
    </FilterDropdown.Section>
  </FilterDropdown.Panel>
</FilterDropdown>
```

### Compound subcomponents

All subcomponents throw if rendered outside a `<FilterDropdown>`.

#### FilterDropdown.Trigger

Button that toggles the panel. Shows an uppercase monospace eyebrow, the summary and a chevron.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | Eyebrow text (rendered uppercase) |
| `summary` | `ReactNode` | required | Main trigger text, e.g. current selection |
| `...buttonProps` | | | Remaining props spread onto the `<button>`; `className` and `onClick` are ignored |

#### FilterDropdown.Panel

Floating panel holding the options. Hidden while closed.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | `Section`, `Checkbox` or `Radio` rows |
| `...divProps` | | | Remaining props spread onto the panel `<div>`; `style` applies only while open |

#### FilterDropdown.Section

Group of options with an optional eyebrow title.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | — | Eyebrow heading (rendered uppercase) |
| `children` | `ReactNode` | required | Option rows |

#### FilterDropdown.Checkbox

Toggleable option row for `mode="checkbox"`.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `string` | required | Value added to or removed from the selection |
| `label` | `ReactNode` | required | Row label |
| `description` | `ReactNode` | — | Secondary line under the label |

#### FilterDropdown.Radio

Single-choice option row for `mode="radio"`.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `string` | required | Value that replaces the selection |
| `label` | `ReactNode` | required | Row label |
| `description` | `ReactNode` | — | Secondary line under the label |

### Gotchas

- `Trigger` and `Panel` must both be rendered inside `FilterDropdown`; the panel positions against the root `<div>`.
- `summary` is not computed. Derive it from the selection yourself.
- Values are always `string[]`, also in radio mode (zero or one entry).
- Radio mode closes the panel on pick, and a picked radio cannot be cleared from the UI. Checkbox mode stays open until Escape or an outside click.
- Controlled mode (`value` defined) ignores internal state; update it in `onChange`.
- There is no `disabled` prop on the root; pass `disabled` to `FilterDropdown.Trigger`.
- Keyboard: arrows, Home, End and Tab move between rows once open; Escape closes and returns focus to the trigger. Opening is by click (or Enter/Space on the focused trigger button).
- The panel is absolutely positioned, not portaled, with `z-index: 1000` and a 320px max height. An `overflow: hidden` ancestor clips it; use `placement` to open upward or right-aligned. There is no automatic flip.

---

## EntityPicker

Search-as-you-type combobox that lists entity results with optional domain chips. The parent owns the query and does the filtering.

```tsx
import { EntityPicker } from '@tinkermonkey/heimdall-ui'
import type { EntityPickerResult, DropdownPlacement } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `query` | `string` | required | Controlled search input value |
| `onQueryChange` | `(query: string) => void` | required | Called on every keystroke |
| `results` | `EntityPickerResult[]` | `[]` | Results to list, already filtered |
| `onSelect` | `(result: EntityPickerResult) => void` | required | Called when a result is picked |
| `onClear` | `() => void` | required | Called when the clear (×) button is clicked |
| `placeholder` | `string` | `'Search entities...'` | Input placeholder |
| `disabled` | `boolean` | `false` | Disable input and clear button |
| `inputId` | `string` | — | `id` on the `<input>` (pair with a label) |
| `placement` | `DropdownPlacement` | `'bottom-start'` | Results panel side and edge alignment |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface EntityPickerResult {
  id: string
  label: string
  domain?: string
  domainColor?: StatusColor // 'emerald' | 'amber' | 'rose' | 'cyan' | 'violet' | 'neutral'
}
```

### Usage

```tsx
const [query, setQuery] = useState('')

<EntityPicker
  query={query}
  onQueryChange={setQuery}
  results={query ? entities.filter((e) => e.label.includes(query)) : []}
  onSelect={(e) => { setSelected(e); setQuery('') }}
  onClear={() => setQuery('')}
/>
```

```tsx
<Field label="Parent class" htmlFor="parent-class">
  <EntityPicker
    inputId="parent-class"
    query={query}
    onQueryChange={setQuery}
    results={results}
    onSelect={(e) => { setParent(e); setQuery(e.label) }}
    onClear={() => { setParent(null); setQuery('') }}
    placeholder="Search classes..."
    placement="top-start"
  />
</Field>
```

### Gotchas

- Fully controlled and does no filtering; supply filtered `results`. The picker does not display the selected entity — render it yourself, or set `query` to its label in `onSelect`.
- The panel renders only while open and `results` is non-empty. There is no built-in empty or loading state.
- The panel opens on typing, or on focus when `query` and `results` are both non-empty. It closes after a pick, on Escape and on outside click.
- `onSelect` does not change `query`; clear or replace it in the handler.
- The × button appears only while `query` is non-empty and the picker is enabled.
- Keyboard: ArrowUp/ArrowDown/Home/End move the active result (the first result is active by default); Enter picks it.
- A result's domain chip renders only when both `domain` and `domainColor` are set.
- The `ref` points to the root `<div>`, not the input.
- The panel is absolutely positioned, not portaled; an `overflow: hidden` ancestor clips it.

---

## KeyValueEditor

Editable table of key/value rows with an optional datatype column and add/remove controls.

```tsx
import { KeyValueEditor } from '@tinkermonkey/heimdall-ui'
import type { KeyValueRow } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `rows` | `KeyValueRow[]` | required | Rows in display order |
| `onChange` | `(rows: KeyValueRow[]) => void` | required | Called with the full rows array on any edit |
| `datatypeColumn` | `boolean` | `false` | Show a datatype `Select` column |
| `datatypes` | `string[]` | `['string', 'number', 'boolean']` | Datatype options |
| `disabled` | `boolean` | `false` | Disable inputs, remove and add buttons |
| `keyPlaceholder` | `string` | `'Key'` | Placeholder for key inputs |
| `valuePlaceholder` | `string` | `'Value'` | Placeholder for value inputs |
| `addLabel` | `string` | `'Add row'` | Add button label |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface KeyValueRow {
  id: string
  key: string
  value: string
  datatype?: string
}
```

### Usage

```tsx
const [rows, setRows] = useState<KeyValueRow[]>([
  { id: 'env', key: 'environment', value: 'production' },
])

<KeyValueEditor rows={rows} onChange={setRows} />
```

```tsx
<KeyValueEditor
  rows={rows}
  onChange={setRows}
  datatypeColumn
  datatypes={['string', 'number', 'boolean', 'array']}
  keyPlaceholder="attribute_name"
  addLabel="Add attribute"
/>
```

### Gotchas

- Fully controlled. `onChange` receives the whole array; replace state with it.
- Values are always strings, whatever the datatype; parse them yourself.
- Added rows get a generated `id` (opaque, not sequential), empty key and value, and `datatype: 'string'` when `datatypeColumn` is on.
- A row with no `datatype` shows `string` in the datatype column but stays `undefined` in data until changed.
- Column headers are fixed (`Key`, `Value`, `Type`); the placeholder props do not change them.
- No validation: empty and duplicate keys are allowed. `id` must be unique per row (used as the React key).

---

## OrderedList

Ranked list with move-up / move-down buttons and an optional star marker on a primary item.

```tsx
import { OrderedList } from '@tinkermonkey/heimdall-ui'
import type { OrderedItem } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `items` | `OrderedItem[]` | required | Items in rank order |
| `onChange` | `(items: OrderedItem[]) => void` | required | Called with the reordered array |
| `primaryItemId` | `string` | — | Item id that gets the star badge |
| `disabled` | `boolean` | `false` | Disable all move buttons |
| `...divProps` | | | Remaining props spread onto the root `<div role="list">` |

### Data types

```ts
interface OrderedItem {
  id: string
  label: string
}
```

### Usage

```tsx
const [items, setItems] = useState<OrderedItem[]>([
  { id: 'src_primary', label: 'src_primary' },
  { id: 'src_mirror', label: 'src_mirror' },
  { id: 'src_archive', label: 'src_archive' },
])

<OrderedList items={items} onChange={setItems} />
```

```tsx
// First item is primary; the star follows whichever item is on top
<OrderedList items={items} onChange={setItems} primaryItemId={items[0]?.id} />
```

### Gotchas

- Reordering is by buttons only (one step per click); there is no drag and drop.
- Fully controlled. `onChange` receives a new array; replace state with it.
- `primaryItemId` is visual only and tied to an id, not a position. Pass `items[0]?.id` for "top item is primary".
- The first item's up button and the last item's down button are always disabled.
- `label` is a plain string; there is no slot for custom row content.

---

## RelationshipBuilder

Three-column form (Source / Predicate / Target) composing two `EntityPicker`s and a `Select` into one relationship value.

```tsx
import { RelationshipBuilder } from '@tinkermonkey/heimdall-ui'
import type { RelationshipBuilderValue, EntityPickerResult } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `RelationshipBuilderValue` | required | Controlled source, predicate and target |
| `onChange` | `(value: RelationshipBuilderValue) => void` | required | Called with the next full value |
| `sourceQuery` | `string` | required | Source picker search text |
| `onSourceQueryChange` | `(query: string) => void` | required | Source picker input handler |
| `targetQuery` | `string` | required | Target picker search text |
| `onTargetQueryChange` | `(query: string) => void` | required | Target picker input handler |
| `sourceResults` | `EntityPickerResult[]` | `[]` | Filtered source results |
| `targetResults` | `EntityPickerResult[]` | `[]` | Filtered target results |
| `predicates` | `string[]` | `['contains', 'relates to', 'depends on', 'is used by']` | Predicate options |
| `onSourceClear` | `() => void` | required | Source picker × clicked |
| `onTargetClear` | `() => void` | required | Target picker × clicked |
| `disabled` | `boolean` | `false` | Disable both pickers and the predicate select |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface RelationshipBuilderValue {
  source?: EntityPickerResult
  predicate: string
  target?: EntityPickerResult
}
```

### Usage

```tsx
const [value, setValue] = useState<RelationshipBuilderValue>({ predicate: 'contains' })
const [sourceQuery, setSourceQuery] = useState('')
const [targetQuery, setTargetQuery] = useState('')

const match = (q: string) =>
  q ? entities.filter((e) => e.label.toLowerCase().includes(q.toLowerCase())) : []

<RelationshipBuilder
  value={value}
  onChange={setValue}
  sourceQuery={sourceQuery}
  onSourceQueryChange={setSourceQuery}
  targetQuery={targetQuery}
  onTargetQueryChange={setTargetQuery}
  sourceResults={match(sourceQuery)}
  targetResults={match(targetQuery)}
  onSourceClear={() => { setSourceQuery(''); setValue({ ...value, source: undefined }) }}
  onTargetClear={() => { setTargetQuery(''); setValue({ ...value, target: undefined }) }}
/>
```

```tsx
<RelationshipBuilder
  value={value}
  onChange={setValue}
  sourceQuery={sourceQuery}
  onSourceQueryChange={setSourceQuery}
  targetQuery={targetQuery}
  onTargetQueryChange={setTargetQuery}
  sourceResults={match(sourceQuery)}
  targetResults={match(targetQuery)}
  predicates={['contains', 'relates to', 'depends on', 'is used by', 'owns']}
  onSourceClear={() => setSourceQuery('')}
  onTargetClear={() => setTargetQuery('')}
  disabled={saving}
/>
```

### Gotchas

- Three pieces of state are yours: `value`, `sourceQuery` and `targetQuery`. Results are filtered by you.
- Picking a result calls `onChange` with the new entity, then calls `onSourceQueryChange('')` / `onTargetQueryChange('')`.
- The × button only appears while a query is non-empty, so `onSourceClear` / `onTargetClear` fire while searching, not after a pick. The component never clears a selected entity itself; provide a separate control (or clear in the clear handler, as above) if users need to remove a selection.
- The selected entity is shown under its picker as domain text plus label; `domainColor` is not used there.
- Column labels (`Source`, `Predicate`, `Target`) and picker placeholders are fixed.
- `predicate` should be one of `predicates`; an empty string shows the `Select relation type...` placeholder.
- Layout is a fixed three-column grid with no responsive collapse; give it enough width.
