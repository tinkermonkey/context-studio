# Vitest Unit Testing Guide for Context Studio Frontend

This guide establishes consistent testing patterns for utility functions, UI components, hooks, and page components in the Context Studio React frontend.

## Table of Contents

1. [Testing Patterns by Category](#testing-patterns-by-category)
2. [Utility Function Tests](#utility-function-tests)
3. [Primitive UI Component Tests](#primitive-ui-component-tests)
4. [Page Component Tests (Five-State Pattern)](#page-component-tests-five-state-pattern)
5. [Mock Conventions](#mock-conventions)
6. [Test Organization](#test-organization)

---

## Testing Patterns by Category

### Quick Reference

| Category | Location | Mock Strategy | Setup Pattern |
|----------|----------|---------------|---------------|
| **Utility Functions** | `src/utils/**/*.ts`, `src/api/utils/**/*.ts` | None (pure functions) | `describe` > `it` |
| **Primitive UI Components** | `src/components/ui/**/*.tsx` | None | `describe` + `container` queries |
| **Custom Hooks (Query/Mutation)** | `src/api/hooks/**/*.ts` | MSW (HTTP intercept) | MSW server + `renderHook` |
| **Page Components** | `src/routes/app/**/*.tsx` | MSW (HTTP intercept) | MSW server + `renderWithProviders` |

---

## Utility Function Tests

Utility functions are **pure functions with no I/O, side effects, or external dependencies**. They should have zero mocking overhead.

### File Locations
- `src/utils/dateFormatting.ts` → test at `src/utils/__tests__/dateFormatting.test.ts`
- `src/utils/formatters.ts` → test at `src/utils/__tests__/formatters.test.ts`
- `src/utils/statusColorUtils.ts` → test at `src/utils/__tests__/statusColorUtils.test.ts`
- `src/api/utils/queryClient.ts` → test at `src/api/utils/__tests__/queryClient.test.ts`

### Pattern: No Fixtures, No Mocks

Test utility functions with simple assertions. No setup, no teardown, no fixtures required.

```typescript
import { describe, it, expect } from "vitest";
import { formatTimeAgo } from "../dateFormatting";

describe("formatTimeAgo", () => {
  describe("relative time formatting", () => {
    it("returns seconds for times less than 60 seconds ago", () => {
      const now = new Date();
      const 30SecondsAgo = new Date(now.getTime() - 30000);
      // Spy on Date.now to control time in tests
      const spy = vi.spyOn(Date, "now").mockReturnValue(now.getTime());
      
      const result = formatTimeAgo(30SecondsAgo);
      expect(result).toBe("30s ago");
      
      spy.mockRestore();
    });

    it("returns minutes for times less than 60 minutes ago", () => {
      const now = new Date();
      const 30MinutesAgo = new Date(now.getTime() - 30 * 60000);
      const spy = vi.spyOn(Date, "now").mockReturnValue(now.getTime());
      
      const result = formatTimeAgo(30MinutesAgo);
      expect(result).toBe("30m ago");
      
      spy.mockRestore();
    });

    it("returns hours for times less than 24 hours ago", () => {
      const now = new Date();
      const 5HoursAgo = new Date(now.getTime() - 5 * 60 * 60000);
      const spy = vi.spyOn(Date, "now").mockReturnValue(now.getTime());
      
      const result = formatTimeAgo(5HoursAgo);
      expect(result).toBe("5h ago");
      
      spy.mockRestore();
    });
  });

  describe("edge cases", () => {
    it("handles edge case at exactly 60 seconds", () => {
      const now = new Date();
      const 60SecondsAgo = new Date(now.getTime() - 60000);
      const spy = vi.spyOn(Date, "now").mockReturnValue(now.getTime());
      
      const result = formatTimeAgo(60SecondsAgo);
      expect(result).toBe("1m ago");
      
      spy.mockRestore();
    });

    it("handles current time", () => {
      const now = new Date();
      const spy = vi.spyOn(Date, "now").mockReturnValue(now.getTime());
      
      const result = formatTimeAgo(now);
      expect(result).toBe("0s ago");
      
      spy.mockRestore();
    });
  });
});
```

### Key Points

1. **No fixtures** — pass data inline to each test
2. **Spy on `Date.now()`** when testing time-dependent functions — don't use `vi.useFakeTimers()` (too heavy)
3. **One assertion per test** (ideally) or group related assertions that test a single behavior
4. **No test utilities** beyond vitest's `describe`, `it`, `expect` and Vitest mocking APIs

---

## Primitive UI Component Tests

Primitive components are small, reusable UI elements with no data-fetching or complex state. Examples: `Button`, `Chip`, `Input`, `Panel`.

### File Locations

- `src/components/ui/Button.tsx` → test at `src/components/ui/__tests__/Button.test.tsx`
- `src/components/ui/Chip.tsx` → test at `src/components/ui/__tests__/Chip.test.tsx`
- `src/components/ui/Input.tsx` → test at `src/components/ui/__tests__/Input.test.tsx`

### Pattern: CSS Classes, ARIA Roles, data-testid

Primitive component tests assert **three categories**:

1. **CSS variant classes** — does the component apply the correct class for each variant prop?
2. **Accessibility attributes** — does it have the correct `role`, `aria-*` attributes?
3. **data-testid and content** — is it instrumented for E2E tests and does it render children?

**Example: Button component**

```typescript
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Button } from "../Button";

describe("Button", () => {
  // ========================================================================
  // CSS Class Variants
  // ========================================================================
  describe("CSS class variants", () => {
    it("applies btn base class", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn");
    });

    it("applies primary variant class", () => {
      render(<Button variant="primary">Click me</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-primary");
    });

    it("applies accent variant class", () => {
      render(<Button variant="accent">Click me</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-accent");
    });

    it("applies ghost variant class by default", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-ghost");
    });

    it("applies danger variant class", () => {
      render(<Button variant="danger">Delete</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-danger");
    });

    it("applies size modifier class", () => {
      render(<Button size="sm">Small</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-sm");
    });
  });

  // ========================================================================
  // Accessibility
  // ========================================================================
  describe("accessibility", () => {
    it("renders as a button element with correct role", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toBeInTheDocument();
    });

    it("has button type by default", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toHaveAttribute("type", "button");
    });

    it("respects disabled attribute for accessibility", () => {
      render(<Button disabled>Disabled</Button>);
      const btn = screen.getByRole("button");
      expect(btn).toBeDisabled();
      expect(btn).toHaveAttribute("disabled");
    });
  });

  // ========================================================================
  // Content & Props
  // ========================================================================
  describe("content rendering", () => {
    it("renders children text", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByText("Click me")).toBeInTheDocument();
    });

    it("renders children elements", () => {
      render(
        <Button>
          <span>Icon</span> Label
        </Button>,
      );
      expect(screen.getByText("Icon")).toBeInTheDocument();
      expect(screen.getByText("Label")).toBeInTheDocument();
    });

    it("accepts custom className prop", () => {
      render(<Button className="custom-class">Click me</Button>);
      const btn = screen.getByRole("button");
      expect(btn).toHaveClass("btn");
      expect(btn).toHaveClass("custom-class");
    });
  });
});
```

**Example: Chip component**

```typescript
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Chip } from "../Chip";

describe("Chip", () => {
  // ========================================================================
  // CSS Class Variants
  // ========================================================================
  describe("CSS class styling", () => {
    it("applies chip base class", () => {
      const { container } = render(<Chip>Tag</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toBeInTheDocument();
    });

    it("applies color class for each variant", () => {
      const colors = ["cyan", "amber", "violet", "emerald", "rose", "gray"] as const;
      
      colors.forEach((color) => {
        const { container } = render(<Chip color={color}>Test</Chip>);
        const chip = container.querySelector(".chip");
        expect(chip).toHaveClass(color);
      });
    });
  });

  // ========================================================================
  // Conditional Content (Color Indicator)
  // ========================================================================
  describe("color indicator dot", () => {
    it("renders dot when color is specified", () => {
      const { container } = render(<Chip color="cyan">Cyan</Chip>);
      const dot = container.querySelector(".dot");
      expect(dot).toBeInTheDocument();
    });

    it("does not render dot when color is not specified", () => {
      const { container } = render(<Chip>No color</Chip>);
      const dot = container.querySelector(".dot");
      expect(dot).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // Content
  // ========================================================================
  describe("content", () => {
    it("renders text content", () => {
      render(<Chip>Tag Label</Chip>);
      expect(screen.getByText("Tag Label")).toBeInTheDocument();
    });

    it("renders element children", () => {
      render(
        <Chip>
          <strong>Bold</strong> Text
        </Chip>,
      );
      expect(screen.getByText("Bold")).toBeInTheDocument();
    });
  });
});
```

### Key Points

1. **Use `screen.getByRole()`** when testing accessibility — it forces you to think about ARIA
2. **Use `container.querySelector()`** for CSS class assertions — you need the element reference
3. **Group tests by concern** — CSS classes, accessibility, content, special behaviors
4. **Test each variant** — use a loop for enum-like props (colors, sizes)
5. **Test negative cases** — when a conditional element should NOT render
6. **No data mocking** — these components are pure rendering

---

## Page Component Tests (Five-State Pattern)

Page components fetch data and render different UIs based on query state. Test **all five states**:

1. **Loading** — skeleton/spinner shown
2. **Empty** — data is success but empty (e.g., `items: []`)
3. **Partial** — small amount of data (covers the happy path)
4. **Error** — query failed, error message shown, retry possible
5. **Populated** — full data set, all features working

### File Locations

- `src/routes/app/settings/__tests__/settings.test.tsx`
- `src/routes/app/schema/__tests__/-taxonomies.test.tsx`
- `src/routes/app/schema/__tests__/-classes.test.tsx`
- `src/routes/app/extraction/__tests__/extraction.test.tsx`
- `src/routes/app/pipelines/__tests__/index.test.tsx`
- `src/routes/app/graph/__tests__/graph.test.tsx`

### Pattern: MSW + renderWithProviders

Use **MSW (Mock Service Worker)** to intercept HTTP calls at the network level. This tests the **full stack** — component → hook → service → network layer.

```typescript
import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { TaxonomiesPage } from "../index";

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

describe("Taxonomies Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays skeleton loading while data is fetching", async () => {
      let resolveRequest: () => void;
      const promise = new Promise<void>((resolve) => {
        resolveRequest = resolve;
      });

      server.use(
        rest.get("*/api/v1/ontology/taxonomies", async (req, res, ctx) => {
          await promise;
          return res(ctx.json({ items: [], total: 0, offset: 0 }));
        }),
      );

      const { container } = render(<TaxonomiesPage />);

      // Wait for loading skeleton to appear
      await waitFor(() => {
        const skeletons = container.querySelectorAll('[style*="skeleton-shimmer"]');
        expect(skeletons.length).toBeGreaterThan(0);
      });

      resolveRequest!();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state message when no taxonomies exist", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, offset: 0 })),
        ),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText(/no taxonomies/i)).toBeInTheDocument();
      });
    });

    it("shows create button in empty state", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, offset: 0 })),
        ),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /create/i })).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Partial State (Happy Path)
  // ========================================================================
  describe("partial state", () => {
    it("displays one taxonomy", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
          res(
            ctx.json({
              items: [
                {
                  id: "tax-1",
                  name: "Test Taxonomy",
                  description: "A test taxonomy",
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ],
              total: 1,
              offset: 0,
            }),
          ),
        ),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Taxonomy")).toBeInTheDocument();
      });
    });

    it("renders table with pagination info", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
          res(
            ctx.json({
              items: [
                {
                  id: "tax-1",
                  name: "Taxonomy 1",
                  description: "First",
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ],
              total: 50,
              offset: 0,
            }),
          ),
        ),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText(/1 of 50/i)).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner on API failure", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Server error" })),
        ),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
      });
    });

    it("provides retry button on error", async () => {
      let callCount = 0;

      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) => {
          callCount++;
          if (callCount === 1) {
            return res(ctx.status(500), ctx.json({ detail: "Server error" }));
          }
          return res(
            ctx.json({
              items: [
                {
                  id: "tax-1",
                  name: "Taxonomy 1",
                  description: "Recovered",
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ],
              total: 1,
              offset: 0,
            }),
          );
        }),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
      });

      const retryButton = screen.getByRole("button", { name: /retry/i });
      await userEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText("Taxonomy 1")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State (Full Data Set)
  // ========================================================================
  describe("populated state", () => {
    it("displays list of taxonomies with all details", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
          res(
            ctx.json({
              items: [
                {
                  id: "tax-1",
                  name: "Animals",
                  description: "Biological classification",
                  created_at: new Date(Date.now() - 86400000).toISOString(),
                  updated_at: new Date(Date.now() - 3600000).toISOString(),
                },
                {
                  id: "tax-2",
                  name: "Colors",
                  description: "Visual spectrum",
                  created_at: new Date(Date.now() - 172800000).toISOString(),
                  updated_at: new Date(Date.now() - 7200000).toISOString(),
                },
                {
                  id: "tax-3",
                  name: "Emotions",
                  description: "Human feelings",
                  created_at: new Date(Date.now() - 259200000).toISOString(),
                  updated_at: new Date(Date.now() - 10800000).toISOString(),
                },
              ],
              total: 3,
              offset: 0,
            }),
          ),
        ),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Animals")).toBeInTheDocument();
        expect(screen.getByText("Colors")).toBeInTheDocument();
        expect(screen.getByText("Emotions")).toBeInTheDocument();
      });
    });

    it("supports pagination", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) => {
          const offset = Number(req.url.searchParams.get("offset")) || 0;

          if (offset === 0) {
            return res(
              ctx.json({
                items: [
                  {
                    id: "tax-1",
                    name: "Page 1",
                    description: "First page",
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                  },
                ],
                total: 50,
                offset: 0,
              }),
            );
          }

          return res(
            ctx.json({
              items: [
                {
                  id: "tax-2",
                  name: "Page 2",
                  description: "Second page",
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ],
              total: 50,
              offset: 25,
            }),
          );
        }),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Page 1")).toBeInTheDocument();
      });

      const nextButton = screen.getByRole("button", { name: /next/i });
      await userEvent.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText("Page 2")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Interactive Behaviors
  // ========================================================================
  describe("interactive behaviors", () => {
    it("opens create modal when add button is clicked", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, offset: 0 })),
        ),
      );

      render(<TaxonomiesPage />);

      const addButton = await screen.findByTestId("taxonomy-add-button");
      await userEvent.click(addButton);

      await waitFor(() => {
        expect(screen.getByTestId("taxonomy-create-modal")).toBeInTheDocument();
      });
    });

    it("opens row context menu when row is clicked", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
          res(
            ctx.json({
              items: [
                {
                  id: "tax-1",
                  name: "Test Taxonomy",
                  description: "Test",
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ],
              total: 1,
              offset: 0,
            }),
          ),
        ),
      );

      render(<TaxonomiesPage />);

      const row = await screen.findByTestId("taxonomy-row-tax-1");
      await userEvent.click(row);

      await waitFor(() => {
        const modal = screen.getByTestId("taxonomy-edit-modal");
        expect(modal).toBeInTheDocument();
      });
    });

    it("searches taxonomies by name", async () => {
      server.use(
        rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) => {
          const search = req.url.searchParams.get("search");
          if (search === "Animal") {
            return res(
              ctx.json({
                items: [
                  {
                    id: "tax-1",
                    name: "Animals",
                    description: "Biological classification",
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                  },
                ],
                total: 1,
                offset: 0,
              }),
            );
          }
          return res(ctx.json({ items: [], total: 0, offset: 0 }));
        }),
      );

      render(<TaxonomiesPage />);

      const searchInput = await screen.findByTestId("taxonomy-search-input");
      await userEvent.type(searchInput, "Animal");

      await waitFor(() => {
        expect(screen.getByText("Animals")).toBeInTheDocument();
      });
    });
  });
});
```

### Key Points

1. **Use MSW for HTTP mocking** — `rest.get()`, `rest.post()`, etc.
2. **Set up server once**, reset handlers between tests
3. **Test all five states** — loading, empty, partial, error, populated
4. **Use `renderWithProviders`** — it includes `QueryClientProvider` and `ToastProvider`
5. **Use `userEvent` for interactions** — `await userEvent.click()`, `await userEvent.type()`
6. **Use `waitFor()` for async assertions** — never `setTimeout` or polling loops
7. **Test the happy path in "partial" state** — small data set, realistic but minimal
8. **Test retry flow in error state** — call handler twice, verify success on retry

---

## Mock Conventions

### When to Mock What

| Dependency | Mock with | Location |
|------------|-----------|----------|
| HTTP calls | MSW (rest.get/post/etc) | Test file or `/test/mocks/handlers.ts` |
| TanStack Query hooks | MSW (data flows through hook) | MSW server |
| Zustand stores | `vi.mock()` + mock factory | Test file after imports |
| Date/Time | `vi.spyOn(Date, 'now')` | Test file, restore after |
| window.matchMedia | Already mocked | `vitest.setup.ts` |
| clipboard API | Already mocked | `vitest.setup.ts` |

### MSW Handler Reuse

If multiple tests use the same API response, create a shared handler file:

**File: `ux/src/test/mocks/handlers.ts`**

```typescript
import { rest } from "msw";

export const ontologyHandlers = {
  listTaxonomies: (items: any[] = [], total: number = 0) =>
    rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
      res(ctx.json({ items, total, offset: 0 })),
    ),
  getTaxonomy: (id: string, data: any) =>
    rest.get(`*/api/v1/ontology/taxonomies/${id}`, (req, res, ctx) =>
      res(ctx.json(data)),
    ),
};

export const pipelineHandlers = {
  listPipelines: (items: any[] = [], total: number = 0) =>
    rest.get("*/api/v1/pipeline/configurations", (req, res, ctx) =>
      res(ctx.json({ items, total, offset: 0 })),
    ),
};

// Error handlers
export const errorHandlers = {
  serverError: (path: string) =>
    rest.get(path, (req, res, ctx) =>
      res(ctx.status(500), ctx.json({ detail: "Server error" })),
    ),
  notFound: (path: string) =>
    rest.get(path, (req, res, ctx) =>
      res(ctx.status(404), ctx.json({ detail: "Not found" })),
    ),
};
```

Then in tests:

```typescript
import { ontologyHandlers } from "@/test/mocks/handlers";

describe("Taxonomies Page", () => {
  it("displays taxonomies when loaded", async () => {
    server.use(
      ontologyHandlers.listTaxonomies(
        [
          { id: "1", name: "Animals", description: "..." },
          { id: "2", name: "Colors", description: "..." },
        ],
        2,
      ),
    );

    render(<TaxonomiesPage />);
    // assertions...
  });
});
```

### Mocking Zustand Stores

If a page uses Zustand stores (e.g., `useCanvasStore`), mock them at the file scope:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@/test/test-utils";
import { SettingsPage } from "../index";

// Mock Zustand stores BEFORE imports that use them
vi.mock("@/stores/canvas", () => ({
  useCanvasStore: vi.fn(),
}));

import { useCanvasStore } from "@/stores/canvas";

describe("Settings Page with Dark Mode", () => {
  beforeEach(() => {
    // Mock the store to return dark mode enabled
    (useCanvasStore as ReturnType<typeof vi.fn>).mockReturnValue({
      darkCanvas: true,
      toggleDarkCanvas: vi.fn(),
    });
  });

  it("applies dark-canvas class to body when dark mode is enabled", async () => {
    render(<SettingsPage />);

    // Dark mode styling should be applied
    expect(document.body).toHaveClass("dark-canvas");
  });
});
```

### Creating Mock Query Results

For testing hooks in isolation (without a page component):

```typescript
import { useQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { rest } from "msw";
import { setupServer } from "msw/node";

const server = setupServer();

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    {children}
  </QueryClientProvider>
);

describe("useTaxonomies hook", () => {
  beforeAll(() => server.listen());
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it("returns empty list when no taxonomies exist", async () => {
    server.use(
      rest.get("*/api/v1/ontology/taxonomies", (req, res, ctx) =>
        res(ctx.json({ items: [], total: 0, offset: 0 })),
      ),
    );

    const { result } = renderHook(() => useTaxonomies(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.items).toEqual([]);
  });
});
```

---

## Test Organization

### Directory Structure

```
ux/src/
├── utils/
│   ├── dateFormatting.ts
│   ├── formatters.ts
│   ├── statusColorUtils.ts
│   └── __tests__/
│       ├── dateFormatting.test.ts
│       ├── formatters.test.ts
│       └── statusColorUtils.test.ts
│
├── api/
│   ├── utils/
│   │   ├── queryClient.ts
│   │   └── __tests__/
│   │       └── queryClient.test.ts
│   ├── services/
│   │   └── __tests__/
│   │       ├── ontology.test.ts
│   │       ├── pipeline.test.ts
│   │       └── ... (service unit tests)
│   └── hooks/
│       └── (hooks tested via page component tests, not in isolation)
│
├── components/
│   ├── ui/
│   │   ├── Button.tsx
│   │   ├── Chip.tsx
│   │   ├── Input.tsx
│   │   └── __tests__/
│   │       ├── Button.test.tsx
│   │       ├── Chip.test.tsx
│   │       └── Input.test.tsx
│   │
│   └── ontology/
│       ├── TaxonomiesTable.tsx
│       ├── ClassesTable.tsx
│       └── __tests__/
│           ├── TaxonomiesTable.test.tsx
│           └── ClassesTable.test.tsx
│
├── routes/
│   └── app/
│       ├── index.tsx (Dashboard)
│       ├── __tests__/
│       │   └── index.test.tsx
│       │
│       ├── schema/
│       │   ├── -taxonomies.tsx
│       │   ├── -classes.tsx
│       │   └── __tests__/
│       │       ├── -taxonomies.test.tsx
│       │       └── -classes.test.tsx
│       │
│       ├── pipelines/
│       │   ├── index.tsx
│       │   └── __tests__/
│       │       └── index.test.tsx
│       │
│       ├── graph/
│       │   ├── index.tsx
│       │   └── __tests__/
│       │       └── graph.test.tsx
│       │
│       ├── extraction/
│       │   ├── index.tsx
│       │   └── __tests__/
│       │       └── extraction.test.tsx
│       │
│       └── settings/
│           ├── index.tsx
│           └── __tests__/
│               └── index.test.tsx
│
└── test/
    ├── test-utils.tsx (renderWithProviders, createTestQueryClient)
    └── mocks/
        ├── handlers.ts (reusable MSW handlers)
        └── stores.ts (reusable Zustand mocks)
```

### Test File Naming

- `FileName.test.tsx` for React components
- `functionName.test.ts` for pure functions
- Match the component/function name exactly

### Running Tests

```bash
cd ux

# Run all tests
npm test

# Run specific test file
npm test Button.test.tsx

# Run tests matching a pattern
npm test --grep "Loading state"

# Run with coverage
npm test -- --coverage
```

---

## Summary

| Type | Pattern | Mocking | Assertions |
|------|---------|---------|------------|
| **Utility** | `describe` > `it` | None | Pure function output |
| **Primitive Component** | Groups: CSS, ARIA, content | None | Class names, roles, content |
| **Page Component** | Five states + behaviors | MSW | Rendered UI, user flow |
| **Store** | Zustand mock factory | `vi.mock()` | Store state propagation |

**Golden Rules:**
1. Test **behavior**, not implementation
2. Use **`screen.getByRole()`** for accessibility
3. Use **MSW** for HTTP, **vi.mock()** for modules
4. **Never use `waitForTimeout`** — assert the expected DOM state
5. **Organize by concern** — loading, error, empty, populated, interaction
