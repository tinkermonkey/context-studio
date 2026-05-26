---
name: heimdall-chat
description: Heimdall component guide for Chat: ChatMessage, ToolBlock, ThinkingBlock, ChatDivider, ChatSuggestions, ChatComposer, ChatContainer
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## ChatMessage

A single chat turn (user or bot) with optional inline tool call and reasoning blocks.

```tsx
import { ChatMessage } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `role` | `'user' \| 'bot'` | required | Message source |
| `senderName` | `string` | required | Display name |
| `timestamp` | `string` | required | Formatted time string |
| `body` | `ReactNode` | required | Message content |
| `avatar` | `string` | — | URL (renders `<img>`) or text (renders as initials) |
| `badge` | `string` | — | Bot role badge (e.g. `'EXECUTOR'`) rendered monospace |
| `toolBlock` | `ToolBlockData` | — | Inline tool call visualization |
| `thinkingBlock` | `ThinkingBlockData` | — | Collapsible reasoning block |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface ToolBlockData {
  name: string
  status: 'running' | 'success' | 'error'
  output?: Array<{ key?: string; value: string }>
}

interface ThinkingBlockData {
  content: string
}
```

### Usage

```tsx
// User message
<ChatMessage role="user" senderName="You" timestamp="10:30 AM" body="Can you analyze this dataset?" />
```

```tsx
// Bot with badge, tool call, and thinking
<ChatMessage
  role="bot"
  senderName="Assistant"
  badge="EXECUTOR"
  timestamp="10:31 AM"
  body="Running analysis..."
  toolBlock={{
    name: 'query_database',
    status: 'success',
    output: [
      { key: 'rows', value: '1,234' },
      { key: 'duration', value: '245ms' },
    ],
  }}
  thinkingBlock={{
    content: `Step 1: Load dataset\nStep 2: Calculate metrics\nStep 3: Return results`,
  }}
/>
```

### Gotchas

- Avatar detection: strings starting with `http://`, `https://`, or `/` render as `<img>`; otherwise rendered as text initials
- Auto-initials: when no `avatar` provided, uses first 2 uppercase characters of `senderName`
- `toolBlock` and `thinkingBlock` can be used independently or together on the same message

---

## ToolBlock

Collapsible block showing a tool/function call name, execution status, and optional key/value output.

```tsx
import { ToolBlock } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `string` | required | Tool call name |
| `status` | `'running' \| 'success' \| 'error'` | required | Execution status |
| `output` | `Array<{ key?: string; value: string }>` | `[]` | Key/value output rows |
| `defaultCollapsed` | `boolean` | `false` | Initial collapsed state |
| `onToggleCollapsed` | `(collapsed: boolean) => void` | — | Collapse/expand callback |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Running (no output yet)
<ToolBlock name="query_database" status="running" />
```

```tsx
// Success with output
<ToolBlock
  name="query_database"
  status="success"
  output={[
    { key: 'rows', value: '1,234' },
    { key: 'duration', value: '245ms' },
  ]}
/>

// Error
<ToolBlock
  name="fetch_schema"
  status="error"
  output={[{ value: 'Connection timeout after 30s' }]}
/>

// Pre-collapsed for historical messages
<ToolBlock name="old_tool_call" status="success" defaultCollapsed output={[{ key: 'result', value: 'ok' }]} />
```

### Gotchas

- Output rows only show when the block is expanded AND the output array has items
- `key` on output rows is optional — rows with only `value` render without a key column

---

## ThinkingBlock

Collapsible monospace block for displaying model reasoning or step-by-step thought processes.

```tsx
import { ThinkingBlock } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `content` | `string` | required | Reasoning text |
| `label` | `string` | `'thinking'` | Header label (displayed uppercase) |
| `defaultCollapsed` | `boolean` | `false` | Initial collapsed state |
| `onToggleCollapsed` | `(collapsed: boolean) => void` | — | Collapse/expand callback |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
<ThinkingBlock
  content={`Breaking down the problem:\n1. Load the dataset\n2. Calculate metrics\n3. Return results`}
/>
```

```tsx
// Pre-collapsed with custom label
<ThinkingBlock
  label="reasoning"
  content={longReasoningText}
  defaultCollapsed
/>
```

### Gotchas

- Content renders with `white-space: pre-wrap` — newlines in the string are preserved as line breaks
- Content section only renders when expanded

---

## ChatDivider

Horizontal rule with centered label for separating conversation sections (dates, sessions).

```tsx
import { ChatDivider } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | Center label text |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
<ChatDivider label="May 18, 2026" />
<ChatDivider label="New session" />
```

### Gotchas

- Renders `role="separator"` with `aria-label={label}`; the visual label span is `aria-hidden="true"` to avoid double-reading

---

## ChatSuggestions

Row of quick-reply suggestion chips. Selecting one disables all others.

```tsx
import { ChatSuggestions } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `suggestions` | `string[]` | required | Chip labels |
| `onSelect` | `(suggestion: string) => void` | required | Called when a chip is clicked |
| `selected` | `string` | — | Currently selected chip; when set, others are disabled |
| `aria-label` | `string` | `'Suggestions'` | Group accessible label |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
const [selected, setSelected] = useState<string | undefined>()

<ChatSuggestions
  suggestions={['Show me the plan', 'Approve & run', 'Cancel']}
  selected={selected}
  onSelect={setSelected}
/>
```

### Gotchas

- Returns `null` if `suggestions` is empty — no DOM element rendered
- Once `selected` is set, unselected chips are `disabled` but still rendered (not hidden)
- `onSelect` is removed from inherited `HTMLAttributes` to avoid a name conflict; always use the explicit prop

---

## ChatComposer

Rich message input with context chips, file attachment previews, and submit controls. Enter submits; Shift+Enter inserts a newline.

```tsx
import { ChatComposer } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `string` | required | Controlled input value |
| `onChange` | `(value: string) => void` | required | Called on every keystroke |
| `onSubmit` | `(value: string, contextItems: ContextItem[]) => void` | required | Called on Enter or send button |
| `placeholder` | `string` | `'Type a message...'` | Textarea placeholder |
| `onContextChange` | `(items: ContextItem[]) => void` | — | Called when context chip removed |
| `onAttachmentChange` | `(attachments: Attachment[]) => void` | — | Called when files added/removed |
| `scopeLabel` | `string` | — | Active bot label shown in toolbar |
| `contextItems` | `ContextItem[]` | `[]` | Context chips to display |
| `attachments` | `Attachment[]` | `[]` | Attached files to display |
| `disabled` | `boolean` | `false` | Disables textarea and buttons |
| `loading` | `boolean` | `false` | Disables send button only |
| `label` | `string` | `'Message'` | Textarea `aria-label` |

```ts
interface ContextItem {
  id: string
  label: string
}

interface Attachment {
  id: string
  name: string
  size?: number
}
```

### Usage

```tsx
// Minimal
const [value, setValue] = useState('')

<ChatComposer
  value={value}
  onChange={setValue}
  onSubmit={(v) => { sendMessage(v); setValue('') }}
/>
```

```tsx
// With context items and attachments
const [value, setValue] = useState('')
const [context, setContext] = useState<ContextItem[]>([{ id: 'schema', label: 'schema.json' }])
const [attachments, setAttachments] = useState<Attachment[]>([])

<ChatComposer
  value={value}
  onChange={setValue}
  onSubmit={(v, ctx) => { sendMessage(v, ctx); setValue('') }}
  scopeLabel="assistant"
  contextItems={context}
  onContextChange={setContext}
  attachments={attachments}
  onAttachmentChange={setAttachments}
  loading={isSending}
/>
```

### Gotchas

- Submit is blocked when `value.trim()` is empty, `disabled={true}`, or `loading={true}`
- File attachment validation is the parent's responsibility — no built-in type or size checks
- Textarea auto-grows up to 200px max height; `rows={2}` minimum
- `onSubmit` receives both the value and current `contextItems`

---

## ChatContainer

Full chat panel composing bot tabs, scrollable message thread, and a composer slot.

```tsx
import { ChatContainer } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | Thread content (ChatMessage, ChatDivider, etc.) |
| `bots` | `BotTab[]` | `[]` | Bot tab definitions |
| `activeBotId` | `string` | — | Currently selected bot tab ID |
| `onBotChange` | `(botId: string) => void` | — | Called when a bot tab is clicked |
| `autoScroll` | `boolean` | `true` | Scroll to bottom when `children` change |
| `composer` | `ReactNode` | — | Composer slot (typically `ChatComposer`) |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface BotTab {
  id: string
  label: string
  role: string
  status: 'idle' | 'busy' | 'healthy' | 'error'
}
```

### Usage

```tsx
// Single-bot with composer
<ChatContainer
  composer={
    <ChatComposer
      value={composerValue}
      onChange={setComposerValue}
      onSubmit={(v) => { sendMessage(v); setComposerValue('') }}
    />
  }
>
  <ChatDivider label="May 26, 2026" />
  <ChatMessage role="user" senderName="You" timestamp="10:30 AM" body="What's the status?" />
  <ChatMessage role="bot" senderName="Assistant" badge="EXECUTOR" timestamp="10:31 AM" body="All systems go." />
</ChatContainer>
```

```tsx
// Multi-bot with tab switching
const BOTS: BotTab[] = [
  { id: 'assistant', label: 'Assistant', role: 'EXECUTOR', status: 'idle' },
  { id: 'analyzer', label: 'Analyzer', role: 'ANALYST', status: 'healthy' },
]

<ChatContainer
  bots={BOTS}
  activeBotId={activeBotId}
  onBotChange={setActiveBotId}
  composer={<ChatComposer value={value} onChange={setValue} onSubmit={handleSubmit} />}
>
  {messages.map(msg =>
    msg.type === 'divider'
      ? <ChatDivider key={msg.id} label={msg.label} />
      : <ChatMessage key={msg.id} {...msg} />
  )}
</ChatContainer>
```

### Gotchas

- `autoScroll` fires on every `children` change — if the parent re-renders without content changes, scroll still fires
- The thread has `role="log"` and `aria-live="polite"` for live region announcements
- If `bots` is empty or not provided, no tab bar is rendered
