#!/usr/bin/env node

/**
 * Test Contract Validator
 *
 * Validates that:
 * 1. All selectors used in tests exist in the codebase
 * 2. All selectors in the codebase are documented in the registry
 * 3. Registry patterns are properly formatted and usable
 *
 * Exit codes:
 * 0 = validation passed (all checks passed or warnings only)
 * 1 = hard failure (test references non-existent selector)
 */

import fs from "fs";
import path from "path";
import {
  loadSelectorRegistry,
  extractSelectorsFromRegistry,
  matchesPattern,
} from "../lib/selector-registry";

interface ValidationResult {
  errors: string[];
  warnings: string[];
}

const result: ValidationResult = {
  errors: [],
  warnings: [],
};

/**
 * Walks a directory tree and extracts selectors using the provided regex patterns
 */
function extractSelectorsFromDirectory(
  directory: string,
  options: {
    fileExtensions: string[];
    patterns: RegExp[];
    skipDotFiles?: boolean;
  }
): Set<string> {
  const selectors = new Set<string>();
  const { fileExtensions, patterns, skipDotFiles = true } = options;

  function walkDir(dir: string) {
    if (!fs.existsSync(dir)) {
      return;
    }

    const files = fs.readdirSync(dir);

    for (const file of files) {
      const filePath = path.join(dir, file);
      const stat = fs.statSync(filePath);

      // Skip node_modules, dist, build, and optionally dot files
      if (
        (skipDotFiles && file.startsWith(".")) ||
        file === "node_modules" ||
        file === "dist" ||
        file === "build"
      ) {
        continue;
      }

      if (stat.isDirectory()) {
        walkDir(filePath);
      } else if (fileExtensions.some((ext) => file.endsWith(ext))) {
        try {
          const content = fs.readFileSync(filePath, "utf-8");

          for (const pattern of patterns) {
            pattern.lastIndex = 0;
            let match;
            while ((match = pattern.exec(content)) !== null) {
              const selector = match[1];
              // Skip template literals with variables
              if (!selector.includes("${")) {
                selectors.add(selector);
              }
            }
          }
        } catch (err) {
          const fileType =
            fileExtensions[0] === ".spec.ts" ? "test" : "source";
          console.warn(
            `⚠️  Warning: Could not read ${fileType} file ${filePath}: ${err instanceof Error ? err.message : String(err)}`
          );
        }
      }
    }
  }

  walkDir(directory);
  return selectors;
}

// Extract all data-testid values from source code
function extractSelectorsFromCode(directory: string): Set<string> {
  return extractSelectorsFromDirectory(directory, {
    fileExtensions: [".tsx", ".ts", ".jsx", ".js"],
    patterns: [
      /data-testid=["']([^"']+)["']/g,
      /data-testid=\{\s*`([^`]+)`\s*\}/g,
      /dataTestId\s*=\s*["']([^"']+)["']/g,
    ],
  });
}

// Extract all data-testid references from E2E tests only
function extractSelectorsFromE2ETests(testDirectory: string): Set<string> {
  return extractSelectorsFromDirectory(testDirectory, {
    fileExtensions: [".spec.ts", ".spec.tsx"],
    patterns: [
      /data-testid=["']([^"']+)["']/g,
      /getByTestId\(["']([^"']+)["']\)/g,
      /getByTestId\(`([^`]+)`\)/g,
      /\[data-testid=["']([^"']+)["']\]/g,
      /locator\(\['data-testid=([^']+)'\]\)/g,
      /locator\(['"][^'"].*data-testid=['"]([^'"]+)['"]/g,
    ],
  });
}

// Load registry and extract all documented selectors
function loadRegistry(): {
  documented: Set<string>;
  patterns: string[];
  knownFuture: Set<string>;
} {
  const registryPath = path.join(process.cwd(), "selector-registry.yaml");

  try {
    const registry = loadSelectorRegistry(registryPath);
    const { documented, patterns, knownFuture } =
      extractSelectorsFromRegistry(registry);
    return { documented, patterns, knownFuture };
  } catch (err) {
    console.error(
      `❌ ${err instanceof Error ? err.message : "Error loading registry"}`
    );
    process.exit(1);
  }
}

// Main validation
function validate() {
  console.log("🔍 Validating test contract...\n");

  const srcDir = path.join(process.cwd(), "src");
  const e2eDir = path.join(process.cwd(), "e2e", "tests");

  // Check that required directories exist
  if (!fs.existsSync(srcDir)) {
    console.error(
      `❌ FATAL: Required directory not found: ${srcDir}\n` +
      `This script must be run from the /ux directory.`
    );
    process.exit(1);
  }

  if (!fs.existsSync(e2eDir)) {
    console.error(
      `❌ FATAL: Required directory not found: ${e2eDir}\n` +
      `This script must be run from the /ux directory.`
    );
    process.exit(1);
  }

  // Extract selectors from code and E2E tests only (not unit tests)
  const codeSelectors = extractSelectorsFromCode(srcDir);
  const testSelectors = extractSelectorsFromE2ETests(e2eDir);

  // Load registry
  const { documented, patterns, knownFuture } = loadRegistry();

  console.log(`📊 Found ${codeSelectors.size} selectors in source code`);
  console.log(`📊 Found ${testSelectors.size} selectors in tests`);
  console.log(`📊 Found ${documented.size} documented selectors`);
  console.log(`📊 Found ${knownFuture.size} known future selectors\n`);

  // Check 1: Test selectors must exist in code or match a pattern or be known future
  console.log("✅ Checking test selectors against code...");
  const futureSelectors = new Set<string>();
  for (const testSelector of testSelectors) {
    if (knownFuture.has(testSelector)) {
      // Known future selectors are tracked but not errors
      futureSelectors.add(testSelector);
    } else if (
      !codeSelectors.has(testSelector) &&
      !matchesPattern(testSelector, patterns)
    ) {
      result.errors.push(
        `❌ Test references non-existent selector: "${testSelector}"`
      );
    }
  }

  if (result.errors.length === 0) {
    console.log(
      "✓ All test selectors exist in code or match documented patterns\n"
    );
  } else {
    console.log(`✗ Found ${result.errors.length} invalid test selectors\n`);
  }

  if (futureSelectors.size > 0) {
    console.log(
      `ℹ️  Found ${futureSelectors.size} known future selectors (not implemented yet):`
    );
    futureSelectors.forEach((sel) =>
      console.log(`  ℹ️  ${sel} (planned for future implementation)`)
    );
    console.log();
  }

  // Check 2: Code selectors should be in registry (warnings only)
  console.log("✅ Checking code selectors against registry...");
  for (const codeSelector of codeSelectors) {
    if (
      !documented.has(codeSelector) &&
      !matchesPattern(codeSelector, patterns) &&
      !knownFuture.has(codeSelector)
    ) {
      result.warnings.push(
        `⚠️  Code selector not in registry: "${codeSelector}"`
      );
    }
  }

  if (result.warnings.length === 0) {
    console.log("✓ All code selectors are documented in registry\n");
  } else {
    console.log(
      `⚠️  Found ${result.warnings.length} undocumented code selectors (warnings)\n`
    );
  }

  // Check 3: Spec classification — detect API-only tests mislabeled as UI tests.
  //
  // A spec file is "API-only" if it contains apiRequest() calls but zero UI interaction
  // patterns (page.goto, getByTestId, page.click, page.fill, page.locator, page.type).
  //
  // Files in e2e/tests/api-contracts/ are exempt (they are intentionally API-only).
  // Files outside that directory must have at least one UI interaction, or they will be
  // flagged — because they will pass even if the frontend serves a blank error page.
  console.log("✅ Checking test classification (API-only vs UI)...");
  checkSpecClassification(e2eDir, result);

  // Print results
  if (result.errors.length > 0) {
    console.log("❌ HARD FAILURES:");
    result.errors.forEach((err) => console.log(`  ${err}`));
    console.log();
  }

  if (result.warnings.length > 0) {
    console.log("⚠️  WARNINGS:");
    result.warnings.slice(0, 10).forEach((warn) => console.log(`  ${warn}`));
    if (result.warnings.length > 10) {
      console.log(`  ... and ${result.warnings.length - 10} more`);
    }
    console.log();
  }

  // Summary
  if (result.errors.length > 0) {
    console.log("❌ Validation FAILED");
    process.exit(1);
  } else if (result.warnings.length > 0) {
    console.log("⚠️  Validation completed with warnings");
    process.exit(0);
  } else {
    console.log("✅ Validation PASSED: All selectors valid");
    process.exit(0);
  }
}

// UI interaction patterns that prove a test actually drives the browser.
const UI_INTERACTION_PATTERNS = [
  /page\.goto\s*\(/,
  /page\.getByTestId\s*\(/,
  /getByTestId\s*\(/,
  /page\.click\s*\(/,
  /page\.fill\s*\(/,
  /page\.type\s*\(/,
  /page\.locator\s*\(/,
  /page\.getByRole\s*\(/,
  /page\.getByText\s*\(/,
  /page\.getByLabel\s*\(/,
  /await\s+expect\s*\(\s*page\./,
];

const API_ONLY_PATTERN = /\bapiRequest\s*[(<]/;

function checkSpecClassification(
  testDir: string,
  result: ValidationResult
): void {
  const apiContractsDir = path.join(testDir, "api-contracts");

  function walkSpecs(dir: string): void {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir)) {
      const fullPath = path.join(dir, entry);
      const stat = fs.statSync(fullPath);
      if (stat.isDirectory()) {
        walkSpecs(fullPath);
      } else if (entry.endsWith(".spec.ts") || entry.endsWith(".spec.tsx")) {
        classifySpec(fullPath, apiContractsDir, result);
      }
    }
  }

  walkSpecs(testDir);
}

function stripComments(source: string): string {
  // Remove single-line (//) and block (/* */) comments to prevent commented-out
  // code from triggering false positives in the pattern checks below.
  //
  // Limitation: this regex-based stripper does not respect string or template
  // literals, so URLs containing `//` (e.g. "http://...") and block-comment-like
  // sequences inside strings will also be stripped. This is acceptable for the
  // heuristic classification check — the patterns we're matching (apiRequest,
  // page.goto, getByTestId) are unlikely to appear solely inside string literals
  // — but it means the classifier is not a strict parser.
  return source
    .replace(/\/\/[^\n]*/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");
}

function classifySpec(
  filePath: string,
  apiContractsDir: string,
  result: ValidationResult
): void {
  const isInApiContracts = filePath.startsWith(apiContractsDir + path.sep) ||
    path.dirname(filePath) === apiContractsDir;

  let rawContent: string;
  try {
    rawContent = fs.readFileSync(filePath, "utf-8");
  } catch {
    return;
  }

  const content = stripComments(rawContent);
  const hasApiRequest = API_ONLY_PATTERN.test(content);
  const hasUiInteraction = UI_INTERACTION_PATTERNS.some((p) => p.test(content));
  const relPath = path.relative(process.cwd(), filePath);

  if (isInApiContracts) {
    // api-contracts/ specs should NOT have UI interactions — that's what ui-flows/ is for.
    if (hasUiInteraction) {
      result.warnings.push(
        `⚠️  api-contracts spec has UI interactions (move to ui-flows/): ${relPath}`
      );
    }
  } else {
    // All other spec directories are assumed to be UI test directories.
    // A spec with apiRequest() but no UI interactions will pass against a blank frontend.
    if (hasApiRequest && !hasUiInteraction) {
      result.errors.push(
        `❌ Spec has no UI interactions — will pass against a blank frontend. ` +
        `Move to api-contracts/ or add browser-level assertions: ${relPath}`
      );
    }
  }
}

validate();
