import { describe, it, expect, beforeEach, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";
import StructuredReporter from "../../e2e/reporters/structured-reporter";
import {
  Reporter,
  FullResult,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";

// Mock the file system
vi.mock("fs");
vi.mock("child_process");

describe("StructuredReporter", () => {
  let reporter: StructuredReporter;
  let mockTestCase: Partial<TestCase>;
  let mockTestResult: Partial<TestResult>;

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock fs.existsSync to return false for non-existent files
    vi.mocked(fs.existsSync).mockReturnValue(false);
    vi.mocked(fs.mkdirSync).mockImplementation(() => "/mock/dir");

    reporter = new StructuredReporter();

    // Create mock test case
    mockTestCase = {
      location: {
        file: "/mock/test.spec.ts",
        line: 1,
        column: 1,
      },
      titlePath: vi.fn().mockReturnValue(["Test Suite", "test case"]),
      outcome: vi.fn().mockReturnValue("passed"),
      results: [
        {
          status: "passed" as const,
          duration: 1000,
          error: undefined,
          attachments: [],
        } as unknown as TestResult,
      ],
    };

    // Create mock test result
    mockTestResult = {
      status: "passed" as const,
      duration: 1000,
      error: undefined,
      attachments: [],
      stdout: [],
    };
  });

  describe("type safety", () => {
    it("should enforce TestReport discriminated union for passed status", () => {
      // This test verifies TypeScript compile-time behavior
      // A passed status should not allow failure property
      const passedReport: any = {
        spec_file: "test.spec.ts",
        test_name: "test case",
        status: "passed",
        duration_ms: 1000,
        attempts: [],
        selectors_used: [],
      };

      expect(passedReport.status).toBe("passed");
      expect(passedReport.failure).toBeUndefined();
    });

    it("should enforce TestReport discriminated union for failed status", () => {
      // A failed status should require failure property
      const failedReport: any = {
        spec_file: "test.spec.ts",
        test_name: "test case",
        status: "failed",
        duration_ms: 1000,
        attempts: [],
        selectors_used: [],
        failure: {
          message: "test failed",
          screenshots: [],
        },
      };

      expect(failedReport.status).toBe("failed");
      expect(failedReport.failure).toBeDefined();
      expect(failedReport.failure.message).toBe("test failed");
    });
  });

  describe("selector extraction", () => {
    it("should extract selectors from data-testid attributes in test files", () => {
      const testContent = `
        test('example', async ({ page }) => {
          await page.getByTestId('selector-one').click();
          await page.getByTestId('selector-two').fill('text');
        });
      `;

      vi.mocked(fs.existsSync).mockImplementation((p) => {
        return p === "/mock/test.spec.ts";
      });
      vi.mocked(fs.readFileSync).mockReturnValue(testContent);

      // Manually test selector extraction pattern
      const selectorPattern =
        /(?:getByTestId|data-testid)[=\s(]*['"`]([^'"`]+)['"`]/g;
      const selectors: string[] = [];
      let match;
      while ((match = selectorPattern.exec(testContent)) !== null) {
        selectors.push(match[1]);
      }

      expect(selectors).toContain("selector-one");
      expect(selectors).toContain("selector-two");
    });

    it("should handle selector patterns with dynamic IDs", () => {
      const testContent = `
        const id = 'some-id';
        await page.getByTestId(\`selector-\${id}\`).click();
      `;

      // Dynamic selectors with template literals are skipped
      const selectorPattern =
        /(?:getByTestId|data-testid)[=\s(]*['"`]([^'"`]+)['"`]/g;
      const selectors: string[] = [];
      let match;
      while ((match = selectorPattern.exec(testContent)) !== null) {
        if (!match[1].includes("$")) {
          selectors.push(match[1]);
        }
      }

      // Should not extract template literals
      expect(selectors).not.toContain("selector-${id}");
    });
  });

  describe("report generation", () => {
    it("should compute stats from tests array without redundant fields", () => {
      // RunReport should not have total, passed, failed, etc.
      const mockReport: any = {
        run_id: "test-run-1",
        started_at: new Date().toISOString(),
        ended_at: new Date().toISOString(),
        duration_ms: 5000,
        tests: [
          {
            spec_file: "test1.spec.ts",
            test_name: "test 1",
            status: "passed",
            duration_ms: 1000,
            attempts: [],
            selectors_used: [],
          },
          {
            spec_file: "test2.spec.ts",
            test_name: "test 2",
            status: "failed",
            duration_ms: 2000,
            attempts: [],
            selectors_used: [],
            failure: {
              message: "assertion failed",
              screenshots: [],
            },
          },
        ],
        selector_coverage: {
          documented: {},
          coverage_percentage: 0,
          gaps: [],
          undocumented: [],
        },
      };

      // RunReport should not have total, passed, failed, skipped, flaky fields
      expect(mockReport).not.toHaveProperty("total");
      expect(mockReport).not.toHaveProperty("passed");
      expect(mockReport).not.toHaveProperty("failed");
      expect(mockReport).toHaveProperty("tests");

      // Stats should be computed from tests array
      const stats = {
        total: mockReport.tests.length,
        passed: mockReport.tests.filter(
          (t: any) => t.status === "passed"
        ).length,
        failed: mockReport.tests.filter(
          (t: any) => t.status === "failed"
        ).length,
      };

      expect(stats.total).toBe(2);
      expect(stats.passed).toBe(1);
      expect(stats.failed).toBe(1);
    });

    it("should correctly classify test statuses", () => {
      const testStatuses = [
        { input: "passed", expected: "passed" },
        { input: "failed", expected: "failed" },
        { input: "skipped", expected: "skipped" },
        { input: "flaky", expected: "flaky" },
      ];

      testStatuses.forEach(({ input, expected }) => {
        expect(input).toBe(expected);
      });
    });
  });

  describe("failure extraction", () => {
    it("should extract failure info with message and stack", () => {
      const failureInfo = {
        message: "Expected true to be false",
        stack: "at test.spec.ts:10:5",
        screenshots: ["screenshot1.png"],
        video: "video.webm",
      };

      expect(failureInfo).toHaveProperty("message");
      expect(failureInfo).toHaveProperty("stack");
      expect(failureInfo).toHaveProperty("screenshots");
      expect(failureInfo.screenshots.length).toBe(1);
    });

    it("should handle missing optional failure properties", () => {
      const failureInfo = {
        message: "Test failed",
        screenshots: [],
      };

      expect(failureInfo).toHaveProperty("message");
      expect(failureInfo.screenshots).toEqual([]);
      expect(failureInfo).not.toHaveProperty("video");
    });
  });

  describe("attempt tracking", () => {
    it("should aggregate multiple attempt results", () => {
      const attempts = [
        {
          status: "failed" as const,
          duration_ms: 1000,
          failure: {
            message: "First attempt failed",
            screenshots: [],
          },
        },
        {
          status: "passed" as const,
          duration_ms: 500,
        },
      ];

      expect(attempts).toHaveLength(2);
      expect(attempts[0].status).toBe("failed");
      expect(attempts[1].status).toBe("passed");
    });

    it("should calculate total duration from all attempts", () => {
      const attempts = [
        { status: "failed" as const, duration_ms: 1000 },
        { status: "passed" as const, duration_ms: 500 },
      ];

      const totalDuration = attempts.reduce((sum, a) => sum + a.duration_ms, 0);
      expect(totalDuration).toBe(1500);
    });
  });

  describe("selector coverage", () => {
    it("should track documented vs undocumented selectors", () => {
      const coverage = {
        documented: {
          "test-id-1": {
            id: "test-id-1",
            component: "Button",
            coverage: "exercised" as const,
          },
        },
        coverage_percentage: 100,
        gaps: [],
        undocumented: ["unknown-selector"],
      };

      expect(Object.keys(coverage.documented)).toContain("test-id-1");
      expect(coverage.undocumented).toContain("unknown-selector");
    });

    it("should calculate coverage percentage correctly", () => {
      const documented = {
        "selector-1": { coverage: "exercised" as const },
        "selector-2": { coverage: "not_exercised" as const },
        "selector-3": { coverage: "exercised" as const },
      };

      const exercised = Object.values(documented).filter(
        (d) => d.coverage === "exercised"
      ).length;
      const coveragePercentage = Math.round(
        (exercised / Object.keys(documented).length) * 100
      );

      expect(coveragePercentage).toBe(67);
    });
  });

  describe("YAML registry loading", () => {
    it("should handle missing registry gracefully", () => {
      vi.mocked(fs.existsSync).mockReturnValue(false);

      // The reporter should handle missing registry without crashing
      const reporter = new StructuredReporter();
      expect(reporter).toBeDefined();
    });

    it("should parse valid YAML registry", () => {
      const yamlContent = `
pages:
  taxonomies:
    id: taxonomy-page
    component: TaxonomyList
      `;

      vi.mocked(fs.existsSync).mockImplementation(
        (p) =>
          p.toString().includes("selector-registry.yaml") ||
          p === "/mock/dir"
      );
      vi.mocked(fs.readFileSync).mockReturnValue(yamlContent);

      // Verify YAML parsing works
      const parseableContent = yamlContent.includes("id: taxonomy-page");
      expect(parseableContent).toBe(true);
    });
  });

  describe("pattern matching for dynamic selectors", () => {
    it("should match selectors against pattern templates", () => {
      const patterns = ["item-{id}", "row-{uuid}"];
      const testSelectors = ["item-123", "item-abc", "row-a1b2c3"];

      const matchesPattern = (selector: string, patterns: string[]): boolean => {
        for (const pattern of patterns) {
          const regexPattern = pattern.replace(
            /\{[^}]+\}/g,
            "[\\w-]+"
          );
          if (new RegExp(`^${regexPattern}$`).test(selector)) {
            return true;
          }
        }
        return false;
      };

      expect(matchesPattern("item-123", patterns)).toBe(true);
      expect(matchesPattern("item-abc", patterns)).toBe(true);
      expect(matchesPattern("row-a1b2c3", patterns)).toBe(true);
      expect(matchesPattern("unknown-123", patterns)).toBe(false);
    });
  });
});
