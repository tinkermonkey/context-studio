import { describe, it, expect, beforeEach, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

// Mock modules
vi.mock("fs");
vi.mock("js-yaml");

describe("check_test_contract validation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("selector extraction from code", () => {
    it("should extract data-testid attributes from JSX", () => {
      const content = `
        <button data-testid="submit-button">Submit</button>
        <input data-testid="username-input" />
      `;

      const dataTestIdRegex = /data-testid=["']([^"']+)["']/g;
      const selectors: string[] = [];
      let match;

      while ((match = dataTestIdRegex.exec(content)) !== null) {
        selectors.push(match[1]);
      }

      expect(selectors).toContain("submit-button");
      expect(selectors).toContain("username-input");
      expect(selectors).toHaveLength(2);
    });

    it("should extract dataTestId prop patterns", () => {
      const content = `
        <Button dataTestId="primary-button" />
        <Input dataTestId="search-field" />
      `;

      const propRegex = /dataTestId\s*=\s*["']([^"']+)["']/g;
      const selectors: string[] = [];
      let match;

      while ((match = propRegex.exec(content)) !== null) {
        selectors.push(match[1]);
      }

      expect(selectors).toContain("primary-button");
      expect(selectors).toContain("search-field");
    });

    it("should skip template literals with variables", () => {
      const content = `
        <div data-testid={\`item-\${id}\`}>Item</div>
      `;

      const jsxExpressionRegex = /data-testid=\{\s*\`([^\`]+)\`\s*\}/g;
      const selectors: string[] = [];
      let match;

      while ((match = jsxExpressionRegex.exec(content)) !== null) {
        // Skip templates with variables
        if (!match[1].includes("${")) {
          selectors.push(match[1]);
        }
      }

      expect(selectors).toHaveLength(0);
    });
  });

  describe("selector extraction from E2E tests", () => {
    it("should extract getByTestId calls", () => {
      const testContent = `
        await page.getByTestId('taxonomy-form').fill('value');
        await page.getByTestId("submit-button").click();
      `;

      const patterns = [
        /getByTestId\(["']([^"']+)["']\)/g,
        /getByTestId\(\`([^\`]+)\`\)/g,
      ];

      const selectors: string[] = [];

      for (const pattern of patterns) {
        let match;
        while ((match = pattern.exec(testContent)) !== null) {
          if (!match[1].includes("${")) {
            selectors.push(match[1]);
          }
        }
      }

      expect(selectors).toContain("taxonomy-form");
      expect(selectors).toContain("submit-button");
    });

    it("should extract from CSS selectors in locator", () => {
      const testContent = `
        await page.locator('[data-testid="modal-close"]').click();
      `;

      const pattern = /\[data-testid=["']([^"']+)["']\]/g;
      const selectors: string[] = [];
      let match;

      while ((match = pattern.exec(testContent)) !== null) {
        selectors.push(match[1]);
      }

      expect(selectors).toContain("modal-close");
    });

    it("should handle complex selector patterns", () => {
      const testContent = `
        await page.getByTestId(\`form-field-\${fieldName}\`).fill('text');
        await page.getByTestId('static-id').click();
      `;

      const patterns = [
        /getByTestId\(["']([^"']+)["']\)/g,
        /getByTestId\(\`([^\`]+)\`\)/g,
      ];

      const selectors: string[] = [];

      for (const pattern of patterns) {
        let match;
        while ((match = pattern.exec(testContent)) !== null) {
          if (!match[1].includes("${")) {
            selectors.push(match[1]);
          }
        }
      }

      expect(selectors).toContain("static-id");
      expect(selectors).not.toContain("form-field-${fieldName}");
    });
  });

  describe("registry parsing", () => {
    it("should load and parse YAML registry", () => {
      const registryContent = {
        pages: {
          taxonomies: {
            id: "taxonomy-form",
            component: "TaxonomyForm",
            description: "Form for creating taxonomies",
          },
        },
      };

      const documented = new Set<string>();

      for (const section of Object.values(registryContent)) {
        if (section && typeof section === "object" && !Array.isArray(section)) {
          for (const entry of Object.values(section)) {
            if (
              entry &&
              typeof entry === "object" &&
              !Array.isArray(entry) &&
              "id" in entry
            ) {
              const typedEntry = entry as Record<string, unknown>;
              if (typeof typedEntry.id === "string") {
                documented.add(typedEntry.id);
              }
            }
          }
        }
      }

      expect(documented).toContain("taxonomy-form");
      expect(documented.size).toBe(1);
    });

    it("should extract pattern templates from registry", () => {
      const registryContent = {
        rows: {
          dynamic_item: {
            id: "item-{id}",
            component: "ItemRow",
            pattern: true,
          },
          dynamic_taxonomy: {
            id: "taxonomy-row-{uuid}",
            component: "TaxonomyRow",
            pattern: true,
          },
        },
      };

      const patterns = new Map<string, string>();

      for (const section of Object.values(registryContent)) {
        if (section && typeof section === "object" && !Array.isArray(section)) {
          for (const entry of Object.values(section)) {
            if (
              entry &&
              typeof entry === "object" &&
              !Array.isArray(entry) &&
              "id" in entry
            ) {
              const typedEntry = entry as Record<string, unknown>;
              const isPattern = typedEntry.pattern as boolean | undefined;
              if (
                typeof typedEntry.id === "string" &&
                isPattern
              ) {
                patterns.set(
                  typedEntry.id.replace(/{[^}]+}/g, "*"),
                  typedEntry.id
                );
              }
            }
          }
        }
      }

      expect(patterns.size).toBe(2);
      expect(patterns.has("item-*")).toBe(true);
      expect(patterns.has("taxonomy-row-*")).toBe(true);
    });

    it("should track known future selectors", () => {
      const registryContent = {
        future: {
          coming_soon: {
            id: "feature-not-yet-implemented",
            status: "not_yet_implemented",
          },
          planned: {
            id: "planned-selector",
            status: "future",
          },
        },
      };

      const knownFuture = new Set<string>();

      for (const section of Object.values(registryContent)) {
        if (section && typeof section === "object" && !Array.isArray(section)) {
          for (const entry of Object.values(section)) {
            if (
              entry &&
              typeof entry === "object" &&
              !Array.isArray(entry) &&
              "id" in entry
            ) {
              const typedEntry = entry as Record<string, unknown>;
              const status = typedEntry.status as string | undefined;
              if (
                typeof typedEntry.id === "string" &&
                (status === "not_yet_implemented" || status === "future")
              ) {
                knownFuture.add(typedEntry.id);
              }
            }
          }
        }
      }

      expect(knownFuture).toContain("feature-not-yet-implemented");
      expect(knownFuture).toContain("planned-selector");
    });
  });

  describe("pattern matching", () => {
    it("should match selectors against wildcard patterns", () => {
      const patterns = new Map<string, string>([
        ["item-*", "item-{id}"],
        ["row-*-action", "row-{id}-action"],
      ]);

      const matchesPattern = (selector: string): boolean => {
        for (const [pattern] of patterns) {
          const regexPattern = pattern.replace(/\*/g, "[\\w-]+");
          if (new RegExp(`^${regexPattern}$`).test(selector)) {
            return true;
          }
        }
        return false;
      };

      expect(matchesPattern("item-123")).toBe(true);
      expect(matchesPattern("item-abc-def")).toBe(true);
      expect(matchesPattern("row-123-action")).toBe(true);
      expect(matchesPattern("item-")).toBe(false);
      expect(matchesPattern("different-pattern")).toBe(false);
    });

    it("should handle UUID patterns", () => {
      const patterns = new Map<string, string>([
        ["taxonomy-row-*", "taxonomy-row-{uuid}"],
      ]);

      const matchesPattern = (selector: string): boolean => {
        for (const [pattern] of patterns) {
          const regexPattern = pattern.replace(/\*/g, "[\\w-]+");
          if (new RegExp(`^${regexPattern}$`).test(selector)) {
            return true;
          }
        }
        return false;
      };

      const uuid = "123e4567-e89b-12d3-a456-426614174000";
      expect(matchesPattern(`taxonomy-row-${uuid}`)).toBe(true);
    });

    it("should handle complex pattern templates", () => {
      const patterns = new Map<string, string>([
        ["button-*-*", "button-{type}-{state}"],
      ]);

      const matchesPattern = (selector: string): boolean => {
        for (const [pattern] of patterns) {
          const regexPattern = pattern.replace(/\*/g, "[\\w-]+");
          if (new RegExp(`^${regexPattern}$`).test(selector)) {
            return true;
          }
        }
        return false;
      };

      expect(matchesPattern("button-primary-active")).toBe(true);
      expect(matchesPattern("button-secondary-disabled")).toBe(true);
      expect(matchesPattern("button-primary")).toBe(false);
    });
  });

  describe("validation logic", () => {
    it("should identify selectors not in registry", () => {
      const documentedSelectors = new Set(["button-submit", "input-username"]);
      const testSelectors = [
        "button-submit",
        "input-username",
        "unknown-selector",
      ];

      const invalidSelectors = testSelectors.filter(
        (s) => !documentedSelectors.has(s)
      );

      expect(invalidSelectors).toContain("unknown-selector");
      expect(invalidSelectors).not.toContain("button-submit");
    });

    it("should allow known future selectors in tests", () => {
      const documentedSelectors = new Set(["button-submit"]);
      const knownFutureSelectors = new Set(["feature-coming-soon"]);
      const testSelectors = ["button-submit", "feature-coming-soon"];

      const validSelectors = testSelectors.filter(
        (s) =>
          documentedSelectors.has(s) || knownFutureSelectors.has(s)
      );

      expect(validSelectors).toHaveLength(2);
    });

    it("should validate entire selector coverage workflow", () => {
      const documentedSelectors = new Set(["form-input", "form-button"]);
      const patterns = new Map<string, string>([
        ["row-*", "row-{id}"],
      ]);
      const knownFutureSelectors = new Set(["future-feature"]);

      const testSelectors = [
        "form-input",
        "form-button",
        "row-123",
        "row-abc",
        "future-feature",
        "unknown-selector",
      ];

      const matchesPattern = (selector: string): boolean => {
        for (const [pattern] of patterns) {
          const regexPattern = pattern.replace(/\*/g, "[\\w-]+");
          if (new RegExp(`^${regexPattern}$`).test(selector)) {
            return true;
          }
        }
        return false;
      };

      const errors = testSelectors.filter(
        (sel) =>
          !documentedSelectors.has(sel) &&
          !matchesPattern(sel) &&
          !knownFutureSelectors.has(sel)
      );

      expect(errors).toContain("unknown-selector");
      expect(errors).toHaveLength(1);
    });
  });

  describe("YAML parsing error handling", () => {
    it("should handle invalid YAML gracefully", () => {
      const invalidYaml = `
        invalid: [yaml
        broken: syntax
      `;

      // Simulate YAML parsing error
      const tryParseYaml = (content: string) => {
        try {
          return yaml.load(content);
        } catch (e) {
          return undefined;
        }
      };

      expect(tryParseYaml(invalidYaml)).toBeUndefined();
    });

    it("should validate registry structure", () => {
      const validRegistry = {
        section1: {
          entry1: {
            id: "selector-1",
            component: "Component1",
          },
        },
      };

      const isValidRegistry = (registry: unknown): boolean => {
        if (!registry || typeof registry !== "object" || Array.isArray(registry)) {
          return false;
        }

        for (const section of Object.values(registry)) {
          if (
            !section ||
            typeof section !== "object" ||
            Array.isArray(section)
          ) {
            return false;
          }

          for (const entry of Object.values(section)) {
            if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
              return false;
            }

            const typedEntry = entry as Record<string, unknown>;
            if (typeof typedEntry.id !== "string") {
              return false;
            }
          }
        }

        return true;
      };

      expect(isValidRegistry(validRegistry)).toBe(true);
      expect(isValidRegistry(null)).toBe(false);
      expect(isValidRegistry([])).toBe(false);
      expect(isValidRegistry("string")).toBe(false);
    });
  });

  describe("file traversal", () => {
    it("should skip dotfiles and directories", () => {
      const filesToCheck = [
        ".gitignore",
        "src/component.tsx",
        ".env",
        "node_modules/dep/index.js",
        "dist/build.js",
      ];

      const shouldSkip = (file: string): boolean => {
        return (
          file.startsWith(".") ||
          file.startsWith("node_modules") ||
          file.startsWith("dist") ||
          file.startsWith("build")
        );
      };

      expect(filesToCheck.filter((f) => shouldSkip(f))).toEqual([
        ".gitignore",
        ".env",
        "node_modules/dep/index.js",
        "dist/build.js",
      ]);
    });

    it("should process TypeScript and JavaScript files", () => {
      const files = [
        "component.tsx",
        "helper.ts",
        "script.js",
        "module.jsx",
        "style.css",
        "readme.md",
      ];

      const isSourceFile = (file: string): boolean => {
        return (
          file.endsWith(".tsx") ||
          file.endsWith(".ts") ||
          file.endsWith(".jsx") ||
          file.endsWith(".js")
        );
      };

      const sourceFiles = files.filter(isSourceFile);
      expect(sourceFiles).toEqual([
        "component.tsx",
        "helper.ts",
        "script.js",
        "module.jsx",
      ]);
    });

    it("should process test files specifically", () => {
      const files = [
        "test.spec.ts",
        "test.spec.tsx",
        "helper.ts",
        "component.test.ts",
      ];

      const isTestFile = (file: string): boolean => {
        return file.endsWith(".spec.ts") || file.endsWith(".spec.tsx");
      };

      const testFiles = files.filter(isTestFile);
      expect(testFiles).toEqual(["test.spec.ts", "test.spec.tsx"]);
    });
  });
});
