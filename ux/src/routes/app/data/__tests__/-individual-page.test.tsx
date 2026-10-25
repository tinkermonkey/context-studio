import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { useBreadcrumbStore } from "@/stores/breadcrumbs";
import { useNavigatorStore } from "@/stores/navigator";
import { IndividualPage } from "../individuals_.$id";

const server = setupServer(...entityPageHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useNavigatorStore.setState({ expandedIds: new Set() });
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

  it("highlights the individual's class in the navigator", async () => {
    render(<IndividualPage id="ind-1" />);

    await waitFor(() =>
      expect(screen.getByTestId("hierarchy-node-class-1")).toHaveClass("hierarchy-row--selected"),
    );
  });

  it("shows not found for an unknown individual", async () => {
    render(<IndividualPage id="missing" />);
    expect(await screen.findByText("Individual not found")).toBeInTheDocument();
  });
});
