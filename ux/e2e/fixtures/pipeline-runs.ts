import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { Page, Route } from "@playwright/test";
import { apiRequest } from "./api-client";
import { TEST_DB_URLS } from "./test-db";

/**
 * Pipeline-run seeding for E2E — completed extraction runs WITHOUT live LLM calls.
 *
 * The extraction review page starts runs with `POST /api/pipelines/{type}/run`,
 * which executes the LLM pipeline synchronously. E2E must never do that, so
 * `routeRunsToSeededOutput` intercepts those two POSTs and, for each request the
 * UI really sends, writes a COMPLETED run with a fixed `output_summary` into the
 * isolated test DB (seed_pipeline_run.py mirrors the run route minus the
 * orchestrator). It then answers the POST with that run as the backend returns
 * it from `GET /api/pipelines/runs/{id}`.
 *
 * Everything downstream — candidates, recognition preview, apply, revert,
 * change events — hits the real test backend against real rows.
 */

const UX_DIR = process.cwd();
const BACKEND_DIR = resolve(UX_DIR, "../local-server");
const VENV_PYTHON = resolve(BACKEND_DIR, ".venv/bin/python");
const SEED_SCRIPT = resolve(UX_DIR, "e2e/fixtures/seed_pipeline_run.py");

export type ExtractionPipelineType = "schema_extraction" | "individual_extraction";

export interface SeededRun {
  id: string;
  pipeline_type: string;
  status: string;
  implementation_id: string;
  configuration_ref: string;
  configuration_version: number;
}

/** Capture of one intercepted run POST: the body the UI sent and the run it got back. */
export interface InterceptedRun {
  request: Record<string, unknown>;
  run: SeededRun;
}

async function configurationVersion(
  page: Page,
  pipelineType: ExtractionPipelineType,
  implementationId: string,
  configurationRef: string,
): Promise<number> {
  const configs = await apiRequest<{ config_ref: string; version: number }[]>(
    page,
    `/api/pipelines/types/${pipelineType}/implementations/${implementationId}/configurations`,
  );
  return configs.find((c) => c.config_ref === configurationRef)?.version ?? 1;
}

/** Write a COMPLETED run for `request` with `outputSummary` and return it as the API reports it. */
export async function seedCompletedRun(
  page: Page,
  pipelineType: ExtractionPipelineType,
  request: Record<string, unknown>,
  outputSummary: Record<string, unknown>,
): Promise<SeededRun> {
  const version = await configurationVersion(
    page,
    pipelineType,
    String(request.implementation_id),
    String(request.configuration_ref),
  );
  const stdout = execFileSync(VENV_PYTHON, [SEED_SCRIPT], {
    cwd: BACKEND_DIR,
    input: JSON.stringify({
      db_url: TEST_DB_URLS.local,
      pipeline_type: pipelineType,
      request,
      configuration_version: version,
      output_summary: outputSummary,
    }),
    encoding: "utf8",
    env: { ...process.env, PYTHONPATH: BACKEND_DIR },
  });
  const { run_id } = JSON.parse(stdout.trim().split("\n").pop() ?? "{}") as { run_id: string };
  return apiRequest<SeededRun>(page, `/api/pipelines/runs/${run_id}`);
}

/**
 * Answer the page's `POST /api/pipelines/{type}/run` calls with seeded completed runs.
 *
 * `outputs` maps each pipeline type to the `output_summary` its run completes with.
 * Returns a live record of what was intercepted, keyed by pipeline type (latest
 * request wins), so specs can assert the request the UI sent and use the run id.
 */
export async function routeRunsToSeededOutput(
  page: Page,
  outputs: Partial<Record<ExtractionPipelineType, Record<string, unknown>>>,
): Promise<Partial<Record<ExtractionPipelineType, InterceptedRun>>> {
  const intercepted: Partial<Record<ExtractionPipelineType, InterceptedRun>> = {};
  for (const [pipelineType, outputSummary] of Object.entries(outputs) as [
    ExtractionPipelineType,
    Record<string, unknown>,
  ][]) {
    await page.route(`**/api/pipelines/${pipelineType}/run`, async (route: Route) => {
      if (route.request().method() !== "POST") return route.fallback();
      const request = route.request().postDataJSON() as Record<string, unknown>;
      const run = await seedCompletedRun(page, pipelineType, request, outputSummary);
      intercepted[pipelineType] = { request, run };
      await route.fulfill({ status: 201, contentType: "application/json", json: run });
    });
  }
  return intercepted;
}

/** Answer the page's run POST for `pipelineType` with an API error (failed-run state). */
export async function routeRunToFailure(
  page: Page,
  pipelineType: ExtractionPipelineType,
  detail: string,
): Promise<void> {
  await page.route(`**/api/pipelines/${pipelineType}/run`, async (route: Route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({ status: 500, contentType: "application/json", json: { detail } });
  });
}
