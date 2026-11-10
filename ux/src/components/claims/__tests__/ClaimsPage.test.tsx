import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { claimHandlers, claimOne, claimTwo } from "@/test/claimFixtures";
import { downloadText } from "@/lib/download";
import { ClaimsPage } from "../ClaimsPage";
import type { ClaimsSearch } from "../claimModel";

// The real components, for their ARIA (radio groups, listbox selects, labelled fields).
vi.mock("@tinkermonkey/heimdall-ui", async () => vi.importActual("@tinkermonkey/heimdall-ui"));

const navigate = vi.fn();
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => navigate };
});
vi.mock("@/lib/download", () => ({ downloadText: vi.fn() }));

const { handlers, requests } = claimHandlers();
const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  requests.lists.length = 0;
  requests.exports.length = 0;
  vi.mocked(downloadText).mockReset();
  navigate.mockReset();
});
afterAll(() => server.close());

function renderPage(search: ClaimsSearch, onSearchChange = vi.fn()) {
  render(<ClaimsPage search={search} onSearchChange={onSearchChange} />);
  return onSearchChange;
}

describe("ClaimsPage", () => {
  it("asks for a taxonomy before listing claims", async () => {
    renderPage({});

    expect(screen.getByTestId("claims-page")).toHaveClass("stack-lg");
    expect(screen.getByTestId("claims-pick-taxonomy")).toHaveTextContent("Choose a taxonomy");
    expect(screen.getByTestId("claims-export-button")).toBeDisabled();
    expect(screen.queryByTestId("claims-table")).not.toBeInTheDocument();
    expect(requests.lists).toHaveLength(0);
  });

  it("lists claims with subject, triage validity and p, severity, fix scope and verdict", async () => {
    renderPage({ taxonomy: "tax-1" });

    const cell = await screen.findByTestId("claim-row-claim-1");
    expect(cell).toHaveClass("claim-cell");
    expect(cell).toHaveTextContent("BusinessActor's name attribute should be required.");
    expect(within(cell).getByText("note-7#1")).toHaveClass("claim-cell__key");

    const row = cell.closest("tr") as HTMLElement;
    expect(await within(row).findByText("business.businessactor")).toHaveClass(
      "claim-cell__subject",
    );
    const triage = screen.getByTestId("claim-triage-cell-claim-1");
    expect(within(triage).getByText("real defect")).toHaveClass("chip--rose");
    expect(within(triage).getByText("p 0.82")).toHaveClass("claim-cell__p");
    expect(within(row).getByText("2 · significant")).toHaveClass("claim-cell__score");
    expect(within(row).getByText("1 · additive")).toHaveClass("claim-cell__score");

    const untriaged = screen.getByTestId("claim-row-claim-2").closest("tr") as HTMLElement;
    expect(within(untriaged).getByText("untriaged")).toBeInTheDocument();
    expect(screen.getByTestId("claim-verdict-cell-claim-2")).toHaveClass("chip--emerald");
    expect(screen.getByTestId("claim-verdict-cell-claim-2")).toHaveTextContent("works as designed");

    expect(screen.getByTestId("claims-count")).toHaveTextContent("2 claims");
    expect(screen.getByTestId("claims-table")).toHaveClass("schema-table-wrap");
    expect(screen.getByTestId("schema-page-layout")).not.toHaveClass("split-2");
    expect(screen.queryByTestId("claim-inspector")).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Subject" })).toBeInTheDocument();
  });

  it("sends the URL's filters to the claims API", async () => {
    renderPage({
      taxonomy: "tax-1",
      subject: "cls-actor",
      validity: "judgment_call",
      triage: "untriaged",
      verdict: "without",
    });

    await screen.findByTestId("claim-row-claim-1");
    const params = requests.lists.at(-1)!;
    expect(params.get("subject_id")).toBe("cls-actor");
    expect(params.get("validity")).toBe("judgment_call");
    expect(params.get("triaged")).toBe("false");
    expect(params.get("has_verdict")).toBe("false");
    expect(params.get("limit")).toBe("50");
    expect(params.get("offset")).toBe("0");
  });

  it("filters by triage and verdict with labelled radio groups", async () => {
    const user = userEvent.setup();
    const onSearchChange = renderPage({ taxonomy: "tax-1" });
    await screen.findByTestId("claim-row-claim-1");

    const triage = screen.getByRole("radiogroup", { name: "Triage" });
    expect(triage).toHaveAttribute("data-testid", "claims-triage-filter");
    await user.click(within(triage).getByRole("radio", { name: "Untriaged" }));
    expect(onSearchChange).toHaveBeenLastCalledWith({ taxonomy: "tax-1", triage: "untriaged" });

    const verdict = screen.getByRole("radiogroup", { name: "Verdict" });
    await user.click(within(verdict).getByRole("radio", { name: "With verdict" }));
    expect(onSearchChange).toHaveBeenLastCalledWith({ taxonomy: "tax-1", verdict: "with" });
  });

  it("selects a claim on row click", async () => {
    const user = userEvent.setup();
    const onSearchChange = renderPage({ taxonomy: "tax-1" });

    await user.click(await screen.findByTestId("claim-row-claim-2"));
    expect(onSearchChange).toHaveBeenLastCalledWith({ taxonomy: "tax-1", selected: "claim-2" });
  });

  it("opens the selected claim in the inspector beside the table", async () => {
    renderPage({ taxonomy: "tax-1", selected: "claim-1" });

    const inspector = await screen.findByTestId("claim-inspector");
    const layout = screen.getByTestId("schema-page-layout");
    expect(layout).toHaveClass("split-2");
    expect(
      within(screen.getByTestId("schema-inspector-container")).getByTestId("claim-inspector"),
    ).toBe(inspector);
    expect(within(inspector).getByTestId("claim-text")).toHaveTextContent(claimOne.text);
    // The inspector shows the subject, so the narrower table drops that column
    expect(screen.queryByRole("columnheader", { name: "Subject" })).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Verdict" })).toBeInTheDocument();
  });

  it("keeps a selected claim open when it is not in the filtered list", async () => {
    // The list no longer has claim-1 (say a verdict moved it out of "No verdict").
    server.use(
      http.get("*/api/taxonomies/:taxonomyId/claims", () =>
        HttpResponse.json({ items: [claimTwo], total: 1, limit: 50, offset: 0 }),
      ),
    );
    renderPage({ taxonomy: "tax-1", selected: "claim-1" });

    const inspector = await screen.findByTestId("claim-inspector");
    expect(within(inspector).getByTestId("claim-text")).toHaveTextContent(claimOne.text);
    expect(screen.getByTestId("schema-page-layout")).toHaveClass("split-2");
  });

  it("exports the filtered claims as JSONL", async () => {
    const user = userEvent.setup();
    renderPage({ taxonomy: "tax-1", verdict: "with" });
    await screen.findByTestId("claim-row-claim-1");

    await user.click(screen.getByTestId("claims-export-button"));

    await waitFor(() => expect(downloadText).toHaveBeenCalled());
    expect(requests.exports.at(-1)!.get("has_verdict")).toBe("true");
    const [filename, text, type] = vi.mocked(downloadText).mock.calls[0];
    expect(filename).toBe("claims-dr_spec.jsonl");
    expect(type).toBe("application/x-ndjson");
    expect(
      text
        .trim()
        .split("\n")
        .map((line) => JSON.parse(line).id),
    ).toEqual(["claim-1", "claim-2"]);
  });
});
