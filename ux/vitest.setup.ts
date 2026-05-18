import "@testing-library/jest-dom/vitest";
import React from "react";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Mock @tinkermonkey/heimdall-ui — the package bundles its own React JSX runtime
// which accesses ReactCurrentDispatcher before React initializes in jsdom.
vi.mock("@tinkermonkey/heimdall-ui", () => ({
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
        className: ["text-input", mono && "text-input--mono", error && "text-input--error", className]
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
  Select: React.forwardRef(
    ({ error = false, className = "", children, ...props }: any, ref: any) =>
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
  Sidebar: ({ children, onCollapse, ...props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-sidebar" }, [
      React.createElement(
        "button",
        { key: "toggle", title: "toggle sidebar", onClick: onCollapse },
        "Toggle",
      ),
      children,
    ]),
  Topbar: ({ children, ...props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-topbar" }, children),
  Titlebar: ({ children, ...props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-titlebar" }, children),
  Statusbar: ({ children, ...props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-statusbar" }, children),
  CommandPalette: ({ children, ...props }: any) =>
    React.createElement("div", { "data-testid": "heimdall-command-palette" }, children),
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
