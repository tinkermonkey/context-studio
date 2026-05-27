import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

interface SelectorEntry {
  selector: string;
  component: string;
  description: string;
}

interface Registry {
  selectors: SelectorEntry[];
}

const registryPath = path.resolve(process.cwd(), "selector-registry.yaml");
const srcDir = path.resolve(process.cwd(), "src");
const e2eDir = path.resolve(process.cwd(), "e2e");

const WRITE = process.argv.includes("--write");
const SHOW_ORPHANS = process.argv.includes("--orphans");

function loadRegistry(): Registry {
  const raw = fs.readFileSync(registryPath, "utf-8");
  return yaml.load(raw) as Registry;
}

interface Usage {
  testid: string;
  file: string;
}

/** All testids referenced in code: data-testid="…" attributes and getByTestId("…") calls. */
function findTestidUsages(dir: string, ext: string[]): Usage[] {
  const usages: Usage[] = [];
  if (!fs.existsSync(dir)) return usages;

  function walk(current: string) {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (ext.some((e) => entry.name.endsWith(e))) {
        const content = fs.readFileSync(full, "utf-8");
        const rel = path.relative(process.cwd(), full);
        for (const m of content.matchAll(/data-testid=["']([^"']+)["']/g)) {
          usages.push({ testid: m[1], file: rel });
        }
        for (const m of content.matchAll(/getByTestId\(["']([^"']+)["']\)/g)) {
          usages.push({ testid: m[1], file: rel });
        }
      }
    }
  }

  walk(dir);
  return usages;
}

/**
 * Static testid definitions and dynamic prefixes derived from component source.
 * - statics: exact `data-testid="foo"` → defining file
 * - prefixes: the literal head of a template, `data-testid={`foo-${id}`}` → "foo-" → file
 * Used by --write to register the right entry (exact selector vs `prefix-*` wildcard).
 */
function findTestidDefinitions(dir: string, ext: string[]) {
  const statics = new Map<string, string>();
  const prefixes = new Map<string, string>();
  if (!fs.existsSync(dir)) return { statics, prefixes };

  function walk(current: string) {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (ext.some((e) => entry.name.endsWith(e)) && !/\.(test|spec)\.|__tests__/.test(full)) {
        const content = fs.readFileSync(full, "utf-8");
        const rel = path.relative(process.cwd(), full);
        for (const m of content.matchAll(/data-testid=["']([^"']+)["']/g)) {
          if (!statics.has(m[1])) statics.set(m[1], rel);
        }
        // template literal: data-testid={`prefix-${...}`}
        for (const m of content.matchAll(/data-testid=\{`([^`$]*)\$\{/g)) {
          if (m[1] && !prefixes.has(m[1])) prefixes.set(m[1], rel);
        }
      }
    }
  }

  walk(dir);
  return { statics, prefixes };
}

function matches(testid: string, pattern: string): boolean {
  if (pattern.endsWith("*")) return testid.startsWith(pattern.slice(0, -1));
  return testid === pattern;
}

function isRegistered(testid: string, registered: Set<string>): boolean {
  for (const pattern of registered) if (matches(testid, pattern)) return true;
  return false;
}

/** Resolve an unregistered testid to the registry entry that should cover it. */
function resolveEntry(
  testid: string,
  usageFile: string,
  defs: ReturnType<typeof findTestidDefinitions>,
): SelectorEntry {
  if (defs.statics.has(testid)) {
    return { selector: testid, component: defs.statics.get(testid)!, description: "TODO: describe" };
  }
  // longest matching template prefix wins (most specific)
  let best: string | null = null;
  for (const prefix of defs.prefixes.keys()) {
    if (testid.startsWith(prefix) && (best === null || prefix.length > best.length)) best = prefix;
  }
  if (best) {
    return { selector: `${best}*`, component: defs.prefixes.get(best)!, description: "TODO: describe" };
  }
  // no source definition (e.g. produced by a third-party component, queried in a test)
  return { selector: testid, component: usageFile, description: "TODO: describe (no source definition found)" };
}

function serializeEntry(e: SelectorEntry): string {
  return `  - selector: ${e.selector}\n    component: ${e.component}\n    description: ${e.description}\n`;
}

function main() {
  const registry = loadRegistry();
  const registered = new Set(registry.selectors.map((s) => s.selector));

  const usages = [...findTestidUsages(srcDir, [".tsx", ".ts", ".jsx", ".js"]), ...findTestidUsages(e2eDir, [".ts", ".js"])];
  const usedSet = new Set(usages.map((u) => u.testid));

  const unregistered = usages.filter((u) => !isRegistered(u.testid, registered));
  const uniqueUnregistered = [...new Map(unregistered.map((u) => [u.testid, u])).values()];

  // Orphans: registered patterns that nothing in code uses (candidates for pruning).
  const orphans = registry.selectors.filter((s) => ![...usedSet].some((t) => matches(t, s.selector)));

  if (WRITE && uniqueUnregistered.length > 0) {
    const defs = findTestidDefinitions(srcDir, [".tsx", ".ts", ".jsx", ".js"]);
    const newEntries = new Map<string, SelectorEntry>();
    for (const u of uniqueUnregistered) {
      const entry = resolveEntry(u.testid, u.file, defs);
      newEntries.set(entry.selector, entry); // dedupe (many ids collapse to one wildcard)
    }
    const block =
      `\n  # ── Auto-added by \`validate-selectors --write\` — review the TODO descriptions ──\n` +
      [...newEntries.values()].map(serializeEntry).join("");
    fs.appendFileSync(registryPath, block);
    console.log(`✍️  Added ${newEntries.size} registry entr${newEntries.size === 1 ? "y" : "ies"} for ${uniqueUnregistered.length} unregistered testid(s). Review and edit descriptions in selector-registry.yaml.`);
    return;
  }

  if (SHOW_ORPHANS && orphans.length > 0) {
    console.warn(`⚠️  ${orphans.length} registered selector(s) are not used anywhere (candidates for pruning):`);
    orphans.forEach((o) => console.warn(`  - ${o.selector}  (${o.component})`));
    console.warn("");
  }

  if (uniqueUnregistered.length > 0) {
    console.error("❌ Selector contract violation — unregistered data-testid attributes:");
    uniqueUnregistered.forEach((u) => console.error(`  - ${u.testid}  (${u.file})`));
    console.error('\nRun `npm run validate-selectors -- --write` to auto-add stubs, then fill in descriptions.');
    process.exit(1);
  }

  console.log(`✅ Selector contract valid (${registered.size} registered, ${usedSet.size} in use)`);
}

main();
