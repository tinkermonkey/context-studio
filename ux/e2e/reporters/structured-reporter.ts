import {
  Reporter,
  FullResult,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";
import * as fs from "fs";
import * as path from "path";
import { execSync } from "child_process";
import * as yaml from "js-yaml";

type TestReport =
  | {
      spec_file: string;
      test_name: string;
      status: "passed" | "skipped";
      duration_ms: number;
      attempts: AttemptReport[];
      selectors_used: string[];
      failure?: never;
    }
  | {
      spec_file: string;
      test_name: string;
      status: "failed" | "flaky";
      duration_ms: number;
      attempts: AttemptReport[];
      selectors_used: string[];
      failure: FailureReport;
    };

interface AttemptReport {
  status: "passed" | "failed" | "skipped";
  duration_ms: number;
  failure?: FailureReport;
}

interface FailureReport {
  message: string;
  stack?: string;
  screenshots: string[];
  video?: string;
}

interface RunReport {
  run_id: string;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  tests: TestReport[];
  selector_coverage: SelectorCoverage;
}

// Computed properties for RunReport
interface RunReportStats {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  flaky: number;
}

function computeRunStats(tests: TestReport[]): RunReportStats {
  return {
    total: tests.length,
    passed: tests.filter((t) => t.status === "passed").length,
    failed: tests.filter((t) => t.status === "failed").length,
    skipped: tests.filter((t) => t.status === "skipped").length,
    flaky: tests.filter((t) => t.status === "flaky").length,
  };
}

interface DocumentedSelector {
  id: string;
  component: string;
  coverage: "exercised" | "not_exercised";
}

interface SelectorCoverage {
  documented: Record<string, DocumentedSelector>;
  coverage_percentage: number;
  gaps: string[];
  undocumented: string[];
}

interface RegistryEntry {
  id: string;
  component: string;
  [key: string]: unknown;
}

interface SelectorRegistry {
  [key: string]: RegistryEntry | SelectorRegistry;
}

export default class StructuredReporter implements Reporter {
  private reportDir: string;
  private startTime: number = 0;
  private tests: TestReport[] = [];
  private selectorRegistry: SelectorRegistry = {};
  private usedSelectors: Set<string> = new Set();

  constructor() {
    this.reportDir = path.join(__dirname, "..", "reports");
    if (!fs.existsSync(this.reportDir)) {
      fs.mkdirSync(this.reportDir, { recursive: true });
    }
    this.loadSelectorRegistry();
  }

  private loadSelectorRegistry(): void {
    const registryPath = path.join(__dirname, "..", "..", "selector-registry.yaml");
    if (fs.existsSync(registryPath)) {
      try {
        const content = fs.readFileSync(registryPath, "utf-8");
        const parsed = yaml.load(content) as SelectorRegistry;
        this.selectorRegistry = parsed || {};
      } catch (error) {
        console.error(
          `Failed to load selector registry from ${registryPath}:`,
          error instanceof Error ? error.message : String(error)
        );
        this.selectorRegistry = {};
      }
    }
  }

  onBegin(): void {
    this.startTime = Date.now();
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const specFile = test.location.file;
    const testTitle = test.titlePath().join(" > ");

    // Find existing test report if it's being retried
    const existingIndex = this.tests.findIndex((t) => {
      // Match by spec file and full test path (including describe hierarchy)
      return t.spec_file === specFile && t.test_name === testTitle;
    });

    const testStatus = this.computeTestStatus(test);

    // For duration, sum all attempts
    const totalDuration = test.results.reduce((sum, r) => sum + r.duration, 0);

    // For failure info on flaky tests, extract from the first failed attempt
    let failureInfo: FailureReport | undefined;
    if (testStatus === "failed" || testStatus === "flaky") {
      const firstFailedResult = test.results.find((r) => r.status === "failed");
      failureInfo = firstFailedResult
        ? this.extractFailureInfo(firstFailedResult)
        : undefined;
    }

    // Collect selectors from all attempts and the test file
    const allSelectors = this.extractSelectorsFromTest(test, result);

    // Create report with proper discriminated union typing
    let testReport: TestReport;
    if (testStatus === "failed" || testStatus === "flaky") {
      testReport = {
        spec_file: specFile,
        test_name: testTitle,
        status: testStatus,
        duration_ms: totalDuration,
        attempts: this.extractAttempts(test),
        selectors_used: allSelectors,
        failure: failureInfo || {
          message: "Test failed without error details",
          screenshots: [],
        },
      };
    } else {
      testReport = {
        spec_file: specFile,
        test_name: testTitle,
        status: testStatus,
        duration_ms: totalDuration,
        attempts: this.extractAttempts(test),
        selectors_used: allSelectors,
      };
    }

    if (existingIndex >= 0) {
      // Update existing test report with new outcome (handles retries)
      this.tests[existingIndex] = testReport;
    } else {
      // First time seeing this test
      this.tests.push(testReport);
    }

    allSelectors.forEach((s) => this.usedSelectors.add(s));
  }

  onEnd(_result: FullResult): void {
    const endTime = Date.now();
    const timestamp = new Date()
      .toISOString()
      .replace(/[:.]/g, "-")
      .slice(0, -5);
    const gitSha = this.getGitSha();
    const runId = `${timestamp}_${gitSha}`;

    const selectorCoverage = this.buildSelectorCoverage();

    const report: RunReport = {
      run_id: runId,
      started_at: new Date(this.startTime).toISOString(),
      ended_at: new Date(endTime).toISOString(),
      duration_ms: endTime - this.startTime,
      tests: this.tests,
      selector_coverage: selectorCoverage,
    };

    this.writeJsonReport(report, runId);
    this.writeMarkdownReport(report, runId);
    this.pruneOldReports();
  }

  private computeTestStatus(test: TestCase): "passed" | "failed" | "skipped" | "flaky" {
    const outcome = test.outcome();
    if (outcome === "skipped") return "skipped";
    if (outcome === "flaky") return "flaky";
    if (outcome === "unexpected") return "failed";
    return "passed";
  }

  private extractAttempts(test: TestCase): AttemptReport[] {
    return test.results.map((result) => ({
      status: result.status as "passed" | "failed" | "skipped",
      duration_ms: result.duration,
      failure: result.status === "failed" ? this.extractFailureInfo(result) : undefined,
    }));
  }

  private extractFailureInfo(result: TestResult): FailureReport {
    const failure: FailureReport = {
      message: result.error?.message || "Unknown error",
      stack: result.error?.stack,
      screenshots: result.attachments
        .filter((a) => a.name === "screenshot" && a.path)
        .map((a) => a.path!),
      video: result.attachments.find((a) => a.name === "video")?.path,
    };
    return failure;
  }

  private extractSelectorsFromTest(test: TestCase, result: TestResult): string[] {
    const selectors = new Set<string>();

    // Extract from test location source if available
    const testFile = test.location.file;
    if (testFile && fs.existsSync(testFile)) {
      try {
        const source = fs.readFileSync(testFile, "utf-8");
        // Look for getByTestId calls in the entire test file
        const selectorPattern = /(?:getByTestId|data-testid)[=\s(]*['"`]([^'"`]+)['"`]/g;
        let match;
        while ((match = selectorPattern.exec(source)) !== null) {
          selectors.add(match[1]);
        }
      } catch (error) {
        console.warn(
          `Failed to read test file ${testFile}:`,
          error instanceof Error ? error.message : String(error)
        );
      }
    }

    // Extract from stdout in the result
    for (const output of result.stdout) {
      if (typeof output === "string") {
        const pattern = /getByTestId[=\s(]*['"`]([^'"`]+)['"`]/g;
        let match;
        while ((match = pattern.exec(output)) !== null) {
          selectors.add(match[1]);
        }
      }
    }

    return Array.from(selectors).sort();
  }

  private buildSelectorCoverage(): SelectorCoverage {
    const documented: Record<string, DocumentedSelector> = {};
    const gaps: string[] = [];
    const undocumented: string[] = [];

    // Flatten the registry structure
    const flatRegistry = this.flattenRegistry(this.selectorRegistry);
    const patternRegistry = this.extractPatternTemplates(this.selectorRegistry);

    // Check coverage
    for (const [_key, entry] of Object.entries(flatRegistry)) {
      const id = entry.id;
      if (this.usedSelectors.has(id)) {
        documented[id] = {
          id,
          component: entry.component || "Unknown",
          coverage: "exercised",
        };
      } else {
        documented[id] = {
          id,
          component: entry.component || "Unknown",
          coverage: "not_exercised",
        };
        gaps.push(id);
      }
    }

    // Find undocumented selectors
    Array.from(this.usedSelectors).forEach((selector) => {
      if (
        !flatRegistry[selector] &&
        !this.matchesPatternTemplate(selector, patternRegistry)
      ) {
        undocumented.push(selector);
      }
    });

    const coveredCount = Object.values(documented).filter(
      (d) => d.coverage === "exercised"
    ).length;
    const coveragePercentage =
      Object.keys(documented).length > 0
        ? Math.round((coveredCount / Object.keys(documented).length) * 100)
        : 0;

    return {
      documented,
      coverage_percentage: coveragePercentage,
      gaps,
      undocumented,
    };
  }

  private flattenRegistry(
    registry: SelectorRegistry,
    result: Record<string, RegistryEntry> = {}
  ): Record<string, RegistryEntry> {
    for (const [_key, value] of Object.entries(registry)) {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        if ("id" in value) {
          result[(value as RegistryEntry).id] = value as RegistryEntry;
        } else {
          this.flattenRegistry(value as SelectorRegistry, result);
        }
      }
    }
    return result;
  }

  private extractPatternTemplates(
    registry: SelectorRegistry,
    result: string[] = []
  ): string[] {
    for (const [_key, value] of Object.entries(registry)) {
      if (!value || typeof value !== "object" || Array.isArray(value)) {
        continue;
      }

      // Check if this is a registry entry (has 'id' property)
      if ("id" in value) {
        const entry = value as RegistryEntry;
        if (typeof entry.id === "string" && entry.id.includes("{") && entry.id.includes("}")) {
          result.push(entry.id);
        }
      } else {
        // Recursively search nested registries
        this.extractPatternTemplates(value as SelectorRegistry, result);
      }
    }
    return result;
  }

  private matchesPatternTemplate(
    selector: string,
    patterns: string[]
  ): boolean {
    for (const pattern of patterns) {
      // Split pattern into literal and placeholder parts
      const parts = pattern.split(/(\{[^}]+\})/);
      const regexPattern = parts
        .map((part) => {
          // Placeholder parts: replace with flexible ID pattern
          if (part.startsWith("{") && part.endsWith("}")) {
            return "[a-zA-Z0-9_-]+";
          }
          // Literal parts: escape regex special characters
          return part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        })
        .join("");

      const regex = new RegExp(`^${regexPattern}$`);
      if (regex.test(selector)) {
        return true;
      }
    }
    return false;
  }

  private writeJsonReport(report: RunReport, runId: string): void {
    const filePath = path.join(this.reportDir, `${runId}.json`);
    try {
      fs.writeFileSync(filePath, JSON.stringify(report, null, 2));
      console.log(`\n📊 Structured report written to ${filePath}`);
    } catch (error) {
      console.error(
        `Failed to write JSON report to ${filePath}:`,
        error instanceof Error ? error.message : String(error)
      );
    }
  }

  private writeMarkdownReport(report: RunReport, runId: string): void {
    const filePath = path.join(this.reportDir, `${runId}.md`);

    try {
      const stats = computeRunStats(report.tests);

      let markdown = `# Test Run Report\n\n`;
      markdown += `**Run ID:** ${report.run_id}\n`;
      markdown += `**Started:** ${report.started_at}\n`;
      markdown += `**Ended:** ${report.ended_at}\n`;
      markdown += `**Duration:** ${(report.duration_ms / 1000).toFixed(2)}s\n\n`;

      // Summary stats
      markdown += `## Summary\n\n`;
      markdown += `| Metric | Count | Percentage |\n`;
      markdown += `|--------|-------|------------|\n`;
      markdown += `| Total | ${stats.total} | 100% |\n`;
      markdown += `| Passed | ${stats.passed} | ${stats.total > 0 ? Math.round((stats.passed / stats.total) * 100) : 0}% |\n`;
      markdown += `| Failed | ${stats.failed} | ${stats.total > 0 ? Math.round((stats.failed / stats.total) * 100) : 0}% |\n`;
      markdown += `| Flaky | ${stats.flaky} | ${stats.total > 0 ? Math.round((stats.flaky / stats.total) * 100) : 0}% |\n`;
      markdown += `| Skipped | ${stats.skipped} | ${stats.total > 0 ? Math.round((stats.skipped / stats.total) * 100) : 0}% |\n\n`;

      // Selector coverage
      markdown += `## Selector Coverage\n\n`;
      const exercisedCount = Object.values(report.selector_coverage.documented).filter(
        (d) => d.coverage === "exercised"
      ).length;
      markdown += `**Coverage:** ${report.selector_coverage.coverage_percentage}% (${exercisedCount}/${Object.keys(report.selector_coverage.documented).length} documented selectors exercised)\n\n`;

      if (report.selector_coverage.gaps.length > 0) {
        markdown += `### Coverage Gaps (Documented but not exercised)\n\n`;
        markdown += report.selector_coverage.gaps.map((s) => `- \`${s}\``).join("\n");
        markdown += `\n\n`;
      }

      if (report.selector_coverage.undocumented.length > 0) {
        markdown += `### Undocumented Selectors (Used but not in registry)\n\n`;
        markdown += report.selector_coverage.undocumented
          .map((s) => `- \`${s}\``)
          .join("\n");
        markdown += `\n\n`;
      }

      // Test details
      markdown += `## Test Details\n\n`;
      for (const test of report.tests) {
        const statusEmoji = {
          passed: "✅",
          failed: "❌",
          skipped: "⏭️",
          flaky: "⚠️",
        }[test.status];

        markdown += `### ${statusEmoji} ${test.test_name}\n`;
        markdown += `- **File:** ${test.spec_file}\n`;
        markdown += `- **Status:** ${test.status}\n`;
        markdown += `- **Duration:** ${test.duration_ms}ms\n`;

        if (test.selectors_used.length > 0) {
          markdown += `- **Selectors used:** ${test.selectors_used.map((s) => `\`${s}\``).join(", ")}\n`;
        }

        if (test.failure) {
          markdown += `- **Error:** ${test.failure.message}\n`;
          if (test.failure.screenshots.length > 0) {
            markdown += `- **Screenshots:** ${test.failure.screenshots.map((s) => `[${path.basename(s)}](${s})`).join(", ")}\n`;
          }
          if (test.failure.video) {
            markdown += `- **Video:** [${path.basename(test.failure.video)}](${test.failure.video})\n`;
          }
        }

        if (test.attempts.length > 1) {
          markdown += `- **Attempts:** ${test.attempts.length}\n`;
        }

        markdown += `\n`;
      }

      fs.writeFileSync(filePath, markdown);
      console.log(`📄 Markdown summary written to ${filePath}`);
    } catch (error) {
      console.error(
        `Failed to write markdown report to ${filePath}:`,
        error instanceof Error ? error.message : String(error)
      );
    }
  }

  private getGitSha(): string {
    try {
      const sha = execSync("git rev-parse --short HEAD", { encoding: "utf-8" }).trim();
      return sha;
    } catch {
      return "unknown";
    }
  }

  private pruneOldReports(): void {
    const maxReports = 20;
    try {
      const files = fs
        .readdirSync(this.reportDir)
        .filter((f) => f.endsWith(".json"))
        .sort()
        .reverse();

      if (files.length > maxReports) {
        const filesToDelete = files.slice(maxReports);
        let deletedCount = 0;
        for (const file of filesToDelete) {
          const jsonPath = path.join(this.reportDir, file);
          const mdPath = path.join(this.reportDir, file.replace(".json", ".md"));
          try {
            fs.unlinkSync(jsonPath);
            deletedCount++;
          } catch (error) {
            console.warn(
              `Failed to delete JSON report ${jsonPath}:`,
              error instanceof Error ? error.message : String(error)
            );
          }
          if (fs.existsSync(mdPath)) {
            try {
              fs.unlinkSync(mdPath);
            } catch (error) {
              console.warn(
                `Failed to delete markdown report ${mdPath}:`,
                error instanceof Error ? error.message : String(error)
              );
            }
          }
        }
        if (deletedCount > 0) {
          console.log(
            `🧹 Pruned ${deletedCount} old reports (keeping last ${maxReports})`
          );
        }
      }
    } catch (error) {
      console.error(
        `Failed to prune old reports:`,
        error instanceof Error ? error.message : String(error)
      );
    }
  }

  printsToStdio(): boolean {
    return false;
  }
}
