import { describe, it, expect, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { PipelineTypeCard } from "../PipelineTypeCard";
import type { components } from "@/api/types";

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => vi.fn() };
});

type PipelineTypeResponse = components["schemas"]["PipelineTypeResponse"];
type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];

const type = {
  pipeline_type: "schema_extraction",
  description: "Extract schema",
} as PipelineTypeResponse;

const run = (status: string) =>
  ({ id: "run-1", status, created_at: new Date().toISOString() }) as unknown as PipelineRunResponse;

describe("PipelineTypeCard run status", () => {
  it.each([
    ["completed", "Completed", "chip--emerald"],
    ["failed", "Failed", "chip--rose"],
    ["running", "Running", "chip--cyan"],
    ["pending", "Pending", "chip--amber"],
    ["COMPLETED", "Completed", "chip--emerald"],
  ])("renders the API status %s as %s", (status, label, chipClass) => {
    render(<PipelineTypeCard type={type} latestRun={run(status)} />);
    const statusEl = screen.getByTestId("pipeline-run-status-schema_extraction");
    const chip = within(statusEl).getByText(label);
    expect(chip.closest(".chip")).toHaveClass(chipClass);
    expect(screen.getByTestId("pipeline-type-card-schema_extraction")).toHaveAttribute(
      "role",
      "article",
    );
  });
});
