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

interface TestReport {
  spec_file: string;
  test_name: string;
  status: "passed" | "failed" | "skipped" | "flaky";
  duration_ms: number;
  attempts: AttemptReport[];
  selectors_used: string[];
  failure?: FailureReport;
}

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
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  flaky: number;
  tests: TestReport[];
  selector_coverage: SelectorCoverage;
}

interface SelectorCoverage {
  documented: Record<
    string,
    {
      id: string;
      component: string;
      coverage: "exercised" | "not_exercised";
    }
  >;
  coverage_percentage: number;
  gaps: string[];
  undocumented: string[];
}

export default class StructuredReporter implements Reporter {
  private reportDir: string;
  private startTime: number = 0;
  private tests: TestReport[] = [];
  private selectorRegistry: Record<string, any> = {};
  private usedSelectors: Set<string> = new Set();
  private testStats = {
    total: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    flaky: 0,
  };

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
      const content = fs.readFileSync(registryPath, "utf-8");
      const parsed = yaml.load(content) as Record<string, any>;
      this.selectorRegistry = parsed || {};
    }
  }

  onBegin(): void {
    this.startTime = Date.now();
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const specFile = test.location.file;
    const testStatus = this.computeTestStatus(test);

    // Update stats
    this.testStats.total++;
    if (testStatus === "passed") this.testStats.passed++;
    if (testStatus === "failed") this.testStats.failed++;
    if (testStatus === "skipped") this.testStats.skipped++;
    if (testStatus === "flaky") this.testStats.flaky++;

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

    const testReport: TestReport = {
      spec_file: specFile,
      test_name: test.title,
      status: testStatus,
      duration_ms: totalDuration,
      attempts: this.extractAttempts(test),
      selectors_used: this.extractSelectorsFromTest(test, result),
      failure: failureInfo,
    };

    this.tests.push(testReport);
    testReport.selectors_used.forEach((s) => this.usedSelectors.add(s));
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
      ...this.testStats,
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
      } catch {
        // If we can't read the file, skip source extraction
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
    const documented: Record<string, any> = {};
    const gaps: string[] = [];
    const undocumented: string[] = [];

    // Flatten the registry structure
    const flatRegistry = this.flattenRegistry(this.selectorRegistry);

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
      if (!flatRegistry[selector] && !this.isPatternSelector(selector)) {
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
    registry: Record<string, any>,
    result: Record<string, any> = {}
  ): Record<string, any> {
    for (const [_key, value] of Object.entries(registry)) {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        if ("id" in value) {
          result[value.id] = value;
        } else {
          this.flattenRegistry(value, result);
        }
      }
    }
    return result;
  }

  private isPatternSelector(selector: string): boolean {
    // Check if selector matches a pattern like {entity-type}-table
    return /\{[^}]+\}/.test(selector);
  }

  private writeJsonReport(report: RunReport, runId: string): void {
    const filePath = path.join(this.reportDir, `${runId}.json`);
    fs.writeFileSync(filePath, JSON.stringify(report, null, 2));
    console.log(`\n📊 Structured report written to ${filePath}`);
  }

  private writeMarkdownReport(report: RunReport, runId: string): void {
    const filePath = path.join(this.reportDir, `${runId}.md`);

    let markdown = `# Test Run Report\n\n`;
    markdown += `**Run ID:** ${report.run_id}\n`;
    markdown += `**Started:** ${report.started_at}\n`;
    markdown += `**Ended:** ${report.ended_at}\n`;
    markdown += `**Duration:** ${(report.duration_ms / 1000).toFixed(2)}s\n\n`;

    // Summary stats
    markdown += `## Summary\n\n`;
    markdown += `| Metric | Count | Percentage |\n`;
    markdown += `|--------|-------|------------|\n`;
    markdown += `| Total | ${report.total} | 100% |\n`;
    markdown += `| Passed | ${report.passed} | ${report.total > 0 ? Math.round((report.passed / report.total) * 100) : 0}% |\n`;
    markdown += `| Failed | ${report.failed} | ${report.total > 0 ? Math.round((report.failed / report.total) * 100) : 0}% |\n`;
    markdown += `| Flaky | ${report.flaky} | ${report.total > 0 ? Math.round((report.flaky / report.total) * 100) : 0}% |\n`;
    markdown += `| Skipped | ${report.skipped} | ${report.total > 0 ? Math.round((report.skipped / report.total) * 100) : 0}% |\n\n`;

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
    const files = fs
      .readdirSync(this.reportDir)
      .filter((f) => f.endsWith(".json"))
      .sort()
      .reverse();

    if (files.length > maxReports) {
      const filesToDelete = files.slice(maxReports);
      for (const file of filesToDelete) {
        const jsonPath = path.join(this.reportDir, file);
        const mdPath = path.join(this.reportDir, file.replace(".json", ".md"));
        fs.unlinkSync(jsonPath);
        if (fs.existsSync(mdPath)) {
          fs.unlinkSync(mdPath);
        }
      }
      console.log(
        `🧹 Pruned ${filesToDelete.length} old reports (keeping last ${maxReports})`
      );
    }
  }

  printsToStdio(): boolean {
    return false;
  }
}
