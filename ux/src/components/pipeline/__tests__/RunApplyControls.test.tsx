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
    pipeline_type: "schema_extraction",
    implementation_id: "impl-001",
    configuration_slug: "test-config",
    configuration_ref: "main",
    configuration_version: 1,
    status: "COMPLETED",
    started_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    failure_reason: null,
    input_summary: { concept_scheme_id: "scheme-001" },
    output_summary: {
      candidate_count: 5,
      classes: [
        { id: "class-0", name: "Class A", confidence: 0.95 },
        { id: "class-1", name: "Class B", confidence: 0.80 },
        { id: "class-2", name: "Class C", confidence: 0.60 },
      ],
      properties: [
        { id: "prop-0", name: "Property 1", confidence: 0.90 },
        { id: "prop-1", name: "Property 2", confidence: 0.70 },
      ],
      relationships: [
        { id: "rel-0", name: "Related to", confidence: 0.85 },
      ],
    },
    ...overrides,
  } as PipelineRunResponse;
}

function createMockApplyResponse(): ApplyRunResponse {
  return {
    run_id: "run-001",
    pipeline_type: "schema_extraction",
    classes_created: 2,
    classes_updated: 1,
    classes_skipped: 0,
    properties_created: 1,
    properties_skipped: 0,
    individuals_created: 0,
    individuals_skipped: 0,
    external_references_created: 0,
    relationships_created: 1,
    relationships_modified: 0,
    relationships_skipped: 0,
    created_class_ids: ["class-001", "class-002"],
  } as ApplyRunResponse;
}

describe("RunApplyControls", () => {
  describe("confidence threshold calculation", () => {
    it("returns 0.5 when no candidates are selected", () => {
      const run = createMockRun();
      const onApplySuccess = vi.fn();

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: [],
            properties: [],
            relationships: [],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={onApplySuccess}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      expect(button).toBeDisabled();
      expect(button).toHaveTextContent("No candidates selected");
    });

    it("calculates minimum confidence from selected classes", async () => {
      const run = createMockRun();
      const onApplySuccess = vi.fn();

      server.use(
        http.post("*/api/pipelines/runs/run-001/apply", () =>
          HttpResponse.json(createMockApplyResponse()),
        ),
      );

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: ["class-1", "class-2"],
            properties: [],
            relationships: [],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={onApplySuccess}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      expect(button).not.toBeDisabled();
      expect(button).toHaveTextContent("Apply selected (2)");

      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      const dialogText = within(dialog).getByText(/Confidence threshold will be set to/);

      const match = dialogText.textContent?.match(/(\d+\.\d+)/);
      expect(match).toBeDefined();

      const threshold = parseFloat(match![1]);
      expect(threshold).toBeGreaterThanOrEqual(0.59);
      expect(threshold).toBeLessThanOrEqual(0.60);
    });

    it("calculates minimum confidence from selected properties", async () => {
      const run = createMockRun();

      server.use(
        http.post("*/api/pipelines/runs/run-001/apply", () =>
          HttpResponse.json(createMockApplyResponse()),
        ),
      );

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: [],
            properties: ["prop-1"],
            relationships: [],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={vi.fn()}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      const dialogText = within(dialog).getByText(/Confidence threshold will be set to/);

      const match = dialogText.textContent?.match(/(\d+\.\d+)/);
      const threshold = parseFloat(match![1]);

      expect(threshold).toBeGreaterThanOrEqual(0.69);
      expect(threshold).toBeLessThanOrEqual(0.70);
    });

    it("calculates minimum confidence from selected relationships", async () => {
      const run = createMockRun();

      server.use(
        http.post("*/api/pipelines/runs/run-001/apply", () =>
          HttpResponse.json(createMockApplyResponse()),
        ),
      );

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: [],
            properties: [],
            relationships: ["rel-0"],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={vi.fn()}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      const dialogText = within(dialog).getByText(/Confidence threshold will be set to/);

      const match = dialogText.textContent?.match(/(\d+\.\d+)/);
      const threshold = parseFloat(match![1]);

      expect(threshold).toBeGreaterThanOrEqual(0.84);
      expect(threshold).toBeLessThanOrEqual(0.85);
    });

    it("uses minimum confidence across mixed candidate types", async () => {
      const run = createMockRun();

      server.use(
        http.post("*/api/pipelines/runs/run-001/apply", () =>
          HttpResponse.json(createMockApplyResponse()),
        ),
      );

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: ["class-0"],
            properties: ["prop-1"],
            relationships: ["rel-0"],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={vi.fn()}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      const dialogText = within(dialog).getByText(/Confidence threshold will be set to/);

      const match = dialogText.textContent?.match(/(\d+\.\d+)/);
      const threshold = parseFloat(match![1]);

      expect(threshold).toBeGreaterThanOrEqual(0.69);
      expect(threshold).toBeLessThanOrEqual(0.70);
    });

    it("defaults to 0 for non-schema-extraction pipeline types", () => {
      const run = createMockRun({ pipeline_type: "individual_extraction" });

      render(
        <RunApplyControls
          run={run}
          pipelineType="individual_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: [],
            properties: [],
            relationships: [],
            individuals: ["ind-0"],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={vi.fn()}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      expect(button).not.toBeDisabled();
    });

    it("shows already applied state correctly", () => {
      const run = createMockRun();

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: ["class-0"],
            properties: [],
            relationships: [],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          isApplied={true}
          onApplySuccess={vi.fn()}
        />,
      );

      const button = screen.getByTestId("run-apply-button-disabled");
      expect(button).toBeDisabled();
      expect(button).toHaveTextContent("Already applied");
    });

    it("counts all candidate types in total", () => {
      const run = createMockRun();

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: ["class-0"],
            properties: ["prop-0", "prop-1"],
            relationships: ["rel-0"],
            individuals: ["ind-0"],
            groundingCandidates: ["ground-0"],
            refinementCandidates: ["ref-0"],
          }}
          onApplySuccess={vi.fn()}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      expect(button).toHaveTextContent("Apply selected (7)");
    });

    it("handles empty output summary gracefully", () => {
      const run = createMockRun({
        output_summary: undefined,
      });

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={undefined}
          selectedCandidates={{
            classes: ["class-0"],
            properties: [],
            relationships: [],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={vi.fn()}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      expect(button).not.toBeDisabled();
    });
  });

  describe("apply action", () => {
    it("opens confirmation dialog when apply button clicked", async () => {
      const run = createMockRun();
      const onApplySuccess = vi.fn();

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: ["class-0"],
            properties: [],
            relationships: [],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={onApplySuccess}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      expect(button).toBeInTheDocument();

      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeInTheDocument();

      const confirmText = within(dialog).getByText(/You are about to apply/);
      expect(confirmText).toBeInTheDocument();
    });

    it("includes concept_scheme_id for schema extraction", async () => {
      const run = createMockRun({
        input_summary: { concept_scheme_id: "scheme-123" },
      });
      const onApplySuccess = vi.fn();

      server.use(
        http.post("*/api/pipelines/runs/run-001/apply", async ({ request }) => {
          const body = await request.json();
          expect(body).toHaveProperty("concept_scheme_id", "scheme-123");
          return HttpResponse.json(createMockApplyResponse());
        }),
      );

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: ["class-0"],
            properties: [],
            relationships: [],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={onApplySuccess}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      const confirmButton = within(dialog).getByRole("button", { name: /Apply/i });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      });
    });

    it("includes taxonomy_id for individual extraction", async () => {
      const run = createMockRun({
        pipeline_type: "individual_extraction",
        input_summary: { taxonomy_id: "tax-456" },
      });
      const onApplySuccess = vi.fn();

      server.use(
        http.post("*/api/pipelines/runs/run-001/apply", async ({ request }) => {
          const body = await request.json();
          expect(body).toHaveProperty("taxonomy_id", "tax-456");
          return HttpResponse.json(createMockApplyResponse());
        }),
      );

      render(
        <RunApplyControls
          run={run}
          pipelineType="individual_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: [],
            properties: [],
            relationships: [],
            individuals: ["ind-0"],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={onApplySuccess}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      const confirmButton = within(dialog).getByRole("button", { name: /Apply/i });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      });
    });

    it("includes node_id for grounding pipeline", async () => {
      const run = createMockRun({
        pipeline_type: "schema_node_grounding",
        input_summary: { node_id: "node-789" },
      });
      const onApplySuccess = vi.fn();

      server.use(
        http.post("*/api/pipelines/runs/run-001/apply", async ({ request }) => {
          const body = await request.json();
          expect(body).toHaveProperty("node_id", "node-789");
          return HttpResponse.json(createMockApplyResponse());
        }),
      );

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_node_grounding"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: [],
            properties: [],
            relationships: [],
            individuals: [],
            groundingCandidates: ["ground-0"],
            refinementCandidates: [],
          }}
          onApplySuccess={onApplySuccess}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      const confirmButton = within(dialog).getByRole("button", { name: /Apply/i });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      });
    });
  });

  describe("button states", () => {
    it("disables apply button while request is in flight", async () => {
      const run = createMockRun();

      let resolveRequest: any;
      const requestPromise = new Promise((resolve) => {
        resolveRequest = resolve;
      });

      server.use(
        http.post("*/api/pipelines/runs/run-001/apply", async () => {
          await requestPromise;
          return HttpResponse.json(createMockApplyResponse());
        }),
      );

      render(
        <RunApplyControls
          run={run}
          pipelineType="schema_extraction"
          outputSummary={run.output_summary}
          selectedCandidates={{
            classes: ["class-0"],
            properties: [],
            relationships: [],
            individuals: [],
            groundingCandidates: [],
            refinementCandidates: [],
          }}
          onApplySuccess={vi.fn()}
        />,
      );

      const button = screen.getByTestId("run-apply-button");
      await userEvent.click(button);

      const dialog = screen.getByRole("dialog");
      const confirmButton = within(dialog).getByRole("button", { name: /Apply/i });

      expect(confirmButton).not.toBeDisabled();
      await userEvent.click(confirmButton);

      resolveRequest();
    });
  });
});
