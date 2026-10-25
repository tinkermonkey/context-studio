import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { RunApplyControls } from "../RunApplyControls";
import type { components } from "@/api/types";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];
type ApplyRunResponse = components["schemas"]["ApplyRunResponse"];

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

function createMockRun(overrides?: Partial<PipelineRunResponse>): PipelineRunResponse {
  return {
    id: "run-001",
    batch_run_id: "batch-001",
    pipeline_type: "schema_node_grounding",
    implementation_id: "impl-001",
    configuration_slug: "test-config",
    configuration_ref: "main",
    configuration_version: 1,
    status: "completed",
    started_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    failure_reason: null,
    input_summary: { node_id: "node-789" },
    output_summary: {},
    ...overrides,
  } as PipelineRunResponse;
}

function createMockApplyResponse(): ApplyRunResponse {
  return {
    run_id: "run-001",
    pipeline_type: "schema_node_grounding",
    classes_created: 0,
    classes_updated: 1,
    classes_skipped: 0,
    properties_created: 0,
    properties_skipped: 0,
    individuals_created: 0,
    individuals_skipped: 0,
    external_references_created: 1,
    relationships_created: 0,
    relationships_modified: 0,
    relationships_skipped: 0,
    created_class_ids: [],
  } as unknown as ApplyRunResponse;
}

async function confirmApply() {
  await userEvent.click(screen.getByTestId("run-apply-button"));
  const dialog = screen.getByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: /Apply/i }));
}

describe("RunApplyControls", () => {
  it("disables apply when nothing is selected", () => {
    render(<RunApplyControls run={createMockRun()} selectedCount={0} />);
    const button = screen.getByTestId("run-apply-button");
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("No candidates selected");
    expect(button).toHaveAttribute("aria-label", "Apply selected candidates");
  });

  it("shows the selected count and the fixed 0.95 threshold", async () => {
    render(<RunApplyControls run={createMockRun()} selectedCount={2} />);
    const button = screen.getByTestId("run-apply-button");
    expect(button).toHaveTextContent("Apply selected (2)");
    await userEvent.click(button);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("0.95")).toBeInTheDocument();
    expect(within(dialog).getByText("2 candidates")).toBeInTheDocument();
  });

  it("shows the already applied state", () => {
    render(<RunApplyControls run={createMockRun()} selectedCount={1} isApplied />);
    expect(screen.getByTestId("run-apply-button-disabled")).toBeDisabled();
    expect(screen.queryByTestId("run-apply-button")).not.toBeInTheDocument();
  });

  it("displays targetName in the confirmation dialog when provided", async () => {
    render(<RunApplyControls run={createMockRun()} selectedCount={1} targetName="My Node" />);
    await userEvent.click(screen.getByTestId("run-apply-button"));
    expect(within(screen.getByRole("dialog")).getByText("My Node")).toBeInTheDocument();
  });

  it("displays implementation_id when targetName is not provided", async () => {
    render(<RunApplyControls run={createMockRun()} selectedCount={1} />);
    await userEvent.click(screen.getByTestId("run-apply-button"));
    expect(within(screen.getByRole("dialog")).getByText("impl-001")).toBeInTheDocument();
  });

  it.each([
    "schema_node_grounding",
    "schema_node_definition_refinement",
    "schema_node_connection_refinement",
  ])("sends node_id and the 0.95 threshold for %s", async (pipelineType) => {
    let query: URLSearchParams | undefined;
    let bodyText: string | undefined;
    server.use(
      http.post("*/api/pipelines/runs/run-001/apply", async ({ request }) => {
        query = new URL(request.url).searchParams;
        bodyText = await request.text();
        return HttpResponse.json(createMockApplyResponse());
      }),
    );
    const onApplySuccess = vi.fn();
    render(
      <RunApplyControls
        run={createMockRun({ pipeline_type: pipelineType })}
        selectedCount={1}
        onApplySuccess={onApplySuccess}
      />,
    );

    await confirmApply();

    await waitFor(() => expect(onApplySuccess).toHaveBeenCalled());
    expect(query?.get("node_id")).toBe("node-789");
    expect(query?.get("confidence_threshold")).toBe("0.95");
    // Node-scoped apply is threshold-based: no explicit candidate selection is sent.
    expect(bodyText ?? "").not.toContain("accepted_candidate_ids");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("prevents apply when node_id is missing", async () => {
    const onApplySuccess = vi.fn();
    const applySpy = vi.fn();
    server.use(
      http.post("*/api/pipelines/runs/run-001/apply", () => {
        applySpy();
        return HttpResponse.json(createMockApplyResponse());
      }),
    );
    render(
      <RunApplyControls
        run={createMockRun({ input_summary: {} })}
        selectedCount={1}
        onApplySuccess={onApplySuccess}
      />,
    );

    await confirmApply();

    expect(applySpy).not.toHaveBeenCalled();
    expect(onApplySuccess).not.toHaveBeenCalled();
  });
});
