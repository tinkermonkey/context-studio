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
          response: { use: vi.fn() }
        },
        request: vi.fn(() => Promise.resolve({ data: {} })),
        get: vi.fn(() => Promise.resolve({ data: {} })),
        post: vi.fn(() => Promise.resolve({ data: {} })),
        put: vi.fn(() => Promise.resolve({ data: {} })),
        delete: vi.fn(() => Promise.resolve({ data: {} }))
      }))
    }
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
      response: { use: vi.fn() }
    },
    defaults: {
      headers: { common: {} }
    }
  },
  updateBaseURL: vi.fn(),
  setAuthToken: vi.fn()
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

// DOM compatibility fixes for appendChild issues
if (typeof Node !== "undefined") {
  const originalAppendChild = Node.prototype.appendChild;
  (Node.prototype as any).appendChild = function (child: any) {
    if (!child || typeof child !== "object") {
      // Create a text node for primitive values
      child = document.createTextNode(String(child));
    }
    if (child && child.nodeType) {
      return originalAppendChild.call(this, child);
    }
    return child;
  };

  const originalInsertBefore = Node.prototype.insertBefore;
  (Node.prototype as any).insertBefore = function (newNode: any, referenceNode: any) {
    if (!newNode || typeof newNode !== "object") {
      newNode = document.createTextNode(String(newNode));
    }
    if (newNode && newNode.nodeType) {
      return originalInsertBefore.call(this, newNode, referenceNode);
    }
    return newNode;
  };
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
  root = null;
  rootMargin = "";
  thresholds: number[] = [];

  constructor(callback: IntersectionObserverCallback) {
    // No-op
  }

  observe(target: Element) {
    // No-op
  }

  unobserve(target: Element) {
    // No-op
  }

  disconnect() {
    // No-op
  }

  takeRecords() {
    return [];
  }
};

// Mock ResizeObserver for tests
global.ResizeObserver = class ResizeObserver {
  constructor(callback: ResizeObserverCallback) {
    // No-op
  }
  observe(target: Element, options?: ResizeObserverOptions) {
    // No-op
  }
  unobserve(target: Element) {
    // No-op
  }
  disconnect() {
    // No-op
  }
};
