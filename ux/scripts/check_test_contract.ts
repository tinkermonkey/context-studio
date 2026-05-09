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

function loadRegistry(): Registry {
  const raw = fs.readFileSync(registryPath, "utf-8");
  return yaml.load(raw) as Registry;
}

function findTestidUsages(dir: string, ext: string[]): Set<string> {
  const usages = new Set<string>();
  if (!fs.existsSync(dir)) return usages;

  function walk(current: string) {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (ext.some((e) => entry.name.endsWith(e))) {
        const content = fs.readFileSync(full, "utf-8");
        const matches = content.matchAll(/data-testid=["']([^"']+)["']/g);
        for (const m of matches) usages.add(m[1]);
        const testMatches = content.matchAll(/getByTestId\(["']([^"']+)["']\)/g);
        for (const m of testMatches) usages.add(m[1]);
      }
    }
  }

  walk(dir);
  return usages;
}

function main() {
  const registry = loadRegistry();
  const registered = new Set(registry.selectors.map((s) => s.selector));

  const srcUsages = findTestidUsages(srcDir, [".tsx", ".ts", ".jsx", ".js"]);
  const e2eUsages = findTestidUsages(e2eDir, [".ts", ".js"]);
  const allUsages = new Set([...srcUsages, ...e2eUsages]);

  const unregistered = [...allUsages].filter((s) => !registered.has(s));

  if (unregistered.length > 0) {
    console.error("❌ Selector contract violation — unregistered data-testid attributes:");
    unregistered.forEach((s) => console.error(`  - ${s}`));
    process.exit(1);
  }

  console.log(
    `✅ Selector contract valid (${registered.size} registered, ${allUsages.size} in use)`,
  );
}

main();
