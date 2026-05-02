#!/usr/bin/env tsx
/**
 * Full-page screenshot capture for UX design review.
 *
 * Visits every implemented route in the running app and saves a full-height
 * screenshot to ux/screenshots/<slug>.png.
 *
 * Usage (servers must already be running on 8000/3100):
 *   npx tsx scripts/capture-screenshots.ts
 *   npx tsx scripts/capture-screenshots.ts --width 1440
 *   npx tsx scripts/capture-screenshots.ts --out ./my-screenshots
 */

import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ── Config ────────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const flag = (name: string, fallback: string) => {
  const i = args.indexOf(name);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
};

const FRONTEND = "http://localhost:3100";
const BACKEND  = "http://localhost:8000";
const OUT_DIR  = path.resolve(__dirname, "..", flag("--out", "screenshots"));
const WIDTH    = parseInt(flag("--width", "1440"), 10);
const HEIGHT   = 900; // initial viewport height; screenshots are full-page

// ── Fetch live entity IDs ─────────────────────────────────────────────────────

async function fetchJson(url: string) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<{ items: { id: string }[] }>;
}

async function getLiveIds() {
  const [taxonomies, schemes, classes] = await Promise.all([
    fetchJson(`${BACKEND}/api/taxonomies?limit=1`),
    fetchJson(`${BACKEND}/api/schemes?limit=1`),
    fetchJson(`${BACKEND}/api/classes?limit=1`),
  ]);
  return {
    taxonomyId: taxonomies.items[0]?.id ?? "",
    schemeId:   schemes.items[0]?.id ?? "",
    classId:    classes.items[0]?.id ?? "",
  };
}

// ── Route manifest ────────────────────────────────────────────────────────────

function buildRoutes(ids: Awaited<ReturnType<typeof getLiveIds>>) {
  const { taxonomyId, schemeId, classId } = ids;

  return [
    // ── Core ontology ─────────────────────────────────────────
    { slug: "home",                      path: "/app" },
    { slug: "taxonomies",                path: "/app/taxonomies" },
    { slug: "taxonomy-detail",           path: `/app/taxonomies/${taxonomyId}`,  skip: !taxonomyId },
    { slug: "concept-schemes",           path: "/app/concept-schemes" },
    { slug: "concept-scheme-detail",     path: `/app/concept-schemes/${schemeId}`, skip: !schemeId },
    { slug: "classes",                   path: "/app/classes" },
    { slug: "class-detail",              path: `/app/classes/${classId}`,        skip: !classId },
    { slug: "individuals",               path: "/app/individuals" },
    { slug: "relationships",             path: "/app/relationships" },
    { slug: "properties",                path: "/app/properties" },

    // ── Reference ─────────────────────────────────────────────
    { slug: "reference",                 path: "/app/reference" },
    { slug: "reference-search",          path: "/app/reference/search" },
    { slug: "reference-properties",      path: "/app/reference/properties" },
    { slug: "reference-rag-test",        path: "/app/reference/rag-test" },

    // ── RAG ───────────────────────────────────────────────────
    { slug: "rag-experiments",           path: "/app/rag/experiments" },
    { slug: "rag-pipeline-comparison",   path: "/app/rag/pipeline-comparison" },
    { slug: "rag-test-runner",           path: "/app/rag/test-runner" },

    // ── Config ────────────────────────────────────────────────
    { slug: "config",                    path: "/app/config" },
    { slug: "config-pipelines",          path: "/app/config/pipelines" },
    { slug: "config-data-sources",       path: "/app/config/data-sources" },
    { slug: "config-models",             path: "/app/config/models" },
    { slug: "config-processing",         path: "/app/config/processing" },
    { slug: "config-network",            path: "/app/config/network" },
    { slug: "config-system",             path: "/app/config/system" },
    { slug: "config-advanced",           path: "/app/config/advanced" },

    // ── Monitoring ────────────────────────────────────────────
    { slug: "monitoring-system-health",  path: "/app/monitoring/system-health" },
    { slug: "monitoring-task-manager",   path: "/app/monitoring/task-manager" },
    { slug: "monitoring-analytics",      path: "/app/monitoring/analytics" },
    { slug: "monitoring-performance",    path: "/app/monitoring/performance" },
    { slug: "monitoring-llm-trace",      path: "/app/monitoring/llm-traceability" },

    // ── Data ──────────────────────────────────────────────────
    { slug: "datasets",                  path: "/app/datasets" },
  ] as { slug: string; path: string; skip?: boolean }[];
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  console.log(`\nCapturing screenshots → ${OUT_DIR}`);
  console.log(`Viewport: ${WIDTH}×${HEIGHT} (full-page height)\n`);

  const ids = await getLiveIds();
  const routes = buildRoutes(ids).filter((r) => !r.skip);

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: WIDTH, height: HEIGHT });

  const results: { slug: string; status: "ok" | "error"; note?: string }[] = [];

  for (const route of routes) {
    const outPath = path.join(OUT_DIR, `${route.slug}.png`);
    process.stdout.write(`  ${route.slug.padEnd(35)} `);

    try {
      await page.goto(`${FRONTEND}${route.path}`, {
        waitUntil: "networkidle",
        timeout: 15_000,
      });

      // Wait for the page to have visible content beyond the nav shell.
      await page.waitForFunction(
        () => document.body && document.body.innerText.trim().length > 20,
        { timeout: 8_000 }
      ).catch(() => {
        // Non-fatal — still capture whatever is rendered.
      });

      // Brief pause for any client-side transitions to settle.
      await page.waitForTimeout(400);

      await page.screenshot({ path: outPath, fullPage: true });
      const stat = fs.statSync(outPath);
      console.log(`✓  ${(stat.size / 1024).toFixed(0)} KB`);
      results.push({ slug: route.slug, status: "ok" });
    } catch (err) {
      const msg = err instanceof Error ? err.message.split("\n")[0] : String(err);
      console.log(`✗  ${msg}`);
      results.push({ slug: route.slug, status: "error", note: msg });
    }
  }

  await browser.close();

  // ── Summary ───────────────────────────────────────────────────────────────
  const ok    = results.filter((r) => r.status === "ok").length;
  const error = results.filter((r) => r.status === "error").length;
  console.log(`\n${ok} captured, ${error} failed`);
  if (error > 0) {
    console.log("Failed:");
    results.filter((r) => r.status === "error").forEach((r) =>
      console.log(`  ✗ ${r.slug}: ${r.note}`)
    );
  }

  // Write an index for easy navigation.
  const indexPath = path.join(OUT_DIR, "index.html");
  const imgs = results
    .filter((r) => r.status === "ok")
    .map(
      (r) =>
        `<figure>
          <figcaption>${r.slug}</figcaption>
          <a href="${r.slug}.png" target="_blank">
            <img src="${r.slug}.png" alt="${r.slug}" loading="lazy">
          </a>
        </figure>`
    )
    .join("\n");

  fs.writeFileSync(
    indexPath,
    `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Context Studio — UX Screenshots</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font: 14px/1.5 system-ui, sans-serif; background: #111; color: #eee; padding: 24px; }
    h1 { margin-bottom: 24px; font-size: 18px; font-weight: 600; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; }
    figure { background: #1e1e1e; border-radius: 8px; overflow: hidden; }
    figcaption { padding: 8px 12px; font-size: 12px; color: #aaa; background: #252525; }
    img { width: 100%; display: block; border-top: 1px solid #333; }
    a { display: block; }
    a:hover img { opacity: 0.85; }
  </style>
</head>
<body>
  <h1>Context Studio — UX Screenshots (${new Date().toLocaleDateString()})</h1>
  <div class="grid">
${imgs}
  </div>
</body>
</html>`
  );

  console.log(`\nIndex: ${indexPath}`);
  console.log(`       open ${indexPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
