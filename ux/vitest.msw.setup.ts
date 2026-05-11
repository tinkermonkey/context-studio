// Suppress MSW startup messages in test output
import { vi } from "vitest";

vi.stubGlobal("console", {
  ...console,
  log: vi.fn(),
  debug: vi.fn(),
});
