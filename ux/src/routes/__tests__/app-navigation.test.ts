import { describe, it, expect } from "vitest";
import {
  NAV_ACTIONS,
  SIDEBAR_PATH_MAP,
  getActiveItemId,
  getBreadcrumbLabels,
} from "../-app-navigation";

describe("app navigation — pipelines", () => {
  it("maps pipelines sidebar items to their routes", () => {
    expect(SIDEBAR_PATH_MAP["pipelines"]).toBe("/app/pipelines");
    expect(SIDEBAR_PATH_MAP["pipelines-types"]).toBe("/app/pipelines");
    expect(SIDEBAR_PATH_MAP["pipelines-runs"]).toBe("/app/pipelines/runs");
  });

  it("registers command-palette actions for pipeline types and runs", () => {
    const byId = Object.fromEntries(NAV_ACTIONS.map((a) => [a.id, a]));
    expect(byId["nav-pipelines"]).toMatchObject({
      label: "Pipeline Types",
      to: "/app/pipelines",
    });
    expect(byId["nav-pipeline-runs"]).toMatchObject({
      label: "Pipeline Runs",
      to: "/app/pipelines/runs",
    });
  });

  it.each([
    ["/app/pipelines", "pipelines-types"],
    ["/app/pipelines/types/individual_extraction", "pipelines-types"],
    ["/app/pipelines/types/individual_extraction/run", "pipelines-types"],
    ["/app/pipelines/runs", "pipelines-runs"],
    ["/app/pipelines/batches/abc-123", "pipelines-runs"],
  ])("highlights the right sidebar item for %s", (path, id) => {
    expect(getActiveItemId(path)).toBe(id);
  });

  it.each([
    ["/app/pipelines", ["Pipelines", "Pipeline Types"]],
    ["/app/pipelines/runs", ["Pipelines", "Runs"]],
    [
      "/app/pipelines/types/individual_extraction",
      ["Pipelines", "Pipeline Types", "individual_extraction"],
    ],
    [
      "/app/pipelines/types/individual_extraction/run",
      ["Pipelines", "Pipeline Types", "individual_extraction", "Run"],
    ],
    ["/app/pipelines/batches/abc-123", ["Pipelines", "Runs", "Batch abc-123"]],
  ])("labels breadcrumbs for %s", (path, labels) => {
    expect(getBreadcrumbLabels(path)).toEqual(labels);
  });

  it("decodes encoded type segments and tolerates malformed ones", () => {
    expect(getBreadcrumbLabels("/app/pipelines/types/my%20type")).toEqual([
      "Pipelines",
      "Pipeline Types",
      "my type",
    ]);
    expect(getBreadcrumbLabels("/app/pipelines/types/%E0%A4%A")).toEqual([
      "Pipelines",
      "Pipeline Types",
      "%E0%A4%A",
    ]);
  });

  it("keeps existing labels and falls back to the pathname", () => {
    expect(getBreadcrumbLabels("/app")).toEqual(["Dashboard"]);
    expect(getBreadcrumbLabels("/app/unknown")).toEqual(["/app/unknown"]);
    expect(getActiveItemId("/app")).toBe("dashboard");
  });
});
