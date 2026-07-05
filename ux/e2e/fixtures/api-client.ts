import { Page } from "@playwright/test";

/**
 * Simple API request helper for E2E tests
 */
export async function apiRequest<T>(
  page: Page,
  endpoint: string,
  options?: {
    method?: string;
    body?: unknown;
  },
): Promise<T> {
  const fetchOptions: Parameters<typeof page.request.fetch>[1] = {
    method: options?.method || "GET",
    headers: {
      "Content-Type": "application/json",
    },
  };

  if (options?.body) {
    fetchOptions.data = options.body;
  }

  const response = await page.request.fetch(`http://localhost:8888${endpoint}`, fetchOptions);

  if (!response.ok()) {
    const error = await response.text();
    throw new Error(`API request failed: ${response.status()} ${error}`);
  }

  // 204 No Content (e.g. DELETE) and other empty bodies have no JSON to parse.
  if (response.status() === 204) {
    return undefined as T;
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export class APIError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
