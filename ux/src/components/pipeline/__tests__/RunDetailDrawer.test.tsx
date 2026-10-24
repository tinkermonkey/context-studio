import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { RunDetailDrawer } from "../RunDetailDrawer";
import type { components } from "@/api/types";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function makeRun(overrides: Partial<PipelineRunResponse> = {}): PipelineRunResponse {
  return {
    id: "run-1",
    batch_run_id: "batch-1",
    pipeline_type: "schema_extraction",
    implementation_id: "default",
    configuration_ref: "schema-extraction-default",
    configuration_slug: "schema-extraction-default",
    configuration_version: 1,
    status: "completed",
    started_at: "2026-10-23T10:00:00Z",
    updated_at: "2026-10-23T10:00:11Z",
    failure_reason: null,
    input_summary: { taxonomy_id: "tax-1", concept_scheme_id: "scheme-1" },
    output_summary: {},
    ...overrides,
  } as PipelineRunResponse;
}

function serveRun(run: PipelineRunResponse) {
  server.use(
    http.get("*/api/pipelines/runs/run-1", () => HttpResponse.json(run)),
    http.get("*/api/pipelines/runs/run-1/change-events", () =>
      HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 }),
    ),
  );
}

describe("RunDetailDrawer", () => {
  it.each(["schema_extraction", "individual_extraction"])(
    "sends a completed %s run to the Extraction review page instead of applying in place",
    async (pipelineType) => {
      serveRun(makeRun({ pipeline_type: pipelineType }));
      const onOpen = vi.fn();
      render(<RunDetailDrawer runId="run-1" onOpenExtractionReview={onOpen} />);

      const button = await screen.findByTestId("run-open-extraction-review");
      expect(button).toHaveAccessibleName("Review in Extraction review");
      expect(screen.getByTestId("run-completed-section")).toBeInTheDocument();
      expect(screen.queryByTestId("run-apply-section")).not.toBeInTheDocument();
      expect(screen.queryByTestId("run-apply-button")).not.toBeInTheDocument();

      await userEvent.click(button);
      expect(onOpen).toHaveBeenCalledWith("run-1");
    },
  );

  it("keeps the in-drawer review and threshold apply for node-scoped pipelines", async () => {
    serveRun(
      makeRun({
        pipeline_type: "schema_node_grounding",
        input_summary: { node_id: "node-1" },
        output_summary: { candidates: [] },
      }),
    );
    render(<RunDetailDrawer runId="run-1" onOpenExtractionReview={vi.fn()} />);

    expect(await screen.findByTestId("run-apply-section")).toBeInTheDocument();
    expect(screen.getByTestId("run-apply-button")).toBeDisabled();
    expect(screen.getByTestId("grounding-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("run-open-extraction-review")).not.toBeInTheDocument();
  });

  it("renders the lower-case completed status as an emerald chip", async () => {
    serveRun(makeRun());
    render(<RunDetailDrawer runId="run-1" />);
    const chip = await screen.findByText("completed");
    expect(chip.closest(".chip")).toHaveClass("chip--emerald");
  });

  it("shows the failure reason for a lower-case failed run", async () => {
    serveRun(makeRun({ status: "failed", failure_reason: "LLM timeout" }));
    render(<RunDetailDrawer runId="run-1" />);
    expect(await screen.findByTestId("run-failure-reason")).toHaveTextContent("LLM timeout");
    expect(screen.queryByTestId("run-completed-section")).not.toBeInTheDocument();
  });

  it.each([
    ["pending", "run-pending-placeholder"],
    ["running", "run-running-placeholder"],
  ])("shows the %s placeholder for a lower-case status", async (status, testId) => {
    serveRun(makeRun({ status }));
    render(<RunDetailDrawer runId="run-1" />);
    expect(await screen.findByTestId(testId)).toBeInTheDocument();
    expect(screen.queryByTestId("run-completed-section")).not.toBeInTheDocument();
  });
});
