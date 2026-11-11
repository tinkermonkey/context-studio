import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { DrSpecDriftDialog, SPEC_DIR_KEY } from "../DrSpecDriftDialog";

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => vi.fn() };
});

const SPEC = "/work/documentation_robotics/spec";
const revision = { repo: "git@github.com:x/dr.git", commit: "b016a07412", spec_version: "0.11.0" };
const entries = [
  {
    kind: "class",
    source_id: "api.contact",
    change: "update",
    entity_id: "c1",
    fields: { description: { taxonomy: "Old", source: "New" } },
  },
  {
    kind: "property",
    source_id: "api.contact.uses.api.server",
    change: "create",
    fields: { title: { taxonomy: null, source: "uses" } },
  },
];

const requests: Array<{ spec_dir: string; dry_run: boolean }> = [];

const server = setupServer(
  http.post("*/api/v1/interchange/dr-spec/drift", async ({ request }) => {
    const body = (await request.json()) as { spec_dir: string; dry_run: boolean };
    requests.push(body);
    if (body.spec_dir === "/nowhere") {
      return HttpResponse.json(
        { detail: "/nowhere is not a DR spec directory (no dist/manifest.json)" },
        { status: 422 },
      );
    }
    return HttpResponse.json({
      taxonomy_id: "tax-dr",
      source_revision: revision,
      dry_run: body.dry_run,
      entries,
      proposal: { id: "proposal-9", dry_run: body.dry_run },
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  requests.length = 0;
  window.localStorage.clear();
});
afterAll(() => server.close());

describe("DrSpecDriftDialog", () => {
  it("checks the spec as a dry run, then proposes what differs", async () => {
    const user = userEvent.setup();
    render(<DrSpecDriftDialog open onClose={vi.fn()} />);

    expect(screen.getByTestId("dr-drift-dialog")).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("region", { name: "DR spec drift" })).toBeInTheDocument();
    expect(screen.getByTestId("dr-drift-propose")).toBeDisabled();

    await user.type(screen.getByTestId("dr-drift-spec-dir"), SPEC);
    await user.click(screen.getByTestId("dr-drift-check"));

    expect(await screen.findByTestId("dr-drift-summary")).toHaveTextContent(
      "2 entities differ from spec 0.11.0 (b016a074).",
    );
    expect(requests).toEqual([{ spec_dir: SPEC, dry_run: true }]);
    const table = screen.getByTestId("dr-drift-entries");
    expect(within(table).getByText("api.contact")).toHaveClass("drift-dialog__id");
    expect(within(table).getByText("update")).toHaveClass("chip--cyan");
    expect(within(table).getByText("create")).toHaveClass("chip--emerald");
    expect(within(table).getByText("description")).toHaveClass("drift-dialog__fields");
    // A create lists what it would set, which isn't a difference: it shows a dash
    expect(within(table).getByText("—")).toHaveClass("drift-dialog__fields");
    expect(within(table).queryByText("title")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(SPEC_DIR_KEY)).toBe(SPEC);

    await user.click(screen.getByTestId("dr-drift-propose"));

    const link = await screen.findByTestId("dr-drift-proposal-link");
    expect(link).toHaveAttribute("href", "/app/proposals/proposal-9");
    expect(requests.at(-1)).toEqual({ spec_dir: SPEC, dry_run: false });
    expect(screen.getByTestId("dr-drift-propose")).toBeDisabled();
  });

  it("says when nothing differs and offers no proposal", async () => {
    server.use(
      http.post("*/api/v1/interchange/dr-spec/drift", () =>
        HttpResponse.json({
          taxonomy_id: "tax-dr",
          source_revision: revision,
          dry_run: true,
          entries: [],
          proposal: null,
        }),
      ),
    );
    window.localStorage.setItem(SPEC_DIR_KEY, SPEC);
    const user = userEvent.setup();
    render(<DrSpecDriftDialog open onClose={vi.fn()} />);

    expect(screen.getByTestId("dr-drift-spec-dir")).toHaveValue(SPEC);
    await user.click(screen.getByTestId("dr-drift-check"));

    expect(await screen.findByTestId("dr-drift-summary")).toHaveTextContent(
      "No drift: the taxonomy matches spec 0.11.0 (b016a074).",
    );
    expect(screen.queryByTestId("dr-drift-entries")).not.toBeInTheDocument();
    expect(screen.getByTestId("dr-drift-propose")).toBeDisabled();
  });

  it("shows why a directory is refused and clears it as the path is corrected", async () => {
    const user = userEvent.setup();
    render(<DrSpecDriftDialog open onClose={vi.fn()} />);

    await user.type(screen.getByTestId("dr-drift-spec-dir"), "/nowhere");
    await user.click(screen.getByTestId("dr-drift-check"));

    expect(
      await screen.findByText("/nowhere is not a DR spec directory (no dist/manifest.json)"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("dr-drift-spec-dir")).toHaveAttribute("aria-invalid", "true");

    await user.type(screen.getByTestId("dr-drift-spec-dir"), "/spec");

    expect(
      screen.queryByText("/nowhere is not a DR spec directory (no dist/manifest.json)"),
    ).not.toBeInTheDocument();
  });
});
