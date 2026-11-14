import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { pipelineService } from "@/api/services/pipeline";
import { adminService } from "@/api/services/admin";
import { PipelinesPage, type PipelinesSearch } from "../index";

const TYPES = [
  { pipeline_type: "no_op", description: "Does nothing", input_contract: {}, output_contract: {} },
  {
    pipeline_type: "individual_extraction",
    description: "Extract individuals",
    input_contract: {},
    output_contract: {},
  },
];

function renderPage(search: PipelinesSearch = {}) {
  vi.spyOn(pipelineService, "listTypes").mockResolvedValue(TYPES);
  vi.spyOn(pipelineService, "listImplementations").mockImplementation(async (type) => [
    { id: "two_step", pipeline_type: type, is_default: false, extracts_sources: false },
    { id: "classic", pipeline_type: type, is_default: true, extracts_sources: false },
  ]);
  vi.spyOn(pipelineService, "listConfigurations").mockResolvedValue([]);
  vi.spyOn(adminService, "getHealth").mockResolvedValue(
    {} as Awaited<ReturnType<typeof adminService.getHealth>>,
  );
  const handlers = { onSearchChange: vi.fn(), onOpenRuns: vi.fn(), onRun: vi.fn() };
  render(<PipelinesPage search={search} {...handlers} />);
  return handlers;
}

describe("PipelinesPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the first pipeline type until the URL names one", async () => {
    renderPage();
    const first = await screen.findByTestId("pipeline-type-list-item-no_op");
    expect(first).toHaveAttribute("aria-selected", "true");
    expect(first).toHaveClass("pipeline-type-list-item--active");
    expect(screen.getByTestId("pipeline-type-content-no_op")).toBeInTheDocument();
    // no_op has no run wizard.
    expect(screen.queryByTestId("pipeline-run-btn")).not.toBeInTheDocument();
  });

  it("shows the type and implementation the URL names, and runs that type", async () => {
    const { onRun } = renderPage({ type: "individual_extraction", impl: "two_step" });
    const item = await screen.findByTestId("pipeline-type-list-item-individual_extraction");
    expect(item).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("pipeline-type-list-item-no_op")).toHaveAttribute(
      "aria-selected",
      "false",
    );
    await waitFor(() => expect(screen.getByTestId("pipeline-implementation")).toHaveValue("two_step"));

    await userEvent.click(screen.getByTestId("pipeline-run-btn"));
    expect(onRun).toHaveBeenCalledWith("individual_extraction");
  });

  it("puts the chosen type, then its implementation, in the URL", async () => {
    const { onSearchChange } = renderPage({ type: "individual_extraction" });
    const implementation = await screen.findByTestId("pipeline-implementation");
    await waitFor(() => expect(implementation).toHaveValue("classic"));
    await userEvent.selectOptions(implementation, "two_step");
    expect(onSearchChange).toHaveBeenLastCalledWith({
      type: "individual_extraction",
      impl: "two_step",
    });

    // Another type starts from its own default implementation.
    await userEvent.click(screen.getByTestId("pipeline-type-list-item-no_op"));
    expect(onSearchChange).toHaveBeenLastCalledWith({ type: "no_op" });
  });

  it("opens the runs list", async () => {
    const { onOpenRuns } = renderPage();
    await userEvent.click(await screen.findByTestId("pipelines-all-runs"));
    expect(onOpenRuns).toHaveBeenCalledTimes(1);
  });
});
