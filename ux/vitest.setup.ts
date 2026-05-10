import "@testing-library/jest-dom";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Mock @tanstack/react-router to handle useSearch gracefully in tests
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return {
    ...actual,
    useSearch: (_options?: Record<string, unknown>) => {
      try {
        // Try to use the real useSearch
        return actual.useSearch?.(_options as any) ?? {};
      } catch {
        // If it fails (no active match), return empty search params
        // This allows components to work in tests without a fully configured router
        return {};
      }
    },
  };
});

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
