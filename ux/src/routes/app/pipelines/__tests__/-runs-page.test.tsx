import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { pipelineService } from "@/api/services/pipeline";
import type { components } from "@/api/types";
import { RunsPage } from "../runs";

type PipelineRun = components["schemas"]["PipelineRunResponse"];

// The shared Heimdall test double has no FilterDropdown: use the shipped components.
vi.mock("@tinkermonkey/heimdall-ui", async () => vi.importActual("@tinkermonkey/heimdall-ui"));

const navigate = vi.hoisted(() => vi.fn());
let search: { selected?: string } = {};
vi.mock("@tanstack/react-router", async () => ({
  ...(await vi.importActual("@tanstack/react-router")),
  useNavigate: () => navigate,
  useSearch: () => search,
}));

const run = (overrides: Partial<PipelineRun>): PipelineRun =>
  ({
    id: "run-1",
    batch_run_id: "batch-1",
    pipeline_type: "individual_extraction",
    implementation_id: "two_step",
    configuration_ref: "extraction-two-step",
    // Not what is shown: the slug used to stand in for the implementation.
    configuration_slug: "slug-not-shown",
    configuration_version: 2,
    status: "completed",
    started_at: "2026-11-12T16:36:00Z",
    output_summary: { candidate_count: 4 },
    ...overrides,
  }) as PipelineRun;

describe("RunsPage", () => {
  beforeEach(() => {
    search = {};
    navigate.mockReset();
    vi.spyOn(pipelineService, "listTypes").mockResolvedValue([]);
    vi.spyOn(pipelineService, "listRuns").mockResolvedValue({
      items: [run({}), run({ id: "run-2", implementation_id: "classic", configuration_ref: "" })],
      total: 2,
      limit: 25,
      offset: 0,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows each run's implementation and configuration in their own columns", async () => {
    render(<RunsPage />);
    const table = await screen.findByTestId("runs-table");
    expect(
      [...table.querySelectorAll(".runs-table-header-cell")].map((cell) => cell.textContent),
    ).toEqual([
      "Pipeline Type",
      "Implementation",
      "Configuration",
      "Status",
      "Started",
      "Candidates",
    ]);

    const implementation = within(table).getByTestId("run-implementation-run-1");
    expect(implementation).toHaveClass("runs-table-cell");
    expect(implementation).toHaveTextContent(/^two_step$/);
    // The full value stays reachable when the column is narrow.
    expect(implementation).toHaveAttribute("title", "two_step");
    const configuration = within(table).getByTestId("run-configuration-run-1");
    expect(configuration).toHaveTextContent(/^extraction-two-step v2$/);
    expect(configuration).toHaveAttribute("title", "extraction-two-step");
    expect(within(table).queryByText(/slug-not-shown/)).not.toBeInTheDocument();

    // A run without a configuration ref shows a dash, not a version alone.
    expect(within(table).getByTestId("run-implementation-run-2")).toHaveTextContent(/^classic$/);
    expect(within(table).getByTestId("run-configuration-run-2")).toHaveTextContent(/^—$/);
  });

  it("selects a run through the URL", async () => {
    render(<RunsPage />);
    const row = await screen.findByTestId("run-row-run-1");
    expect(row).toHaveAttribute("aria-selected", "false");
    await userEvent.click(row);
    expect(navigate).toHaveBeenCalledWith(
      expect.objectContaining({ search: { selected: "run-1" }, replace: true }),
    );
  });
});
