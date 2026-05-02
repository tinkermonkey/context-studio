import {
  Reporter,
  FullResult,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";
import * as fs from "fs";
import * as path from "path";
import { execSync } from "child_process";
import {
  flattenRegistry,
  extractPatternTemplates,
  matchesPattern as matchesPatternTemplate,
  loadSelectorRegistry as loadSharedSelectorRegistry,
} from "../../lib/selector-registry";
import type { SelectorRegistry as SharedSelectorRegistry } from "../../lib/selector-registry";

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

type AttemptReport =
  | {
      status: "passed" | "skipped";
      duration_ms: number;
      failure?: never;
    }
  | {
      status: "failed" | "timedOut" | "interrupted";
      duration_ms: number;
      failure: FailureReport;
    };

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
  is_valid: boolean;
  registry_error?: string;
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
  registry_error?: string;
}

type SelectorRegistry = SharedSelectorRegistry;

export default class StructuredReporter implements Reporter {
  private reportDir: string;
  private startTime: number = 0;
  private tests: TestReport[] = [];
  private selectorRegistry: SelectorRegistry = {};
  private usedSelectors: Set<string> = new Set();
  private registryParseError: Error | null = null;
  private fileSourceCache: Map<string, string> = new Map();

  constructor() {
    this.reportDir = path.join(__dirname, "..", "reports");
    if (!fs.existsSync(this.reportDir)) {
      fs.mkdirSync(this.reportDir, { recursive: true });
    }
    this.loadSelectorRegistry();
  }

  private loadSelectorRegistry(): void {
    const registryPath = path.join(__dirname, "..", "..", "selector-registry.yaml");
    if (!fs.existsSync(registryPath)) {
      console.warn(
        `Selector registry not found at ${registryPath} — selector coverage will be empty. ` +
        `Create selector-registry.yaml to enable coverage tracking.`
      );
      this.selectorRegistry = {};
      return;
    }

    try {
      this.selectorRegistry = loadSharedSelectorRegistry(registryPath);

      if (Object.keys(this.selectorRegistry).length === 0) {
        console.warn(
          `Selector registry at ${registryPath} is empty. ` +
          `Coverage report will show 0% with all selectors as undocumented.`
        );
      }
    } catch (error) {
      this.registryParseError = error instanceof Error ? error : new Error(String(error));
      console.error(
        `Failed to parse selector registry YAML at ${registryPath}: ` +
        `${this.registryParseError.message}. ` +
        `Coverage report will be unavailable.`
      );
      this.selectorRegistry = {};
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
      is_valid: !this.registryParseError,
      ...(this.registryParseError && { registry_error: this.registryParseError.message }),
      tests: this.tests,
      selector_coverage: selectorCoverage,
    };

    const jsonWriteSuccess = this.writeJsonReport(report, runId);
    const markdownWriteSuccess = this.writeMarkdownReport(report, runId);

    if (!jsonWriteSuccess) {
      const error = new Error(
        `Failed to write JSON report for run ${runId}. ` +
        `This is a critical failure as the JSON report is the core agentic deliverable.`
      );
      throw error;
    }

    if (!markdownWriteSuccess) {
      console.error(
        `⚠️ Failed to write Markdown report for run ${runId}. ` +
        `JSON report was written successfully, but human-readable summary is unavailable.`
      );
    }

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
    return test.results.map((result) => {
      if (result.status === "failed" || result.status === "timedOut" || result.status === "interrupted") {
        return {
          status: result.status,
          duration_ms: result.duration,
          failure: this.extractFailureInfo(result),
        };
      }
      return {
        status: result.status as "passed" | "skipped",
        duration_ms: result.duration,
      };
    });
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
        // Use cached source if available to avoid re-reading the same file
        let source = this.fileSourceCache.get(testFile);
        if (!source) {
          source = fs.readFileSync(testFile, "utf-8");
          this.fileSourceCache.set(testFile, source);
        }
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

    // Flatten the registry structure and extract pattern templates
    const flatRegistry = flattenRegistry(this.selectorRegistry);
    const patternRegistry = extractPatternTemplates(this.selectorRegistry);

    // Check coverage for each documented selector
    for (const [_key, entry] of flatRegistry) {
      const id = entry.id;
      let isCovered = false;

      // Check if literal selector was used
      if (this.usedSelectors.has(id)) {
        isCovered = true;
      }
      // Check if it's a pattern template and any selector matches it
      else if (patternRegistry.includes(id)) {
        for (const selector of this.usedSelectors) {
          if (matchesPatternTemplate(selector, [id])) {
            isCovered = true;
            break;
          }
        }
      }

      documented[id] = {
        id,
        component: entry.component || "Unknown",
        coverage: isCovered ? "exercised" : "not_exercised",
      };

      if (!isCovered) {
        gaps.push(id);
      }
    }

    // Find undocumented selectors
    Array.from(this.usedSelectors).forEach((selector) => {
      if (
        !flatRegistry.has(selector) &&
        !matchesPatternTemplate(selector, patternRegistry)
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

    const coverage: SelectorCoverage = {
      documented,
      coverage_percentage: coveragePercentage,
      gaps,
      undocumented,
    };

    // Include parse error if one occurred, so agents can distinguish from legitimate 0% coverage
    if (this.registryParseError) {
      coverage.registry_error = this.registryParseError.message;
    }

    return coverage;
  }


  private writeJsonReport(report: RunReport, runId: string): boolean {
    const filePath = path.join(this.reportDir, `${runId}.json`);
    try {
      fs.writeFileSync(filePath, JSON.stringify(report, null, 2));
      console.log(`\n📊 Structured report written to ${filePath}`);
      return true;
    } catch (error) {
      console.error(
        `Failed to write JSON report to ${filePath}:`,
        error instanceof Error ? error.message : String(error)
      );
      return false;
    }
  }

  private writeMarkdownReport(report: RunReport, runId: string): boolean {
    const filePath = path.join(this.reportDir, `${runId}.md`);

    try {
      const stats = computeRunStats(report.tests);

      let markdown = `# Test Run Report\n\n`;

      if (report.registry_error) {
        markdown += `> **⚠️ INVALID REPORT — Selector registry failed to parse**\n`;
        markdown += `> \`selector_coverage\` shows 0% but this is NOT legitimate coverage data.\n`;
        markdown += `> Fix the registry before trusting any coverage numbers.\n`;
        markdown += `> Error: ${report.registry_error}\n\n`;
      }

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
      return true;
    } catch (error) {
      console.error(
        `Failed to write markdown report to ${filePath}:`,
        error instanceof Error ? error.message : String(error)
      );
      return false;
    }
  }

  private getGitSha(): string {
    try {
      const sha = execSync("git rev-parse --short HEAD", { encoding: "utf-8" }).trim();
      return sha;
    } catch (error) {
      console.warn(
        `Failed to retrieve git commit SHA: ` +
        `${error instanceof Error ? error.message : String(error)}. ` +
        `Run ID will use "unknown" as fallback.`
      );
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
