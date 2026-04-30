import "@testing-library/jest-dom";
import { vi, beforeEach, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Mock Axios to prevent real HTTP requests during tests
vi.mock("axios", () => {
  return {
    default: {
      create: vi.fn(() => ({
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
        request: vi.fn(() => Promise.resolve({ data: {} })),
        get: vi.fn(() => Promise.resolve({ data: {} })),
        post: vi.fn(() => Promise.resolve({ data: {} })),
        put: vi.fn(() => Promise.resolve({ data: {} })),
        delete: vi.fn(() => Promise.resolve({ data: {} })),
      })),
    },
  };
});

// Mock the API client directly to ensure no HTTP requests are made
vi.mock("@/api/client/axios", () => ({
  apiClient: {
    request: vi.fn(() => Promise.resolve({ data: {} })),
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    defaults: {
      headers: { common: {} },
    },
  },
  updateBaseURL: vi.fn(),
  setAuthToken: vi.fn(),
}));

// Clean up after each test
afterEach(() => {
  cleanup();
});

// Ensure DOM is properly set up before each test
beforeEach(() => {
  // Clean up any existing DOM content
  document.body.innerHTML = "";

  // Create a fresh root element for each test
  const root = document.createElement("div");
  root.setAttribute("id", "root");
  document.body.appendChild(root);
});

// Initial DOM setup for test environment
if (typeof document !== "undefined") {
  // Ensure we have a root element for the initial setup
  if (!document.getElementById("root")) {
    const root = document.createElement("div");
    root.setAttribute("id", "root");
    document.body.appendChild(root);
  }
}

// Enhanced JSDOM setup for better React compatibility
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock IntersectionObserver

(global as any).IntersectionObserver = class IntersectionObserver {
  root: Element | Document | null = null;
  rootMargin = "";
  thresholds: number[] = [];

  constructor(
    _callback: IntersectionObserverCallback,

    _options?: IntersectionObserverInit,
  ) {
    // No-op
  }

  observe(_$target: Element): void {
    // No-op
  }

  unobserve(_$target: Element): void {
    // No-op
  }

  disconnect(): void {
    // No-op
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
};

// Mock ResizeObserver for tests
global.ResizeObserver = class ResizeObserver {
  constructor(_$callback: ResizeObserverCallback) {
    // No-op
  }

  observe(_$target: Element, _options?: ResizeObserverOptions) {
    // No-op
  }

  unobserve(_$target: Element) {
    // No-op
  }
  disconnect() {
    // No-op
  }
};
