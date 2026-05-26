---
name: heimdall-inputs
description: Heimdall component guide for Inputs: TextInput, TextArea, NumberInput, Select, TriState, Field, FilterDropdown, EntityPicker, KeyValueEditor, OrderedList, RelationshipBuilder
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## TextInput

Single-line text input with optional monospace and error state.

```tsx
import { TextInput } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mono` | `boolean` | `false` | Use JetBrains Mono font |
| `error` | `boolean` | `false` | Rose border and focus ring |
| `...InputHTMLAttributes` | | | All standard input attributes |

### Usage

```tsx
<TextInput placeholder="Enter value…" />
```

```tsx
<TextInput value={val} onChange={e => setVal(e.target.value)} />
<TextInput placeholder="cls_4f3a" mono />
<TextInput value={val} error onChange={e => setVal(e.target.value)} />
```

### Gotchas

- Always wrap with `<Field>` to get a label and error message

---

## TextArea

Multi-line text input with optional monospace and error state.

```tsx
import { TextArea } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mono` | `boolean` | `false` | Use JetBrains Mono font |
| `error` | `boolean` | `false` | Rose border and focus ring |
| `...TextareaHTMLAttributes` | | | All standard textarea attributes |

### Usage

```tsx
<TextArea placeholder="Enter notes…" rows={3} />
```

```tsx
<TextArea value={val} onChange={e => setVal(e.target.value)} mono rows={4} />
```

---

## NumberInput

Numeric input constrained to `type="number"`.

```tsx
import { NumberInput } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mono` | `boolean` | `false` | Use JetBrains Mono font |
| `error` | `boolean` | `false` | Error state styling |
| `...InputHTMLAttributes` | | | All standard input attributes (step, min, max, etc.) |

### Usage

```tsx
<NumberInput placeholder="0" />
```

```tsx
<NumberInput defaultValue={10} step={5} min={0} max={100} />
```

---

## Select

Native `<select>` wrapper with design system styling.

```tsx
import { Select } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `error` | `boolean` | `false` | Rose border + sets `aria-invalid` |
| `...SelectHTMLAttributes` | | | All standard select attributes |

### Usage

```tsx
<Select>
  <option value="">Choose…</option>
  <option value="a">Option A</option>
</Select>
```

```tsx
<Select value={val} onChange={e => setVal(e.target.value)} error>
  <option value="a">Option A</option>
  <option value="b">Option B</option>
</Select>
```

---

## TriState

Three-state checkbox: unchecked, indeterminate (–), checked.

```tsx
import { TriState } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `indeterminate` | `boolean` | `false` | Show the indeterminate/dash state |
| `...InputHTMLAttributes` | | | All standard checkbox attributes (`checked`, `onChange`, etc.) — `type` is locked to `'checkbox'` |

### Usage

```tsx
// Controlled three states
<TriState checked={checked} onChange={e => setChecked(e.target.checked)} />
```

```tsx
// Indeterminate state
<TriState indeterminate readOnly />
```

### Gotchas

- `indeterminate` sets the native `input.indeterminate` DOM property via `useEffect` — it is not a CSS-only trick
- `type` prop is omitted from the interface; passing it has no effect

---

## Field

Label + input wrapper that handles label, hint, required marker, and error message layout.

```tsx
import { Field } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `ReactNode` | — | Label text above input |
| `htmlFor` | `string` | — | Associates label with input id |
| `required` | `boolean` | `false` | Shows red asterisk |
| `disabled` | `boolean` | `false` | 45% opacity on label text |
| `error` | `ReactNode` | — | Error message below input in rose |
| `errorId` | `string` | — | id on error element for `aria-describedby` |
| `hint` | `ReactNode` | — | Secondary text shown inline after label |
| `children` | `ReactNode` | required | The input element(s) |

### Usage

```tsx
<Field label="Display name">
  <TextInput placeholder="Enter name…" />
</Field>
```

```tsx
<Field
  label="Email"
  htmlFor="email-input"
  required
  error="This field is required"
>
  <TextInput id="email-input" placeholder="user@example.com" error />
</Field>

<Field label="Identifier" hint="Cannot be changed after creation">
  <TextInput placeholder="my_identifier" mono />
</Field>
```

### Gotchas

- `disabled` on `Field` only dims the label — you must also set `disabled` on the child input
- `Field` is a layout wrapper only; it does not add any input functionality

---

## FilterDropdown

Compound dropdown for multi-select (checkbox) or single-select (radio) filters.

```tsx
import { FilterDropdown } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mode` | `'checkbox' \| 'radio'` | `'checkbox'` | Selection mode |
| `value` | `string[]` | — | Controlled selected values |
| `defaultValue` | `string[]` | — | Initial values (uncontrolled) |
| `onChange` | `(selectedValues: string[]) => void` | — | Called on selection change |
| `className` | `string` | — | Additional class on root |
| `children` | `ReactNode` | required | Compound children |

### Compound Subcomponents

- `FilterDropdown.Trigger` — button that opens the panel; props: `label: string` (uppercase eyebrow), `summary: ReactNode` (main text)
- `FilterDropdown.Panel` — dropdown container
- `FilterDropdown.Section` — grouped section; prop: `title?: string`
- `FilterDropdown.Checkbox` — checkbox item; props: `value: string`, `label: ReactNode`, `description?: ReactNode`
- `FilterDropdown.Radio` — radio item; props: `value: string`, `label: ReactNode`, `description?: ReactNode`

### Usage

```tsx
// Minimal checkbox filter
<FilterDropdown onChange={setSelected}>
  <FilterDropdown.Trigger label="STATUS" summary="All" />
  <FilterDropdown.Panel>
    <FilterDropdown.Section>
      <FilterDropdown.Checkbox value="active" label="Active" />
      <FilterDropdown.Checkbox value="stopped" label="Stopped" />
    </FilterDropdown.Section>
  </FilterDropdown.Panel>
</FilterDropdown>
```

```tsx
// Radio mode with sections
<FilterDropdown mode="radio" value={selected} onChange={v => setSelected(v)}>
  <FilterDropdown.Trigger label="DOMAIN" summary={selected[0] ?? 'None'} />
  <FilterDropdown.Panel>
    <FilterDropdown.Section title="DOMAINS">
      <FilterDropdown.Radio value="life" label="life" description="Life sciences" />
      <FilterDropdown.Radio value="climate" label="climate" />
    </FilterDropdown.Section>
  </FilterDropdown.Panel>
</FilterDropdown>
```

### Gotchas

- In `radio` mode, selecting an item immediately closes the panel
- In `checkbox` mode, the panel stays open until ESC or an outside click
- You must include `FilterDropdown.Trigger` and `FilterDropdown.Panel` as direct children

---

## EntityPicker

Search-as-you-type picker with dropdown results for selecting a single entity.

```tsx
import { EntityPicker } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `query` | `string` | required | Controlled search input value |
| `onQueryChange` | `(query: string) => void` | required | Called on every keystroke |
| `results` | `EntityPickerResult[]` | `[]` | Filtered results to display |
| `onSelect` | `(result: EntityPickerResult) => void` | required | Called when user picks a result |
| `onClear` | `() => void` | required | Called when × button clicked |
| `placeholder` | `string` | `'Search entities...'` | Input placeholder |
| `disabled` | `boolean` | `false` | Prevents all interaction |
| `inputId` | `string` | — | id for the input element |

```ts
interface EntityPickerResult {
  id: string
  label: string
  domain?: string
  domainColor?: StatusColor
}
```

### Usage

```tsx
const [query, setQuery] = useState('')

<EntityPicker
  query={query}
  onQueryChange={setQuery}
  results={query ? entities.filter(e => e.label.includes(query)) : []}
  onSelect={e => { setSelected(e); setQuery('') }}
  onClear={() => { setSelected(null); setQuery('') }}
/>
```

### Gotchas

- Fully controlled — the parent must manage query state and supply filtered results
- Results are filtered externally; the component does no filtering itself

---

## KeyValueEditor

Editable table of key/value rows with optional datatype column and add/remove controls.

```tsx
import { KeyValueEditor } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `rows` | `KeyValueRow[]` | required | Array of rows |
| `onChange` | `(rows: KeyValueRow[]) => void` | required | Called on any row change |
| `datatypeColumn` | `boolean` | `false` | Show datatype selector column |
| `datatypes` | `string[]` | `['string', 'number', 'boolean']` | Datatype options |
| `disabled` | `boolean` | `false` | Prevent all edits |
| `keyPlaceholder` | `string` | `'Key'` | Placeholder for key inputs |
| `valuePlaceholder` | `string` | `'Value'` | Placeholder for value inputs |
| `addLabel` | `string` | `'Add row'` | Add button label |

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
  { id: '1', key: 'environment', value: 'production' },
])

<KeyValueEditor rows={rows} onChange={setRows} />
```

```tsx
<KeyValueEditor
  rows={rows}
  onChange={setRows}
  datatypeColumn
  datatypes={['string', 'number', 'boolean', 'array']}
/>
```

### Gotchas

- `onChange` receives the entire rows array, not a diff — replace parent state wholesale
- New rows have auto-generated `id` values; do not rely on them being sequential

---

## OrderedList

Ranked list with move-up/move-down controls and optional primary item marker.

```tsx
import { OrderedList } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `items` | `OrderedItem[]` | required | Items in display order |
| `onChange` | `(items: OrderedItem[]) => void` | required | Called after reorder |
| `primaryItemId` | `string` | — | ID of item to mark with star badge |
| `disabled` | `boolean` | `false` | Disable reordering |

```ts
interface OrderedItem {
  id: string
  label: string
}
```

### Usage

```tsx
const [items, setItems] = useState<OrderedItem[]>([
  { id: '1', label: 'Initialize schema' },
  { id: '2', label: 'Migrate data' },
  { id: '3', label: 'Validate indexes' },
])

<OrderedList items={items} onChange={setItems} primaryItemId={items[0]?.id} />
```

### Gotchas

- `onChange` receives the full reordered array — replace state wholesale

---

## RelationshipBuilder

Three-column form (Source | Predicate | Target) for composing a typed relationship between two entities.

```tsx
import { RelationshipBuilder } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `RelationshipBuilderValue` | required | Controlled state |
| `onChange` | `(value: RelationshipBuilderValue) => void` | required | Called on any field change |
| `sourceQuery` | `string` | required | Controlled source search query |
| `onSourceQueryChange` | `(q: string) => void` | required | Source input change handler |
| `targetQuery` | `string` | required | Controlled target search query |
| `onTargetQueryChange` | `(q: string) => void` | required | Target input change handler |
| `sourceResults` | `EntityPickerResult[]` | `[]` | Source picker results |
| `targetResults` | `EntityPickerResult[]` | `[]` | Target picker results |
| `onSourceClear` | `() => void` | required | Clear source selection |
| `onTargetClear` | `() => void` | required | Clear target selection |
| `predicates` | `string[]` | `['contains', 'relates to', 'depends on', 'is used by']` | Predicate options |
| `disabled` | `boolean` | `false` | Disable all controls |

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

<RelationshipBuilder
  value={value}
  onChange={setValue}
  sourceQuery={sourceQuery}
  onSourceQueryChange={setSourceQuery}
  targetQuery={targetQuery}
  onTargetQueryChange={setTargetQuery}
  sourceResults={sourceResults}
  targetResults={targetResults}
  onSourceClear={() => { setSourceQuery(''); setValue({ ...value, source: undefined }) }}
  onTargetClear={() => { setTargetQuery(''); setValue({ ...value, target: undefined }) }}
/>
```

### Gotchas

- You must manage three separate pieces of state: `value`, `sourceQuery`, and `targetQuery`
- `onSourceClear`/`onTargetClear` must clear both the query state AND the selected entity in `value` — the component does not do this automatically
