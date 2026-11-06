---
name: heimdall-planning
description: Heimdall component guide for Planning: Calendar, MiniCalendar, KanbanBoard
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## Calendar

Controlled date-based event calendar with month, week, day and agenda views, a header with previous / Today / next buttons, and a view switcher.

```tsx
import { Calendar, type CalendarEvent, type CalendarView } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `view` | `CalendarView` | required | Active view: `'month' \| 'week' \| 'day' \| 'agenda'` |
| `focusedDate` | `Date \| string` | required | Date the view and navigation are anchored to |
| `selectedDate` | `Date \| string` | — | Highlighted date (month view only) |
| `events` | `CalendarEvent[]` | — | Events to place on the calendar |
| `calendarColors` | `Record<string, string>` | — | `calendarId` to CSS color; fallback `rgb(var(--status-cyan))` |
| `weekStartsOn` | `0 \| 1` | `0` | `0` Sunday, `1` Monday |
| `onChangeView` | `(view: CalendarView) => void` | — | View switcher clicked |
| `onNavigate` | `(date: Date) => void` | — | Prev/next/Today buttons and month-view arrow keys |
| `onSelectDate` | `(date: Date) => void` | — | Day cell (month) or day column (week) clicked |
| `onSelectEvent` | `(eventId: string) => void` | — | Event clicked or activated with Enter/Space |
| `renderEvent` | `(event: CalendarEvent, calendarColor?: string) => ReactNode` | — | Replaces the default event title |
| `...divProps` | | | Remaining props spread onto the root `<div>` (`onChange` omitted) |

### Data types

`CalendarView` is `'month' | 'week' | 'day' | 'agenda'`.

`CalendarEvent`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | `string` | Unique id, passed to `onSelectEvent` |
| `title` | `string` (optional) | Display text; falls back to `Event` |
| `calendarId` | `string` | Key into `calendarColors` |
| `startDate` | `Date \| string` | Day the event is placed on |
| `endDate` | `Date \| string` (optional) | Accepted but not read by any view |

### Usage

```tsx
// Minimal: controlled view and focused date
function ReleaseCalendar({ events }: { events: CalendarEvent[] }) {
  const [view, setView] = useState<CalendarView>('month')
  const [focusedDate, setFocusedDate] = useState(new Date(2026, 9, 1))

  return (
    <div style={{ height: 560 }}>
      <Calendar
        view={view}
        focusedDate={focusedDate}
        events={events}
        onChangeView={setView}
        onNavigate={setFocusedDate}
      />
    </div>
  )
}
```

```tsx
// Full: colors per calendar, selection, Monday start, custom event content
const events: CalendarEvent[] = [
  { id: 'evt_4f3a', title: 'Schema migration', calendarId: 'cal_ops', startDate: new Date(2026, 9, 6) },
  { id: 'evt_9b21', title: 'v0.9.0 release', calendarId: 'cal_release', startDate: new Date(2026, 9, 8) },
  { id: 'evt_c7d0', title: 'Index rebuild', calendarId: 'cal_ops', startDate: '2026-10-14T09:00:00' },
]

const calendarColors: Record<string, string> = {
  cal_ops: 'rgb(var(--status-cyan))',
  cal_release: 'rgb(var(--status-emerald))',
}

function OpsCalendar() {
  const [view, setView] = useState<CalendarView>('month')
  const [focusedDate, setFocusedDate] = useState(new Date(2026, 9, 6))
  const [selectedDate, setSelectedDate] = useState<Date>()
  const [selectedEventId, setSelectedEventId] = useState<string>()

  return (
    <div style={{ height: 600 }}>
      <Calendar
        view={view}
        focusedDate={focusedDate}
        selectedDate={selectedDate}
        events={events}
        calendarColors={calendarColors}
        weekStartsOn={1}
        onChangeView={setView}
        onNavigate={setFocusedDate}
        onSelectDate={(date) => {
          setSelectedDate(date)
          setFocusedDate(date)
        }}
        onSelectEvent={setSelectedEventId}
        renderEvent={(event) => (
          <span style={{ fontWeight: event.id === selectedEventId ? 600 : 400 }}>
            {event.title}
          </span>
        )}
      />
    </div>
  )
}
```

### Gotchas

- Fully controlled. `view` and `focusedDate` never change internally: without `onChangeView` the view switcher does nothing, and without `onNavigate` the prev/next/Today buttons and arrow keys do nothing.
- Events are placed only on the calendar day of `startDate`. `endDate` is ignored, so a multi-day event appears on its first day only. No view renders times or a time-slot grid; every event is shown as a title bar, like an all-day item.
- Per view: **month** shows up to 3 events per cell then a non-clickable `+N more`; **week** shows 7 day columns listing every event for each day; **day** lists the events on `focusedDate`, or `No events scheduled`; **agenda** lists every event with `startDate >= focusedDate`, sorted ascending, or `No upcoming events`. Month, week and day keep `events` array order.
- Agenda compares full timestamps. If `focusedDate` is `new Date()` (current time), events earlier today are excluded. Pass a midnight date to include the whole day.
- Prev/next step by one month (month), 7 days (week) or 1 day (day and agenda). Today calls `onNavigate(new Date())`.
- `onSelectDate` fires from month cells and week columns only; the day and agenda views never call it. Out-of-month cells in month view ignore clicks.
- `selectedDate` is only highlighted in month view; week, day and agenda do not show it. Today gets an amber date chip in month view only.
- Keyboard navigation exists in month view only, on the focusable grid: arrows move `focusedDate` by ±1 / ±7 days, PageUp/PageDown by one month, Home/End to the first/last day of the focused week (not today). Each key calls `onNavigate`; the focused cell is outlined. Enter/Space on the grid do not select a date, because the cells themselves are not focusable. Event bars, week columns and day/agenda items are focusable and respond to Enter/Space.
- Date-only ISO strings such as `'2026-10-06'` parse as UTC midnight and can land on the previous day in negative-offset time zones. Use `new Date(2026, 9, 6)` or a local timestamp like `'2026-10-06T09:00:00'`.
- Root is `height: 100%` with a scrolling content area; give the parent an explicit height. Week columns use `minmax(150px, 1fr)` and wrap onto extra rows in narrow containers.
- `renderEvent` replaces only the content inside the event bar; the colored left border, click handler and keyboard handling stay. The agenda date label is colored from `calendarColors` as well.
- Header labels and weekday names are hard-coded `en-US`.

## MiniCalendar

Compact single-month date picker for sidebars, with today and selected-day highlighting and dot markers for days that have events.

```tsx
import { MiniCalendar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `focusedDate` | `Date \| string` | required | Any date in the month to display |
| `selectedDate` | `Date \| string` | — | Highlighted day |
| `markers` | `Date[]` | `[]` | Days that show a marker dot |
| `weekStartsOn` | `0 \| 1` | `0` | `0` Sunday, `1` Monday |
| `onSelect` | `(date: Date) => void` | — | In-month day clicked |
| `className` | `string` | `''` | Extra class on the root `<div>` |

### Usage

```tsx
// Minimal
<MiniCalendar
  focusedDate={new Date(2026, 9, 1)}
  selectedDate={selectedDate}
  onSelect={setSelectedDate}
/>
```

```tsx
// Paired with Calendar: shared focus, markers from event start dates
function PlanningSidebar({ events }: { events: CalendarEvent[] }) {
  const [view, setView] = useState<CalendarView>('day')
  const [focusedDate, setFocusedDate] = useState(new Date(2026, 9, 6))

  return (
    <div style={{ display: 'flex', gap: 16, height: 560 }}>
      <div style={{ width: 260 }}>
        <MiniCalendar
          focusedDate={focusedDate}
          selectedDate={focusedDate}
          markers={events.map((e) => new Date(e.startDate))}
          weekStartsOn={1}
          onSelect={setFocusedDate}
        />
      </div>
      <div style={{ flex: 1 }}>
        <Calendar
          view={view}
          focusedDate={focusedDate}
          events={events}
          weekStartsOn={1}
          onChangeView={setView}
          onNavigate={setFocusedDate}
        />
      </div>
    </div>
  )
}
```

### Gotchas

- No month navigation controls. The displayed month follows `focusedDate`; change it from outside (for example from `Calendar`'s `onNavigate`) to page months.
- Controlled selection: clicking a day only calls `onSelect`. Update `selectedDate` yourself.
- Days from the previous/next month are shown dimmed and ignore clicks, but are still focusable buttons.
- `markers` must be `Date` objects; convert string dates with `new Date(...)`. Matching is by calendar day, time is ignored.
- No arrow-key navigation; each day is a plain `<button>` reached with Tab.
- Accepts only the props listed above; other DOM attributes are not part of its type. Minimum width is 240px.

## KanbanBoard

Column board of cards with pointer drag-and-drop, keyboard moves, per-column counts, WIP-limit warnings and controlled selection.

```tsx
import { KanbanBoard, type KanbanCard, type KanbanColumn } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `columns` | `KanbanColumn[]` | required | Columns in display order |
| `cards` | `KanbanCard[]` | required | All cards; grouped by `columnId`, kept in array order |
| `onMoveCard` | `(cardId: string, toColumnId: string, index: number) => void` | required | Pointer drop or keyboard commit/cancel |
| `selectedId` | `string` | — | Card shown with the selected ring |
| `onSelectCard` | `(cardId: string) => void` | — | Card clicked |
| `renderCard` | `(card: KanbanCard, isSelected: boolean) => ReactNode` | — | Replaces default card content |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

`KanbanColumn`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | `string` | Unique id, matched by `KanbanCard.columnId` |
| `title` | `string` | Header label |
| `statusColor` | `StatusColor` (optional) | Header dot: `emerald`, `amber`, `rose`, `cyan`, `violet`, `neutral` |
| `wipLimit` | `number` (optional) | Shows a warning icon when card count exceeds it |

`KanbanCard`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | `string` | Unique id |
| `columnId` | `string` | Owning column `id` |
| `title` | `string` | Main text |
| `context` | `string` (optional) | Mono eyebrow above the title (`FEATURE`, `BUG`) |
| `version` | `string` (optional) | Rendered as a `VersionPill` |
| `dueDate` | `string` (optional) | Displayed verbatim, not parsed |
| `badges` | `string[]` (optional) | Small mono labels |
| `blocked` | `string` (optional) | Amber blocked banner with this text |
| `done` | `boolean` (optional) | Struck-through, dimmed title |

### Usage

```tsx
// Minimal: cards held in state, moved by remove-then-insert
const columns: KanbanColumn[] = [
  { id: 'backlog', title: 'Backlog', statusColor: 'neutral' },
  { id: 'in_progress', title: 'In progress', statusColor: 'amber', wipLimit: 3 },
  { id: 'done', title: 'Done', statusColor: 'emerald' },
]

function moveCard(prev: KanbanCard[], cardId: string, toColumnId: string, index: number): KanbanCard[] {
  const card = prev.find((c) => c.id === cardId)
  if (!card) return prev
  const rest = prev.filter((c) => c.id !== cardId)
  const target = rest.filter((c) => c.columnId === toColumnId)
  target.splice(index, 0, { ...card, columnId: toColumnId })
  return [...rest.filter((c) => c.columnId !== toColumnId), ...target]
}

function TaskBoard({ initialCards }: { initialCards: KanbanCard[] }) {
  const [cards, setCards] = useState(initialCards)

  return (
    <div style={{ height: 600 }}>
      <KanbanBoard
        columns={columns}
        cards={cards}
        onMoveCard={(cardId, toColumnId, index) =>
          setCards((prev) => moveCard(prev, cardId, toColumnId, index))
        }
      />
    </div>
  )
}
```

```tsx
// Full: selection, rich default cards, custom renderer
const cards: KanbanCard[] = [
  {
    id: 'tsk_4f3a',
    columnId: 'backlog',
    context: 'FEATURE',
    title: 'Add lineage export',
    version: 'v0.9.0',
    badges: ['svc_ingest', 'api'],
  },
  {
    id: 'tsk_9b21',
    columnId: 'in_progress',
    context: 'BUG',
    title: 'Fix stale index on cls_organism',
    dueDate: '2026-11-02',
    blocked: 'Waiting on schema migration',
  },
  { id: 'tsk_c7d0', columnId: 'done', context: 'CHORE', title: 'Rotate ingest keys', done: true },
]

function SprintBoard() {
  const [items, setItems] = useState(cards)
  const [selectedId, setSelectedId] = useState<string>()

  return (
    <div style={{ height: 640 }}>
      <KanbanBoard
        columns={columns}
        cards={items}
        selectedId={selectedId}
        onSelectCard={setSelectedId}
        onMoveCard={(cardId, toColumnId, index) =>
          setItems((prev) => moveCard(prev, cardId, toColumnId, index))
        }
        aria-label="Sprint board"
      />
    </div>
  )
}

function CompactBoard() {
  const [items, setItems] = useState(cards)

  return (
    <div style={{ height: 400 }}>
      <KanbanBoard
        columns={columns}
        cards={items}
        onMoveCard={(cardId, toColumnId, index) =>
          setItems((prev) => moveCard(prev, cardId, toColumnId, index))
        }
        renderCard={(card, isSelected) => (
          <div style={{ padding: 8, fontWeight: isSelected ? 600 : 400 }}>
            <code>{card.id}</code> {card.title}
          </div>
        )}
      />
    </div>
  )
}
```

### Gotchas

- Fully controlled. The board never reorders cards itself; it only calls `onMoveCard`, and the card moves when you update `cards`. Selection is controlled the same way through `selectedId` / `onSelectCard`.
- `onMoveCard` is the only move callback, shared by pointer and keyboard. There is no drag-start, drag-over or cancel callback, and no way to veto a move other than ignoring the call.
- Pointer drag starts on `pointerdown` with no distance threshold and captures the pointer to the card. No ghost card follows the cursor; a 2px insertion line marks the drop slot in the hovered column. Release calls `onMoveCard(cardId, hoveredColumnId, index)` if the pointer moved at all; a click with no movement does not call it. Moving past the last column keeps the last hovered column as the target.
- `index` is the card's final position in the target column after it is removed from its old place, for pointer and keyboard moves alike, so a remove-then-insert handler (as above) is correct as written. (Before 0.9.1, a pointer drag downward within the same column reported one slot too high.)
- Keyboard: focus a card (Tab), press Space to grab, arrows to move, Space again to commit, Escape to cancel. Up/Down move within the column; Left/Right jump to the adjacent column at index 0. Arrow moves only update the insertion line and the live-region announcement; `onMoveCard` fires once on commit. Escape while grabbed calls `onMoveCard` with the original column and index, so the handler must tolerate a no-op move.
- In another column the keyboard can reach indices `0` to `length - 1` of that column, so the last slot of a non-empty target column is reachable only by pointer.
- Enter does not select a card; selection is click only. A cross-column move remounts the card in its new column, so keyboard focus is lost after the commit.
- `renderCard` keeps the wrapper (click, drag, keyboard, selected ring) and replaces only the inner content; the `done` styling and default fields are not applied. Interactive controls inside it start a drag on press; add `onPointerDown={(e) => e.stopPropagation()}` to them.
- Root `onPointerMove` / `onPointerUp` drive the drag and are overwritten if passed through `...divProps`. Column hit-testing uses `document.querySelector('[data-column-id=…]')`, so two boards on one page must not share column ids.
- No `touch-action` is set and `pointercancel` is not handled; on touch devices the browser may scroll instead of dragging.
- Cards whose `columnId` matches no column are not rendered. Empty columns show `Drop cards here`. The count chip shows the column's card count; the WIP warning appears only when count is strictly greater than `wipLimit` and never blocks a drop.
- Root is `height: 100%`; give the parent an explicit height. Columns share width equally with a 300px minimum and the board scrolls horizontally when they do not fit; each column body scrolls vertically on its own.
- Moves are announced through a polite live region (`Card "…" moved to … at position N`).
