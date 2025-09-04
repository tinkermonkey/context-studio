import '@testing-library/jest-dom';

// polyfill for createPortal target in jsdom
if (typeof document !== 'undefined') {
  const root = document.getElementById('root') || document.createElement('div');
  root.setAttribute('id', 'root');
  document.body.appendChild(root);
}

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
