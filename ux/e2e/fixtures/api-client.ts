import { Page } from "@playwright/test";

/**
 * Make an API request to the backend and return the response.
 */
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

  return await response.json();
}
