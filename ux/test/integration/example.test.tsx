import { describe, it, expect } from "vitest";
import { setupMocks } from "../msw/setupTests";

// Example test demonstrating use of MSW helpers. This file is a template
// for writing future integration tests that rely on the centralized handlers.

setupMocks();

describe("msw example", () => {
  it("returns domains list from the mock handler", async () => {
    // Simple smoke: prefer axios client over fetch for consistency with repo.
    // Real tests should render components that use the hooks/services instead
    // of calling the HTTP client directly.
    const { apiClient } = await import("../../src/api/client/axios");
    const res = await apiClient.get("/api/domains");
    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("data");
    expect(Array.isArray(res.data.data)).toBe(true);
  });
});
