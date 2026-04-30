import fs from "fs";
import path from "path";
import yaml from "js-yaml";

export interface RegistryEntry {
  id: string;
  component?: string;
  status?: "not_yet_implemented" | "future";
  pattern?: boolean;
  [key: string]: unknown;
}

export interface SelectorRegistry {
  [key: string]: RegistryEntry | SelectorRegistry;
}

/**
 * Loads and parses the selector registry YAML file
 */
export function loadSelectorRegistry(registryPath: string): SelectorRegistry {
  if (!fs.existsSync(registryPath)) {
    throw new Error(`selector-registry.yaml not found at ${registryPath}`);
  }

  try {
    const content = fs.readFileSync(registryPath, "utf-8");
    const registry = yaml.load(content);

    if (!registry || typeof registry !== "object" || Array.isArray(registry)) {
      throw new Error("selector-registry.yaml: root must be an object");
    }

    // Validate registry structure
    validateRegistryStructure(registry as SelectorRegistry);

    return registry as SelectorRegistry;
  } catch (err) {
    if (err instanceof Error) {
      throw new Error(`Error parsing selector-registry.yaml: ${err.message}`);
    }
    throw err;
  }
}

/**
 * Validates that the registry has proper structure
 */
function validateRegistryStructure(registry: SelectorRegistry): void {
  for (const [sectionKey, section] of Object.entries(registry)) {
    if (!section || typeof section !== "object" || Array.isArray(section)) {
      throw new Error(
        `selector-registry.yaml: section "${sectionKey}" must be an object`
      );
    }

    const sectionTyped = section as Record<string, unknown>;

    // Check if this is a leaf section (contains entries with 'id') or a nested section
    const isLeafSection = Object.values(sectionTyped).some((entry) => {
      return (
        entry &&
        typeof entry === "object" &&
        !Array.isArray(entry) &&
        "id" in entry
      );
    });

    if (isLeafSection) {
      // This is a leaf section with entries
      for (const [entryKey, entry] of Object.entries(sectionTyped)) {
        if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
          throw new Error(
            `selector-registry.yaml: entry "${sectionKey}.${entryKey}" must be an object`
          );
        }

        const entryTyped = entry as Record<string, unknown>;
        if (typeof entryTyped.id !== "string") {
          throw new Error(
            `selector-registry.yaml: entry "${sectionKey}.${entryKey}" must have an id field (string)`
          );
        }
      }
    } else {
      // This might be a nested section, recursively validate
      validateRegistryStructure(sectionTyped as SelectorRegistry);
    }
  }
}

/**
 * Recursively flattens a nested registry structure into a map of id -> entry
 */
export function flattenRegistry(
  registry: SelectorRegistry,
  result: Map<string, RegistryEntry> = new Map()
): Map<string, RegistryEntry> {
  for (const value of Object.values(registry)) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const typedValue = value as Record<string, unknown>;
      if ("id" in typedValue && typeof typedValue.id === "string") {
        result.set(typedValue.id, typedValue as RegistryEntry);
      } else {
        flattenRegistry(typedValue as SelectorRegistry, result);
      }
    }
  }
  return result;
}

/**
 * Extracts all pattern templates (entries with {placeholders}) from the registry
 */
export function extractPatternTemplates(
  registry: SelectorRegistry,
  result: string[] = []
): string[] {
  for (const value of Object.values(registry)) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      continue;
    }

    const typedValue = value as Record<string, unknown>;
    if (
      "id" in typedValue &&
      typeof typedValue.id === "string" &&
      typedValue.id.includes("{") &&
      typedValue.id.includes("}")
    ) {
      result.push(typedValue.id);
    } else {
      extractPatternTemplates(typedValue as SelectorRegistry, result);
    }
  }
  return result;
}

/**
 * Checks if a selector matches any pattern in the patterns list
 * Patterns use {placeholder} syntax which matches [a-zA-Z0-9_-]+
 */
export function matchesPattern(selector: string, patterns: string[]): boolean {
  for (const pattern of patterns) {
    const parts = pattern.split(/(\{[^}]+\})/);
    const regexPattern = parts
      .map((part) => {
        if (part.startsWith("{") && part.endsWith("}")) {
          return "[a-zA-Z0-9_-]+";
        }
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

/**
 * Extracts documented, pattern, and future selectors from a registry
 */
export function extractSelectorsFromRegistry(registry: SelectorRegistry): {
  documented: Set<string>;
  patterns: string[];
  knownFuture: Set<string>;
} {
  const documented = new Set<string>();
  const patterns: string[] = [];
  const knownFuture = new Set<string>();

  const flatRegistry = flattenRegistry(registry);
  for (const entry of flatRegistry.values()) {
    if (entry.status === "not_yet_implemented" || entry.status === "future") {
      knownFuture.add(entry.id);
    } else if (entry.pattern) {
      patterns.push(entry.id);
    } else {
      documented.add(entry.id);
    }
  }

  return { documented, patterns, knownFuture };
}
