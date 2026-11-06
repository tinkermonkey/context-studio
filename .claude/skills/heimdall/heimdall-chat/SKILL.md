---
name: heimdall-chat
description: Heimdall component guide for Chat: ChatMessage, ToolBlock, ThinkingBlock, ChatDivider, ChatSuggestions, ChatComposer, ChatContainer, ChatMarkdownContent
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

A typical chat panel is a `ChatContainer` whose children are `ChatMessage` and `ChatDivider` elements, with a `ChatComposer` in its `composer` slot. Use `ChatMarkdownContent` as a message `body` to render model output as markdown.

## ChatMessage

A single chat turn (user or bot) with an optional inline tool call and reasoning block.

```tsx
import { ChatMessage } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `role` | `'user' \| 'bot'` | required | Message source; drives avatar and text color |
| `senderName` | `string` | required | Display name; fallback avatar initials |
| `timestamp` | `string` | required | Preformatted time string |
| `body` | `ReactNode` | required | Message content (text or elements) |
| `avatar` | `string` | first 2 chars of `senderName`, uppercased | URL renders `<img>`; other strings render as text |
| `badge` | `string` | — | Role badge after the name, uppercase monospace |
| `toolBlock` | `ToolBlockData` | — | Renders an expanded `ToolBlock` below the body |
| `thinkingBlock` | `ThinkingBlockData` | — | Renders an expanded `ThinkingBlock` below the body |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

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
<ChatMessage role="user" senderName="operator" timestamp="10:30" body="Summarize failures for svc_ingest." />
```

```tsx
<ChatMessage
  role="bot"
  senderName="executor"
  badge="EXECUTOR"
  timestamp="10:31"
  body="3 failed runs in the last 24h. All timed out on stage_validate."
  thinkingBlock={{
    content: 'Step 1: query run history\nStep 2: group by failure stage\nStep 3: summarize',
  }}
  toolBlock={{
    name: 'query_runs',
    status: 'success',
    output: [
      { key: 'rows', value: '1,234' },
      { key: 'duration', value: '245ms' },
    ],
  }}
/>
```

### Gotchas

- `avatar` is treated as a URL when it starts with `http://`, `https://` or `/`; any other string is rendered as literal avatar text (keep it to 1–2 characters — the avatar is 24px).
- `role` is the component prop, not the ARIA attribute; it is not forwarded to the DOM, so the root cannot be given an ARIA role.
- The blocks always render below `body`, `thinkingBlock` first, then `toolBlock`, and both start expanded. For collapsed blocks, or more than one tool call per message, put `<ToolBlock defaultCollapsed />` / `<ThinkingBlock />` elements inside `body` instead.
- `body` gets no markdown processing; wrap model output in `ChatMarkdownContent`.

---

## ToolBlock

Collapsible block showing a tool call name, execution status, and optional key/value output rows.

```tsx
import { ToolBlock } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `string` | required | Tool call name (monospace header) |
| `status` | `'running' \| 'success' \| 'error'` | required | Status label: amber, emerald or rose |
| `output` | `Array<{ key?: string; value: string }>` | `[]` | Output rows shown when expanded |
| `defaultCollapsed` | `boolean` | `false` | Initial collapsed state (uncontrolled) |
| `onToggleCollapsed` | `(collapsed: boolean) => void` | — | Called with the new collapsed state |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<ToolBlock name="query_runs" status="running" />
```

```tsx
<>
  <ToolBlock
    name="query_runs"
    status="success"
    output={[
      { key: 'rows', value: '1,234' },
      { key: 'duration', value: '245ms' },
    ]}
  />
  <ToolBlock name="fetch_schema" status="error" output={[{ value: 'Connection timeout after 30s' }]} />
  <ToolBlock
    name="fetch_schema"
    status="success"
    defaultCollapsed
    output={[{ key: 'tables', value: '12' }]}
    onToggleCollapsed={(collapsed) => console.log('tool_block collapsed', collapsed)}
  />
</>
```

### Gotchas

- Collapse state is internal; `defaultCollapsed` is read on mount only and there is no controlled `collapsed` prop.
- The header is always a toggle button, but with an empty `output` expanding shows nothing.
- Rows without `key` render the `value` alone (useful for error messages).
- The status label is the raw status string (`running`, `success`, `error`); there is no spinner or custom label.

---

## ThinkingBlock

Collapsible monospace block for model reasoning or step-by-step thought text.

```tsx
import { ThinkingBlock } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `content` | `string` | required | Reasoning text, newlines preserved |
| `label` | `string` | `'thinking'` | Header label, displayed uppercase |
| `defaultCollapsed` | `boolean` | `false` | Initial collapsed state (uncontrolled) |
| `onToggleCollapsed` | `(collapsed: boolean) => void` | — | Called with the new collapsed state |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<ThinkingBlock content={'Breaking down the problem:\n1. Load run history\n2. Group by stage'} />
```

```tsx
<ThinkingBlock
  label="reasoning"
  content={'Step 1: identify entities.\nStep 2: map relationships.\nStep 3: return the graph.'}
  defaultCollapsed
/>
```

### Gotchas

- `content` is a plain string rendered with `white-space: pre-wrap`; markdown is not parsed and elements are not accepted.
- Collapse state is internal; `defaultCollapsed` is read on mount only.
- The content element is unmounted while collapsed.

---

## ChatDivider

Horizontal rule with a centered label for separating conversation sections (dates, sessions).

```tsx
import { ChatDivider } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | Center label, displayed uppercase |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<ChatDivider label="2026-05-18" />
```

```tsx
<>
  <ChatDivider label="2026-05-18" />
  <ChatDivider label="New session" />
</>
```

### Gotchas

- Renders `role="separator"` with `aria-label={label}`; the visible label is `aria-hidden`, so screen readers read it once.

---

## ChatSuggestions

Row of quick-reply chips. Once one is selected, the others are disabled.

```tsx
import { ChatSuggestions } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `suggestions` | `string[]` | required | Chip labels |
| `onSelect` | `(suggestion: string) => void` | required | Called when an enabled chip is clicked |
| `selected` | `string` | — | Selected chip; when set, other chips are disabled |
| `aria-label` | `string` | `'Suggestions'` | Accessible label for the chip group |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<ChatSuggestions
  suggestions={['Show the plan', 'Approve and run', 'Cancel']}
  onSelect={(s) => console.log('suggestion', s)}
/>
```

```tsx
function SuggestionReply() {
  const [selected, setSelected] = useState<string | undefined>()
  return (
    <ChatSuggestions
      aria-label="Reply options"
      suggestions={['Show the plan', 'Approve and run', 'Cancel']}
      selected={selected}
      onSelect={setSelected}
    />
  )
}
```

### Gotchas

- Selection is fully controlled: without `selected`, clicking a chip calls `onSelect` but nothing locks. Store the choice and pass it back.
- The selected chip stays clickable and calls `onSelect` again; to clear the lock, set `selected` back to `undefined`.
- Returns `null` for an empty `suggestions` array.
- Chips are keyed by label, so labels must be unique.
- The native div `onSelect` event is omitted from the props type; `onSelect` is always the chip callback.

---

## ChatComposer

Controlled message input with context chips, attachment chips, a file picker and a send button.

```tsx
import { ChatComposer } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `string` | required | Controlled textarea value |
| `onChange` | `(value: string) => void` | required | Called on every edit |
| `onSubmit` | `(value: string, contextItems: ContextItem[]) => void` | required | Called on Enter (send mode) or send click |
| `placeholder` | `string` | `'Type a message...'` | Textarea placeholder |
| `onContextChange` | `(items: ContextItem[]) => void` | — | Called with the remaining list after a chip is removed |
| `onAttachmentChange` | `(attachments: Attachment[]) => void` | — | Called with the new list on file add or remove |
| `scopeLabel` | `string` | — | Shows "talking to **label**" in the tools row |
| `contextItems` | `ContextItem[]` | `[]` | Context chips to display |
| `attachments` | `Attachment[]` | `[]` | Attachment chips to display |
| `disabled` | `boolean` | `false` | Disables textarea, attach and send |
| `loading` | `boolean` | `false` | Disables send only; typing still works |
| `label` | `string` | `'Message'` | Textarea `aria-label` |
| `accept` | `string` | — | File picker `accept` filter (e.g. `'.csv,.json'`) |
| `enterBehavior` | `'send' \| 'newline'` | `'send'` | What plain Enter does |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface ContextItem {
  id: string
  label: string
}

interface Attachment {
  id: string
  name: string
  size?: number // bytes
}
```

### Usage

```tsx
function Composer() {
  const [value, setValue] = useState('')
  return (
    <ChatComposer
      value={value}
      onChange={setValue}
      onSubmit={(v) => {
        console.log('send', v)
        setValue('')
      }}
    />
  )
}
```

```tsx
function RichComposer({ sending }: { sending: boolean }) {
  const [value, setValue] = useState('')
  const [context, setContext] = useState<ContextItem[]>([{ id: 'ctx_schema', label: 'schema.json' }])
  const [attachments, setAttachments] = useState<Attachment[]>([])
  return (
    <ChatComposer
      value={value}
      onChange={setValue}
      onSubmit={(v, ctx) => {
        console.log('send', v, ctx, attachments)
        setValue('')
        setAttachments([])
      }}
      placeholder="Ask the executor..."
      scopeLabel="executor"
      contextItems={context}
      onContextChange={setContext}
      attachments={attachments}
      onAttachmentChange={setAttachments}
      accept=".csv,.json"
      enterBehavior="newline"
      loading={sending}
    />
  )
}
```

### Gotchas

- Fully controlled: the composer never clears `value` after submit — reset it in `onSubmit`. Context items and attachments are controlled too; without `onAttachmentChange`, picked files are dropped.
- `onAttachmentChange` receives metadata only (`id` from `crypto.randomUUID()`, `name`, `size`); the `File` objects are not exposed, so file contents cannot be read or uploaded through this API.
- `accept` only filters the native picker; there is no type or size validation.
- `onSubmit` receives the value and `contextItems`, not attachments; read those from your own state.
- Submit is blocked when `value.trim()` is empty, `disabled` or `loading`.
- `enterBehavior="send"`: Enter submits, Shift+Enter inserts a newline, and a "↵ send · ⇧↵ newline" hint shows. `"newline"`: Enter inserts a newline, only the send button submits, and the hint is hidden. No Cmd/Ctrl+Enter shortcut exists.
- The Enter handler does not check IME composition, so in send mode Enter used to confirm an IME candidate also submits.
- The composer never adds context items; it only removes them. Populate `contextItems` from your own UI.
- `disabled` does not disable the chip remove buttons.
- The textarea starts at 2 rows and auto-grows to a 200px max, then scrolls.

---

## ChatContainer

Chat panel composing optional bot tabs, a scrolling message thread and a composer slot.

```tsx
import { ChatContainer } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | Thread content (`ChatMessage`, `ChatDivider`, …) |
| `bots` | `BotTab[]` | `[]` | Bot tab definitions; tab row hidden when empty |
| `activeBotId` | `string` | — | Highlighted bot tab id |
| `onBotChange` | `(botId: string) => void` | — | Called when a bot tab is clicked |
| `autoScroll` | `boolean` | `true` | Scroll thread to bottom when `children` changes |
| `composer` | `ReactNode` | — | Slot below the thread (usually `ChatComposer`) |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface BotTab {
  id: string
  label: string
  role: string // shown uppercase under the label
  status: 'idle' | 'busy' | 'healthy' | 'error' // dot color: neutral, amber, emerald, rose
}
```

### Usage

```tsx
function SingleBotChat() {
  const [value, setValue] = useState('')
  return (
    <div style={{ height: 480 }}>
      <ChatContainer
        style={{ height: '100%' }}
        composer={<ChatComposer value={value} onChange={setValue} onSubmit={() => setValue('')} />}
      >
        <ChatDivider label="2026-05-26" />
        <ChatMessage role="user" senderName="operator" timestamp="10:30" body="Status of pipe_ingest?" />
        <ChatMessage role="bot" senderName="executor" badge="EXECUTOR" timestamp="10:31" body="3 of 5 stages complete." />
      </ChatContainer>
    </div>
  )
}
```

```tsx
const BOTS: BotTab[] = [
  { id: 'bot_executor', label: 'executor', role: 'EXECUTOR', status: 'idle' },
  { id: 'bot_analyst', label: 'analyst', role: 'ANALYST', status: 'healthy' },
  { id: 'bot_planner', label: 'planner', role: 'ARCHITECT', status: 'busy' },
]

interface ThreadItem {
  id: string
  kind: 'divider' | 'message'
  label?: string
  role?: 'user' | 'bot'
  senderName?: string
  timestamp?: string
  text?: string
}

function MultiBotChat({ threads }: { threads: Record<string, ThreadItem[]> }) {
  const [activeBotId, setActiveBotId] = useState('bot_executor')
  const [value, setValue] = useState('')
  const items = threads[activeBotId] ?? []
  return (
    <div style={{ height: 600 }}>
      <ChatContainer
        style={{ height: '100%' }}
        bots={BOTS}
        activeBotId={activeBotId}
        onBotChange={setActiveBotId}
        composer={
          <ChatComposer
            value={value}
            onChange={setValue}
            onSubmit={() => setValue('')}
            scopeLabel={BOTS.find((b) => b.id === activeBotId)?.label}
          />
        }
      >
        {items.map((item) =>
          item.kind === 'divider' ? (
            <ChatDivider key={item.id} label={item.label ?? ''} />
          ) : (
            <ChatMessage
              key={item.id}
              role={item.role ?? 'bot'}
              senderName={item.senderName ?? ''}
              timestamp={item.timestamp ?? ''}
              body={<ChatMarkdownContent content={item.text ?? ''} />}
            />
          )
        )}
      </ChatContainer>
    </div>
  )
}
```

### Gotchas

- The root is a flex column with `max-height: 100%`; the thread only scrolls when the container has a bounded height. Give it (or its parent) an explicit height, otherwise it grows with its content.
- `autoScroll` runs on every `children` change. Inline JSX children are new on every parent render, so any re-render jumps to the bottom, even while the user is reading history. Memoize children or set `autoScroll={false}` and manage scrolling yourself.
- Bot tabs are display and selection only: the container does not filter messages by bot. Swap `children` yourself when `activeBotId` changes.
- Bot tabs are toggle buttons (`aria-pressed`) in a `role="group"`, not an ARIA tablist; there is no arrow-key navigation.
- The thread has `role="log"` and `aria-live="polite"`, so new messages are announced.

---

## ChatMarkdownContent

Renders a markdown string (GitHub-flavored) with Heimdall chat typography; the standard renderer for model output in a message body.

```tsx
import { ChatMarkdownContent } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `content` | `string` | required | Markdown source |
| `isStreaming` | `boolean` | `false` | Blinking cursor after the last block; sets `aria-busy` |
| `className` | `string` | — | Extra class on the root `<div>` |
| `syntaxHighlighter` | `(code: string, language: string) => ReactNode` | — | Replaces fenced code blocks that declare a language |

### Usage

```tsx
<ChatMarkdownContent content={'Found **3** failed runs in `svc_ingest`.'} />
```

```tsx
const highlight = (code: string, language: string) => (
  <pre className="app-code" data-language={language}>
    <code>{code}</code>
  </pre>
)

function StreamingReply({ text, done }: { text: string; done: boolean }) {
  return (
    <ChatMessage
      role="bot"
      senderName="analyst"
      badge="ANALYST"
      timestamp="11:04"
      body={<ChatMarkdownContent content={text} isStreaming={!done} syntaxHighlighter={highlight} />}
    />
  )
}
```

### Supported markdown

- CommonMark via `react-markdown` plus `remark-gfm`: tables, strikethrough, task lists, autolinks and footnotes. Both libraries are dependencies of the package; nothing extra to install.
- Styled elements: paragraphs, `h1`–`h3`, lists (nested), blockquotes (amber left border), tables (wrapped in a horizontally scrolling box, mono uppercase headers), inline code, fenced code, `hr`, bold, italic, links.
- `h3` renders as a mono uppercase eyebrow, not a heading. `h4`–`h6` and images get no Heimdall styling.

### Gotchas

- Raw HTML in `content` is not rendered; it appears as literal text. There is no option to enable it.
- URLs pass through react-markdown's default URL transform: `http`, `https`, `mailto`, `irc`, `ircs`, `xmpp` and relative URLs are kept; other protocols (`javascript:`, `data:`, …) become empty.
- Every link opens in a new tab with `rel="noopener noreferrer"`, including relative and `#` links such as footnote references.
- Fenced code without a language tag goes through the inline-code path and gets no `<pre>`, so its line breaks collapse. Always tag fences (` ```text ` for plain output).
- The language is matched with `language-(\w+)`, so `c++` is passed as `c` and `objective-c` as `objective`.
- `syntaxHighlighter` output replaces the whole block, so it must render its own `<pre>`. The code string has its trailing newline removed. Inline code is never passed to it.
- The component is memoized and rebuilds its renderer map when `syntaxHighlighter` changes identity; define it at module level or wrap it in `useCallback`.
- No other props are accepted: no `ref`, no `style`, no DOM attribute spread.
- With `isStreaming`, the cursor attaches after the last top-level block, so it appears after a table or code block, not inside it.
