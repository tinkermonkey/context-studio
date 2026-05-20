import "@testing-library/jest-dom/vitest";
import React from "react";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Mock @tinkermonkey/heimdall-ui — the package bundles its own React JSX runtime
// which accesses ReactCurrentDispatcher before React initializes in jsdom.
vi.mock("@tinkermonkey/heimdall-ui", () => ({
  useFocusTrap: () => {},
  useBodyOverflow: () => {},
  Button: React.forwardRef(
    ({ variant = "primary", size = "md", className = "", children, ...props }: any, ref: any) =>
      React.createElement(
        "button",
        {
          ref,
          className: ["btn", `btn--${variant}`, `btn--${size}`, className]
            .filter(Boolean)
            .join(" "),
          type: "button",
          ...props,
        },
        children,
      ),
  ),
  TextInput: React.forwardRef(
    ({ mono = false, error = false, className = "", ...props }: any, ref: any) =>
      React.createElement("input", {
        ref,
        type: "text",
        className: [
          "text-input",
          mono && "text-input--mono",
          error && "text-input--error",
          className,
        ]
          .filter(Boolean)
          .join(" "),
        ...props,
      }),
  ),
  TextArea: React.forwardRef(
    ({ mono = false, error = false, className = "", ...props }: any, ref: any) =>
      React.createElement("textarea", {
        ref,
        className: ["text-area", mono && "text-area--mono", error && "text-area--error", className]
          .filter(Boolean)
          .join(" "),
        ...props,
      }),
  ),
  Select: React.forwardRef(({ error = false, className = "", children, ...props }: any, ref: any) =>
    React.createElement(
      "select",
      {
        ref,
        className: ["select", error && "select--error", className].filter(Boolean).join(" "),
        ...props,
      },
      children,
    ),
  ),
  Toast: ({ isOpen, onClose, title, subtitle, variant, duration = 4000, ...props }: any) => {
    React.useEffect(() => {
      if (isOpen && duration) {
        const timer = setTimeout(onClose, duration);
        return () => clearTimeout(timer);
      }
    }, [isOpen, duration, onClose]);

    if (!isOpen) return null;

    return React.createElement(
      "div",
      { className: `toast toast--${variant}`, role: "status", "aria-live": "polite", ...props },
      React.createElement("div", { className: "toast__title" }, title),
      subtitle && React.createElement("div", { className: "toast__subtitle" }, subtitle),
      React.createElement(
        "button",
        { className: "toast__close", onClick: onClose, "aria-label": "Dismiss notification" },
        "✕",
      ),
    );
  },
  Modal: React.forwardRef(
    (
      { isOpen, onClose, title, subtitle, children, footer, className = "", ...props }: any,
      ref: any,
    ) => {
      React.useEffect(() => {
        if (isOpen) {
          document.body.style.overflow = "hidden";
        }
        return () => {
          document.body.style.overflow = "";
        };
      }, [isOpen]);

      React.useEffect(() => {
        if (!isOpen) return;
        const handleEscape = (e: KeyboardEvent) => {
          if (e.key === "Escape") {
            onClose();
          }
        };
        document.addEventListener("keydown", handleEscape);
        return () => {
          document.removeEventListener("keydown", handleEscape);
        };
      }, [isOpen, onClose]);

      if (!isOpen) return null;
      const handleBackdropClick = (e: React.MouseEvent) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      };
      return React.createElement(
        "div",
        { className: "modal-backdrop", onClick: handleBackdropClick, ...props, ref },
        React.createElement(
          "div",
          {
            className: ["modal", className].filter(Boolean).join(" "),
            role: "dialog",
            "aria-modal": "true",
          },
          title &&
            React.createElement(
              "div",
              { className: "modal__header" },
              React.createElement(
                "div",
                { className: "modal__header-text" },
                React.createElement("div", { className: "modal__title" }, title),
                subtitle && React.createElement("div", { className: "modal__subtitle" }, subtitle),
              ),
              React.createElement(
                "button",
                {
                  className: "modal__close",
                  onClick: onClose,
                  "aria-label": "Close dialog",
                  type: "button",
                },
                React.createElement("span", {}, "✕"),
              ),
            ),
          React.createElement("div", { className: "modal__body" }, children),
          footer && React.createElement("div", { className: "modal__footer" }, footer),
        ),
      );
    },
  ),
  ConfirmDialog: React.forwardRef(
    (
      {
        isOpen,
        onClose,
        onConfirm,
        title,
        message,
        confirmLabel = "Confirm",
        cancelLabel = "Cancel",
        variant = "primary",
        ...props
      }: any,
      ref: any,
    ) => {
      if (!isOpen) return null;
      return React.createElement(
        "div",
        { className: "modal-backdrop", onClick: onClose, ...props, ref },
        React.createElement(
          "div",
          { className: "modal", role: "dialog", "aria-modal": "true" },
          React.createElement(
            "div",
            { className: "modal__header" },
            React.createElement("div", { className: "modal__title" }, title),
            React.createElement(
              "button",
              { className: "modal__close", onClick: onClose, "aria-label": "Close" },
              "✕",
            ),
          ),
          React.createElement("div", { className: "modal__body" }, message),
          React.createElement(
            "div",
            { className: "modal__footer" },
            React.createElement(
              "button",
              { className: "btn btn--ghost", onClick: onClose },
              cancelLabel,
            ),
            React.createElement(
              "button",
              { className: `btn btn--${variant}`, onClick: onConfirm },
              confirmLabel,
            ),
          ),
        ),
      );
    },
  ),
  Drawer: React.forwardRef(({ isOpen, onClose, title, children, ...props }: any, ref: any) => {
    if (!isOpen) return null;
    const handleBackdropClick = (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    };
    return React.createElement(
      "div",
      { className: "drawer-backdrop", onClick: handleBackdropClick },
      React.createElement(
        "div",
        {
          className: ["drawer", "drawer--right", ...(props.className?.split(" ") || [])]
            .filter(Boolean)
            .join(" "),
          role: "dialog",
          "aria-modal": "true",
          ref,
          ...props,
        },
        title &&
          React.createElement(
            "div",
            { className: "drawer-head" },
            React.createElement("h2", { className: "title" }, title),
            React.createElement(
              "button",
              {
                className: "drawer-close",
                onClick: onClose,
                "aria-label": "Close drawer",
                type: "button",
              },
              React.createElement("span", {}, "✕"),
            ),
          ),
        React.createElement("div", { className: "drawer-body" }, children),
      ),
    );
  }),
  Chip: React.forwardRef(
    (
      { variant = "neutral", form = "default", className = "", children, ...props }: any,
      ref: any,
    ) =>
      React.createElement(
        "span",
        {
          ref,
          className: ["chip", `chip--${variant}`, `chip--${form}`, className]
            .filter(Boolean)
            .join(" "),
          ...props,
        },
        (form === "default" || form === "env") &&
          React.createElement("span", { className: "chip__dot" }),
        children,
      ),
  ),
  Badge: React.forwardRef(
    ({ color = "neutral", className = "", children, ...props }: any, ref: any) =>
      React.createElement(
        "span",
        {
          ref,
          className: ["badge", `badge--${color}`, className].filter(Boolean).join(" "),
          ...props,
        },
        children,
      ),
  ),
  StatusBadge: React.forwardRef(
    ({ color = "neutral", className = "", children, ...props }: any, ref: any) =>
      React.createElement(
        "div",
        {
          ref,
          className: ["status-badge", `status-badge--${color}`, className]
            .filter(Boolean)
            .join(" "),
          ...props,
        },
        children,
      ),
  ),
  Panel: React.forwardRef(
    (
      { title, subtitle, footer, children, bordered = false, className = "", ...props }: any,
      ref: any,
    ) =>
      React.createElement(
        "div",
        {
          ref,
          className: ["panel", bordered && "panel--bordered", className].filter(Boolean).join(" "),
          ...props,
        },
        title &&
          React.createElement(
            "div",
            { className: "panel__header" },
            React.createElement("div", { className: "panel__title" }, title),
            subtitle && React.createElement("div", { className: "panel__subtitle" }, subtitle),
          ),
        React.createElement("div", { className: "panel__body" }, children),
        footer && React.createElement("div", { className: "panel__footer" }, footer),
      ),
  ),
  StatTile: React.forwardRef(
    ({ label, value, delta, color = "cyan", className = "", ...props }: any, ref: any) =>
      React.createElement(
        "div",
        {
          ref,
          className: ["stat-tile", `stat-tile--${color}`, className].filter(Boolean).join(" "),
          ...props,
        },
        React.createElement("div", { className: "stat-tile__label" }, label),
        React.createElement("div", { className: "stat-tile__value" }, value),
        delta &&
          React.createElement(
            "div",
            { className: "stat-tile__meta" },
            React.createElement(
              "span",
              { className: `stat-tile__delta stat-tile__delta--${delta.direction || "up"}` },
              delta.direction === "down" ? "−" : "+",
              Math.abs(delta.value),
            ),
            delta.label &&
              React.createElement("span", { className: "stat-tile__label-secondary" }, delta.label),
          ),
      ),
  ),
  TabBar: React.forwardRef(
    ({ tabs, activeTabId, onSelectTab, className = "", ...props }: any, ref: any) =>
      React.createElement(
        "div",
        {
          ref,
          className: ["tabbar", className].filter(Boolean).join(" "),
          role: "tablist",
          ...props,
        },
        tabs.map((tab: any) =>
          React.createElement(
            "button",
            {
              key: tab.id,
              className: ["tab", activeTabId === tab.id ? "active" : ""].filter(Boolean).join(" "),
              onClick: () => onSelectTab(tab.id),
              role: "tab",
              "aria-selected": activeTabId === tab.id,
            },
            tab.label,
          ),
        ),
      ),
  ),
  Table: React.forwardRef(
    (
      {
        columns = [],
        data = [],
        rowKey = "id",
        selectable = true,
        selectedRows = [],
        _onSelectRows,
        _onSort,
        className = "",
        ...props
      }: any,
      ref: any,
    ) => {
      const getRowKey = (row: any, index: number) => {
        if (typeof rowKey === "function") {
          return rowKey(row, index);
        }
        return row[rowKey];
      };

      return React.createElement(
        "table",
        {
          ref,
          className: ["table", className].filter(Boolean).join(" "),
          ...props,
        },
        React.createElement(
          "thead",
          { className: "table__head" },
          React.createElement(
            "tr",
            { className: "table__row" },
            selectable &&
              React.createElement(
                "th",
                { className: "table__header table__header--checkbox", style: { width: "30px" } },
                React.createElement("input", {
                  type: "checkbox",
                  className: "table__checkbox",
                  checked: selectedRows.length === data.length && data.length > 0,
                  onChange: () => {},
                }),
              ),
            columns.map((column: any) =>
              React.createElement(
                "th",
                {
                  key: String(column.key),
                  className: `table__header ${column.sortable ? "table__header--sortable" : ""}`,
                  style: { width: column.width },
                },
                column.label,
              ),
            ),
          ),
        ),
        React.createElement(
          "tbody",
          { className: "table__body" },
          data.map((row: any, index: number) => {
            const rowKeyValue = getRowKey(row, index);
            return React.createElement(
              "tr",
              {
                key: rowKeyValue,
                "data-row-key": rowKeyValue,
                className: `table__row ${selectedRows.includes(rowKeyValue) ? "table__row--selected" : ""}`,
              },
              selectable &&
                React.createElement(
                  "td",
                  { className: "table__cell table__cell--checkbox" },
                  React.createElement("input", {
                    type: "checkbox",
                    className: "table__checkbox",
                    checked: selectedRows.includes(rowKeyValue),
                    onChange: () => {},
                  }),
                ),
              columns.map((column: any) =>
                React.createElement(
                  "td",
                  { key: `${rowKeyValue}-${String(column.key)}`, className: "table__cell" },
                  column.render
                    ? column.render(row[column.key as keyof typeof row], row, index)
                    : row[column.key as keyof typeof row],
                ),
              ),
            );
          }),
        ),
      );
    },
  ) as any,
  StatGrid: React.forwardRef(({ columns = 4, children, className = "", ...props }: any, ref: any) =>
    React.createElement(
      "div",
      {
        ref,
        className: ["stat-grid", className].filter(Boolean).join(" "),
        style: {
          display: "grid",
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gap: "14px",
          ...props.style,
        },
        ...props,
      },
      children,
    ),
  ),
  Sidebar: ({ children, onCollapse, ..._props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-sidebar" }, [
      React.createElement(
        "button",
        { key: "toggle", title: "toggle sidebar", onClick: onCollapse },
        "Toggle",
      ),
      children,
    ]),
  Topbar: ({ children, ..._props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-topbar" }, children),
  Titlebar: ({ children, ..._props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-titlebar" }, children),
  Statusbar: ({ children, ..._props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-statusbar" }, children),
  CommandPalette: ({ children, ..._props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-command-palette" }, children),
  Icon: ({ name, ...props }: any) =>
    React.createElement("span", { "data-icon": name, ...props }, name),
  NavItem: ({ _icon, label, active = false, ...props }: any) =>
    React.createElement(
      "div",
      {
        className: ["nav-item", active && "nav-item--active"].filter(Boolean).join(" "),
        "aria-current": active ? "page" : undefined,
        ...props,
      },
      label,
    ),
  Field: React.forwardRef(
    ({ label, required = false, error, hint, children, className = "", ...props }: any, ref: any) =>
      React.createElement(
        "div",
        {
          className: ["field", error && "field--error", className].filter(Boolean).join(" "),
          ref,
          ...props,
        },
        label &&
          React.createElement(
            "div",
            { className: "field__label" },
            React.createElement(
              "span",
              {},
              label,
              required && React.createElement("span", { className: "field__required" }, "*"),
            ),
          ),
        children,
        error && React.createElement("div", { className: "field__error" }, error),
        hint && React.createElement("div", { className: "field__hint" }, hint),
      ),
  ),
  NumberInput: React.forwardRef(
    ({ mono = false, error = false, className = "", ...props }: any, ref: any) =>
      React.createElement("input", {
        ref,
        type: "number",
        className: [
          "number-input",
          mono && "number-input--mono",
          error && "number-input--error",
          className,
        ]
          .filter(Boolean)
          .join(" "),
        ...props,
      }),
  ),
  TriState: React.forwardRef(
    (
      { indeterminate = false, checked = false, onChange, className = "", ...props }: any,
      ref: any,
    ) =>
      React.createElement("input", {
        ref,
        type: "checkbox",
        checked: !indeterminate && checked,
        className: [
          "tri-state",
          indeterminate && "tri-state--indeterminate",
          checked && "tri-state--checked",
          className,
        ]
          .filter(Boolean)
          .join(" "),
        onChange: (e: any) => {
          let newState;
          if (indeterminate) {
            newState = true;
          } else if (checked) {
            newState = null;
          } else {
            newState = true;
          }
          onChange?.({ ...e, target: { ...e.target, checked: newState } });
        },
        ...props,
      }),
  ),
  PageHeader: React.forwardRef(
    ({ eyebrow, title, subtitle, idChip, actions, className = "", ...props }: any, ref: any) =>
      React.createElement(
        "div",
        {
          ref,
          className: ["page-header", className].filter(Boolean).join(" "),
          "data-testid": "page-header",
          ...props,
        },
        eyebrow && React.createElement("div", { className: "page-header__eyebrow" }, eyebrow),
        title && React.createElement("h1", { className: "page-header__title" }, title),
        subtitle && React.createElement("div", { className: "page-header__subtitle" }, subtitle),
        idChip && React.createElement("div", { className: "page-header__id-chip" }, idChip),
        actions && React.createElement("div", { className: "page-header__actions" }, actions),
      ),
  ),
  ActivityTimeline: ({ events = [], emptyState, className = "", ...props }: any) =>
    React.createElement(
      "div",
      {
        className: ["activity-timeline", className].filter(Boolean).join(" "),
        "data-testid": "activity-timeline",
        ...props,
      },
      events.length > 0
        ? events.map((event: any, index: number) =>
            React.createElement(
              "div",
              { key: index, className: "activity-timeline__item" },
              event.label || event.type,
            ),
          )
        : emptyState &&
            React.createElement("div", { className: "activity-timeline__empty" }, emptyState),
    ),
  GraphCanvas: ({ nodes = [], edges = [], className = "", ...props }: any) =>
    React.createElement(
      "div",
      {
        className: ["graph-canvas", className].filter(Boolean).join(" "),
        "data-testid": "graph-canvas",
        ...props,
      },
      `Graph with ${nodes.length} nodes and ${edges.length} edges`,
    ),
}));

// Mock window.scrollTo to avoid jsdom "Not implemented" errors
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;

// Set up a mock clipboard API for testing - create it at global scope
const mockClipboardWriteText = vi.fn().mockResolvedValue(undefined);
Object.defineProperty(navigator, "clipboard", {
  value: {
    writeText: mockClipboardWriteText,
  },
  configurable: true,
  writable: true,
});
(globalThis as any).__mockClipboardWriteText = mockClipboardWriteText;

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  document.body.innerHTML = "";
  const root = document.createElement("div");
  root.setAttribute("id", "root");
  document.body.appendChild(root);
});

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

(global as any).IntersectionObserver = class IntersectionObserver {
  root: Element | Document | null = null;
  rootMargin = "";
  thresholds: number[] = [];
  constructor(_callback: IntersectionObserverCallback, _options?: IntersectionObserverInit) {}
  observe(_target: Element): void {}
  unobserve(_target: Element): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
};

global.ResizeObserver = class ResizeObserver {
  constructor(_callback: ResizeObserverCallback) {}
  observe(_target: Element, _options?: ResizeObserverOptions) {}
  unobserve(_target: Element) {}
  disconnect() {}
};

// Mock TanStack Router to provide synchronous rendering in tests
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useRouter: () => ({
      state: { status: "idle" },
      navigate: vi.fn(),
    }),
    useRouterState: () => ({
      location: { pathname: "/app" },
      status: "idle",
    }),
    useSearch: () => ({}),
    useMatch: () => ({
      pathname: "/app",
      params: {},
      search: {},
    }),
  };
});
