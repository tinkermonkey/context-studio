/**
 * Jest test setup for API client testing
 * 
 * This setup file configures the test environment for API client testing
 * without relying on React Native specific imports.
 */

// Mock environment variables
Object.defineProperty(process.env, 'EXPO_PUBLIC_API_URL', {
  value: 'http://localhost:8000',
  writable: true,
  configurable: true,
});

Object.defineProperty(process.env, 'NODE_ENV', {
  value: 'test',
  writable: true,
  configurable: true,
});

// Mock console methods to reduce noise in tests (but not error for testing)
global.console = {
  ...console,
  log: jest.fn(),
  debug: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  // Don't mock error - let tests mock it themselves
};

// Mock fetch for testing
global.fetch = jest.fn();

// Setup fake timers
jest.useFakeTimers();

// Setup and teardown for each test
beforeEach(() => {
  jest.clearAllMocks();
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
  jest.useFakeTimers();
});