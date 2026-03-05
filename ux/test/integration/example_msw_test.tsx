import { describe, it, expect } from "vitest";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { render, screen } from "@testing-library/react";
import { setupMocks } from "../msw/setupTests";

// Example test demonstrating use of MSW helpers. This file is a template
// for writing future integration tests that rely on the centralized handlers.

setupMocks();

describe("msw example", () => {
  it("returns domains list from the mock handler", async () => {
    // Simple smoke: call the domains list endpoint via fetch and assert the
    // mocked response shape. Real tests should render components that use
    // the hooks/services instead of calling fetch directly.
    const res = await fetch("/api/domains");
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data).toHaveProperty("data");
    expect(Array.isArray(data.data)).toBe(true);
  });
});
