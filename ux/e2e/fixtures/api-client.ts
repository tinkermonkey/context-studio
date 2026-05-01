import { Page } from "@playwright/test";

/**
 * Make an API request to the backend and return the response.
 */

// Overload: DELETE returns void
export async function apiRequest(
  page: Page,
  endpoint: string,
  options: { method: "DELETE"; body?: Record<string, unknown>; headers?: Record<string, string> }
): Promise<void>;

// Overload: all other methods return T
export async function apiRequest<T = unknown>(
  page: Page,
  endpoint: string,
  options?: { method?: "GET" | "POST" | "PUT" | "PATCH"; body?: Record<string, unknown>; headers?: Record<string, string> }
): Promise<T>;

// Implementation
export async function apiRequest<T = unknown>(
  page: Page,
  endpoint: string,
  options?: {
    method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
    body?: Record<string, unknown>;
    headers?: Record<string, string>;
  },
): Promise<T | void> {
  const { method = "GET", body, headers = {} } = options || {};

  const response = await page.request.fetch(
    `http://localhost:8888${endpoint}`,
    {
      method,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      data: body ? JSON.stringify(body) : undefined,
    },
  );

  if (!response.ok()) {
    const responseText = await response.text();
    console.error(`API request failed: ${method} ${endpoint}`);
    console.error(`Status: ${response.status()} ${response.statusText()}`);
    console.error(`Response: ${responseText}`);
    throw new Error(
      `API request failed with status ${response.status()}: ${responseText}`,
    );
  }

  // Handle 204 No Content and other empty-body responses
  if (
    response.status() === 204 ||
    response.headers()["content-length"] === "0"
  ) {
    return;
  }

  try {
    return await response.json();
  } catch (error) {
    const responseText = await response.text();
    console.error(`Failed to parse JSON from response: ${method} ${endpoint}`);
    console.error(`Status: ${response.status()} ${response.statusText()}`);
    console.error(`Response body: ${responseText}`);
    throw new Error(
      `Failed to parse JSON from ${method} ${endpoint}: ${error instanceof Error ? error.message : String(error)}. Response: ${responseText.slice(0, 200)}`,
    );
  }
}
