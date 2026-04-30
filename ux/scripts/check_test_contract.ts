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
import yaml from "js-yaml";

interface ValidationResult {
  hasErrors: boolean;
  hasWarnings: boolean;
  errors: string[];
  warnings: string[];
}

const result: ValidationResult = {
  hasErrors: false,
  hasWarnings: false,
  errors: [],
  warnings: [],
};

// Extract all data-testid values from source code
function extractSelectorsFromCode(directory: string): Set<string> {
  const selectors = new Set<string>();
  // Match both literal attributes and JSX expressions
  const dataTestIdRegex = /data-testid=["']([^"']+)["']/g;
  const jsxExpressionRegex = /data-testid=\{\s*`([^`]+)`\s*\}/g;
  const propRegex = /dataTestId\s*=\s*["']([^"']+)["']/g;

  function resetRegexes() {
    dataTestIdRegex.lastIndex = 0;
    jsxExpressionRegex.lastIndex = 0;
    propRegex.lastIndex = 0;
  }

  function walkDir(dir: string) {
    const files = fs.readdirSync(dir);

    for (const file of files) {
      const filePath = path.join(dir, file);
      const stat = fs.statSync(filePath);

      // Skip node_modules, .git, dist, etc.
      if (
        file.startsWith(".") ||
        file === "node_modules" ||
        file === "dist" ||
        file === "build"
      ) {
        continue;
      }

      if (stat.isDirectory()) {
        walkDir(filePath);
      } else if (
        file.endsWith(".tsx") ||
        file.endsWith(".ts") ||
        file.endsWith(".jsx") ||
        file.endsWith(".js")
      ) {
        try {
          const content = fs.readFileSync(filePath, "utf-8");

          // Reset regex lastIndex before processing each file
          resetRegexes();

          // Extract literal data-testid attributes
          let match;
          while ((match = dataTestIdRegex.exec(content)) !== null) {
            selectors.add(match[1]);
          }

          // Extract JSX expression templates (skip templates with variables for now)
          while ((match = jsxExpressionRegex.exec(content)) !== null) {
            if (!match[1].includes("${")) {
              selectors.add(match[1]);
            }
          }

          // Extract prop-based dataTestId usage
          while ((match = propRegex.exec(content)) !== null) {
            selectors.add(match[1]);
          }
        } catch (err) {
          console.warn(`⚠️  Warning: Could not read file ${filePath}: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    }
  }

  walkDir(directory);
  return selectors;
}

// Extract all data-testid references from E2E tests only
function extractSelectorsFromE2ETests(testDirectory: string): Set<string> {
  const selectors = new Set<string>();

  // Patterns to match selector references in tests
  const patterns = [
    /data-testid=["']([^"']+)["']/g,
    /getByTestId\(["']([^"']+)["']\)/g,
    /getByTestId\(`([^`]+)`\)/g,
    /\[data-testid=["']([^"']+)["']\]/g,
    /locator\(\['data-testid=([^']+)'\]\)/g,
    /locator\(['"][^'"].*data-testid=['"]([^'"]+)['"]/g,
  ];

  function resetPatterns() {
    for (const pattern of patterns) {
      pattern.lastIndex = 0;
    }
  }

  function walkDir(dir: string) {
    if (!fs.existsSync(dir)) {
      return;
    }

    const files = fs.readdirSync(dir);

    for (const file of files) {
      const filePath = path.join(dir, file);
      const stat = fs.statSync(filePath);

      if (stat.isDirectory()) {
        walkDir(filePath);
      } else if (
        file.endsWith(".spec.ts") ||
        file.endsWith(".spec.tsx")
      ) {
        try {
          const content = fs.readFileSync(filePath, "utf-8");

          // Reset regex lastIndex before processing each file
          resetPatterns();

          for (const pattern of patterns) {
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
          console.warn(`⚠️  Warning: Could not read test file ${filePath}: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    }
  }

  walkDir(testDirectory);
  return selectors;
}

// Load registry and extract all documented selectors
function loadRegistry(): {
  documented: Set<string>;
  patterns: Map<string, string>;
  knownFuture: Set<string>;
} {
  const registryPath = path.join(process.cwd(), "selector-registry.yaml");

  if (!fs.existsSync(registryPath)) {
    console.error("❌ selector-registry.yaml not found");
    process.exit(1);
  }

  try {
    const content = fs.readFileSync(registryPath, "utf-8");
    const registry = yaml.load(content);

    // Type guard: registry must be an object
    if (!registry || typeof registry !== "object" || Array.isArray(registry)) {
      console.error("❌ selector-registry.yaml: root must be an object");
      process.exit(1);
    }

    const documented = new Set<string>();
    const patterns = new Map<string, string>();
    const knownFuture = new Set<string>();

    for (const section of Object.values(registry)) {
      // Type guard: section must be an object (not a scalar or array)
      if (!section || typeof section !== "object" || Array.isArray(section)) {
        console.error("❌ selector-registry.yaml: all sections must be objects");
        process.exit(1);
      }

      for (const entry of Object.values(section)) {
        // Type guard: entry must be an object with an id field
        if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
          console.error("❌ selector-registry.yaml: all entries must be objects");
          process.exit(1);
        }

        const typedEntry = entry as Record<string, unknown>;

        // Type guard: entry must have an id field that is a string
        if (typeof typedEntry.id !== "string") {
          console.error("❌ selector-registry.yaml: all entries must have an id field (string)");
          process.exit(1);
        }

        const id = typedEntry.id;
        const status = typedEntry.status as string | undefined;
        const pattern = typedEntry.pattern as boolean | undefined;

        // Track known future selectors separately
        if (status === "not_yet_implemented" || status === "future") {
          knownFuture.add(id);
        } else if (pattern) {
          // Store pattern with template placeholders
          patterns.set(id.replace(/{[^}]+}/g, "*"), id);
        } else {
          documented.add(id);
        }
      }
    }

    return { documented, patterns, knownFuture };
  } catch (err) {
    if (err instanceof Error) {
      console.error(`❌ Error parsing selector-registry.yaml: ${err.message}`);
    } else {
      console.error("❌ Error parsing selector-registry.yaml");
    }
    process.exit(1);
  }
}

// Check if a selector matches a pattern
function matchesPattern(selector: string, patterns: Map<string, string>): boolean {
  for (const [pattern] of patterns) {
    // Use .+ instead of [^-]+ to match hyphens and UUIDs properly
    const regexPattern = pattern.replace(/\*/g, "[\\w-]+");
    if (new RegExp(`^${regexPattern}$`).test(selector)) {
      return true;
    }
  }
  return false;
}

// Main validation
function validate() {
  console.log("🔍 Validating test contract...\n");

  const srcDir = path.join(process.cwd(), "src");
  const e2eDir = path.join(process.cwd(), "e2e", "tests");

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
      result.hasErrors = true;
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
    console.log(`ℹ️  Found ${futureSelectors.size} known future selectors (not implemented yet):`);
    futureSelectors.forEach((sel) => console.log(`  ℹ️  ${sel} (planned for future implementation)`));
    console.log();
  }

  // Check 2: Code selectors should be in registry (warnings only)
  console.log("✅ Checking code selectors against registry...");
  for (const codeSelector of codeSelectors) {
    if (!documented.has(codeSelector) && !matchesPattern(codeSelector, patterns) && !knownFuture.has(codeSelector)) {
      result.hasWarnings = true;
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

  // Print results
  if (result.errors.length > 0) {
    console.log("❌ HARD FAILURES (tests reference non-existent selectors):");
    result.errors.forEach((err) => console.log(`  ${err}`));
    console.log();
  }

  if (result.warnings.length > 0) {
    console.log("⚠️  WARNINGS (code selectors not in registry):");
    result.warnings.slice(0, 10).forEach((warn) => console.log(`  ${warn}`));
    if (result.warnings.length > 10) {
      console.log(`  ... and ${result.warnings.length - 10} more`);
    }
    console.log();
  }

  // Summary
  if (result.hasErrors) {
    console.log("❌ Validation FAILED: Tests reference non-existent selectors");
    process.exit(1);
  } else if (result.hasWarnings) {
    console.log("⚠️  Validation completed with warnings: Update selector registry");
    process.exit(2);
  } else {
    console.log("✅ Validation PASSED: All selectors valid");
    process.exit(0);
  }
}

validate();
