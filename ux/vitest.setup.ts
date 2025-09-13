import "@testing-library/jest-dom";
import { vi } from "vitest";

// polyfill for createPortal target in jsdom
if (typeof document !== "undefined") {
  const root = document.getElementById("root") || document.createElement("div");
  root.setAttribute("id", "root");
  document.body.appendChild(root);
}

// DOM compatibility fixes for appendChild issues
if (typeof Node !== "undefined") {
  const originalAppendChild = Node.prototype.appendChild;
  Node.prototype.appendChild = function(child) {
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
  Node.prototype.insertBefore = function(newNode, referenceNode) {
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
  value: vi.fn().mockImplementation(query => ({
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
global.IntersectionObserver = class IntersectionObserver {
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
