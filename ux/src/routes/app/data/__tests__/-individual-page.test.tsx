import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { dataset, entityPageHandlers, relationship } from "@/test/entityPageHandlers";
import { createDataset } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { useBreadcrumbStore } from "@/stores/breadcrumbs";
import { useNavigatorStore } from "@/stores/navigator";
import { IndividualPage } from "../individuals_.$id";

const server = setupServer(...entityPageHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useNavigatorStore.setState({ expandedIds: new Set(), mode: "schema" });
});
afterAll(() => server.close());

describe("IndividualPage", () => {
  it("renders the header with class chip links", async () => {
    render(<IndividualPage id="ind-1" />);

    expect(await screen.findByRole("heading", { name: "LLM Provider Router" })).toBeInTheDocument();
    expect(screen.getByTestId("individual-page")).toHaveClass("entity-page");
    const chip = await screen.findByTestId("individual-class-chip-class-1");
    expect(chip).toHaveAttribute("href", "/app/schema/classes/class-1");
    expect(chip).toHaveTextContent("ApplicationComponent");
  });

  it("reads outgoing relationships as sentences with linked endpoints", async () => {
    render(<IndividualPage id="ind-1" />);

    const sentence = await screen.findByTestId("individual-relationship-rel-1");
    expect(sentence).toHaveClass("entity-sentence");
    expect(await within(sentence).findByText("— realizes →")).toHaveClass(
      "entity-sentence__predicate",
    );
    const target = await within(sentence).findByRole("link", { name: "Pipeline API" });
    expect(target).toHaveAttribute("href", "/app/data/individuals/ind-2");
    expect(
      within(screen.getByTestId("individual-relationships-panel")).getByText("Outgoing"),
    ).toBeInTheDocument();
  });

  it("shows a relationship's attributes read-only on its row", async () => {
    server.use(
      http.get("*/api/relationships", ({ request }) => {
        const source = new URL(request.url).searchParams.get("source_id");
        const items =
          source === "ind-1"
            ? [{ ...relationship, attributes: { quantity: 2, unit: "each", optional: false } }]
            : [];
        return HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });
      }),
    );
    render(<IndividualPage id="ind-1" />);

    const attributes = await screen.findByTestId("individual-relationship-attributes-rel-1");
    expect(attributes).toHaveClass("relationship-attributes");
    expect(attributes).toHaveAttribute("role", "list");
    expect(
      within(attributes)
        .getAllByRole("listitem")
        .map((i) => i.textContent),
    ).toEqual(["optional no", "quantity 2", "unit each"]);
    expect(within(attributes).getByRole("listitem", { name: "quantity: 2" })).toBeInTheDocument();
    expect(within(attributes).queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("shows no attribute list for a relationship without attributes", async () => {
    render(<IndividualPage id="ind-1" />);

    await screen.findByTestId("individual-relationship-rel-1");
    expect(
      screen.queryByTestId("individual-relationship-attributes-rel-1"),
    ).not.toBeInTheDocument();
  });

  it("reads incoming relationships from the target's side", async () => {
    render(<IndividualPage id="ind-2" />);

    const sentence = await screen.findByTestId("individual-relationship-rel-1");
    const source = await within(sentence).findByRole("link", { name: "LLM Provider Router" });
    expect(source).toHaveAttribute("href", "/app/data/individuals/ind-1");
    expect(
      within(screen.getByTestId("individual-relationships-panel")).getByText("Incoming"),
    ).toBeInTheDocument();
  });

  it("shows data properties, provenance and identity", async () => {
    render(<IndividualPage id="ind-1" />);
    await screen.findByRole("heading", { name: "LLM Provider Router" });

    const properties = screen.getByTestId("individual-data-properties-panel");
    expect(within(properties).getByText("language")).toBeInTheDocument();
    expect(within(properties).getByText("python")).toBeInTheDocument();
    expect(within(properties).getByText("[80,443]")).toBeInTheDocument();
    expect(screen.getByTestId("individual-provenance-panel")).toHaveTextContent(
      "Imported from documentation_robotics",
    );
    expect(screen.getByRole("complementary", { name: "Identity" })).toBeInTheDocument();
  });

  it("breadcrumbs follow the class hierarchy", async () => {
    render(<IndividualPage id="ind-1" />);
    await screen.findByRole("heading", { name: "LLM Provider Router" });

    await waitFor(() =>
      expect(useBreadcrumbStore.getState().crumbs?.map((c) => c.label)).toEqual([
        "Data",
        "Documentation Robotics",
        "Application Layer",
        "ApplicationComponent",
        "LLM Provider Router",
      ]),
    );
  });

  it("opens the navigator in Data mode with the individual under its class", async () => {
    render(<IndividualPage id="ind-1" />);

    expect(
      within(screen.getByTestId("navigator-mode")).getByRole("radio", { name: "Data" }),
    ).toHaveAttribute("aria-checked", "true");
    await waitFor(() =>
      expect(screen.getByTestId("hierarchy-node-ind-1")).toHaveClass("hierarchy-row--selected"),
    );
    expect(screen.getByTestId("hierarchy-node-class-1")).toHaveAttribute("aria-expanded", "true");
  });

  it("highlights the individual's class in Schema mode", async () => {
    const user = userEvent.setup();
    render(<IndividualPage id="ind-1" />);
    await screen.findByTestId("hierarchy-node-ind-1");

    await user.click(
      within(screen.getByTestId("navigator-mode")).getByRole("radio", { name: "Schema" }),
    );

    await waitFor(() =>
      expect(screen.getByTestId("hierarchy-node-class-1")).toHaveClass("hierarchy-row--selected"),
    );
    expect(screen.queryByTestId("hierarchy-node-ind-1")).not.toBeInTheDocument();
  });

  it("shows not found for an unknown individual", async () => {
    render(<IndividualPage id="missing" />);
    expect(await screen.findByText("Individual not found")).toBeInTheDocument();
  });

  it("names the individual's dataset once its taxonomy has two", async () => {
    server.use(
      http.get("*/api/datasets", () =>
        HttpResponse.json([
          dataset,
          createDataset({
            id: "ds-2",
            taxonomy_id: "tax-1",
            identifier: "sample",
            title: "Sample",
          }),
        ]),
      ),
    );
    render(<IndividualPage id="ind-1" />);

    expect(await screen.findByTestId("individual-dataset")).toHaveTextContent("Default · default");
  });

  it("leaves the dataset implied while its taxonomy has one", async () => {
    render(<IndividualPage id="ind-1" />);

    expect(await screen.findByRole("heading", { name: "LLM Provider Router" })).toBeInTheDocument();
    await screen.findByTestId("entity-identity");
    expect(screen.queryByTestId("individual-dataset")).not.toBeInTheDocument();
  });
});

describe("IndividualPage sources", () => {
  const passage = (id: string, page: number, quote: string, proposalId: string) => ({
    id,
    entity_id: "ind-1",
    entity_kind: "individual",
    source_id: "src-1",
    proposal_id: proposalId,
    op_seq: 1,
    page,
    start: 8412,
    end: 8447,
    quote,
    created_at: "2026-11-10T12:00:00Z",
  });

  it("lists each source passage with its source, page, quote and proposal", async () => {
    server.use(
      http.get("*/api/individuals/:id/sources", () =>
        HttpResponse.json([
          passage("es-1", 5, "WRF555SDFZ French door refrigerator", "4f2c91d0-1111"),
          passage("es-2", 54, "Accessories for your WRF555SDFZ", "91b7e044-2222"),
        ]),
      ),
      http.get("*/api/sources/:id", () =>
        HttpResponse.json({
          id: "src-1",
          kind: "pdf",
          title: "Whirlpool use and care guide",
          page_starts: [],
          headings: [],
          status: "ready",
          removed_at: null,
        }),
      ),
    );
    render(<IndividualPage id="ind-1" />);

    const panel = await screen.findByTestId("individual-sources-panel");
    expect(await within(panel).findByTestId("entity-sources-summary")).toHaveTextContent(
      "2 passages in 1 source",
    );
    const first = within(panel).getByTestId("entity-source-row-es-1");
    expect(first).toHaveTextContent("WRF555SDFZ French door refrigerator");
    expect(first).toHaveTextContent("p. 5");
    // The source's title is text until the Sources page lands: the only link is the proposal.
    await waitFor(() =>
      expect(within(first).getByTestId("entity-source-title-es-1")).toHaveTextContent(
        "Whirlpool use and care guide",
      ),
    );
    expect(within(first).getAllByRole("link")).toHaveLength(1);
    expect(within(first).getByTestId("entity-source-proposal-es-1")).toHaveAttribute(
      "href",
      "/app/proposals/4f2c91d0-1111",
    );
    expect(within(panel).getByRole("list", { name: "Source passages" })).toBeInTheDocument();
  });

  it("says when nothing was applied from a source", async () => {
    render(<IndividualPage id="ind-1" />);

    expect(await screen.findByTestId("entity-sources-empty")).toHaveTextContent(
      "No source passages.",
    );
  });
});
