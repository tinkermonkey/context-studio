import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { ASK_ABOUT_EVENT } from "@/components/entity/EntityPageParts";
import { useBreadcrumbStore } from "@/stores/breadcrumbs";
import { useNavigatorStore } from "@/stores/navigator";
import { TaxonomyPage } from "../taxonomies_.$id";
import { SchemePage } from "../schemes_.$id";
import { ClassPage } from "../classes_.$id";

const server = setupServer(...entityPageHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useNavigatorStore.setState({ expandedIds: new Set(), mode: "schema" });
});
afterAll(() => server.close());

describe("TaxonomyPage", () => {
  it("renders the header, counts and schemes table", async () => {
    render(<TaxonomyPage id="tax-1" />);

    expect(
      await screen.findByRole("heading", { name: "Documentation Robotics" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("taxonomy-page")).toHaveClass("entity-page");
    expect(screen.getByTestId("entity-eyebrow")).toHaveClass("entity-eyebrow");
    expect(screen.getByTestId("entity-status")).toHaveTextContent("draft");
    expect(screen.getByTestId("entity-version")).toHaveTextContent("v1");

    const link = await screen.findByTestId("taxonomy-scheme-link-scheme-1");
    expect(link).toHaveAttribute("href", "/app/schema/schemes/scheme-1");
    expect(link).toHaveClass("entity-link");
    const schemesPanel = screen.getByTestId("taxonomy-schemes-panel");
    expect(await within(schemesPanel).findByText("Relationship types")).toBeInTheDocument();
  });

  it("has the navigator and identity landmarks", async () => {
    render(<TaxonomyPage id="tax-1" />);
    await screen.findByRole("heading", { name: "Documentation Robotics" });

    expect(screen.getByRole("navigation", { name: "Navigator" })).toHaveAttribute(
      "data-testid",
      "entity-navigator",
    );
    expect(screen.getByRole("complementary", { name: "Identity" })).toHaveAttribute(
      "data-testid",
      "entity-identity",
    );
    // The tree opens to the taxonomy and highlights it.
    expect(await screen.findByTestId("hierarchy-node-scheme-1")).toBeInTheDocument();
    expect(screen.getByTestId("hierarchy-node-tax-1")).toHaveClass("hierarchy-row--selected");
  });

  it("supplies hierarchy breadcrumbs to the shell", async () => {
    render(<TaxonomyPage id="tax-1" />);
    await screen.findByRole("heading", { name: "Documentation Robotics" });

    expect(useBreadcrumbStore.getState()).toMatchObject({
      pathname: "/app/schema/taxonomies/tax-1",
      crumbs: [
        { label: "Schema", to: "/app/schema/taxonomies" },
        { label: "Documentation Robotics" },
      ],
    });
  });

  it("shows the summary and renders the vision as markdown", async () => {
    render(<TaxonomyPage id="tax-1" />);

    const summary = await screen.findByTestId("taxonomy-summary-text");
    expect(summary).toHaveClass("entity-definition");
    expect(summary).toHaveTextContent("Architecture ontology");
    // The header no longer repeats the summary.
    expect(screen.getAllByText("Architecture ontology")).toHaveLength(1);
    const vision = screen.getByTestId("taxonomy-vision-text");
    expect(vision).toHaveClass("intent-markdown");
    expect(within(vision).getByRole("heading", { name: "Design charter" })).toBeInTheDocument();
    expect(
      within(vision).getByText("An element is a named architectural fact."),
    ).toBeInTheDocument();
  });

  it("edits the vision in place", async () => {
    let saved: unknown;
    server.use(
      http.put("*/api/taxonomies/:id", async ({ request }) => {
        saved = await request.json();
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    render(<TaxonomyPage id="tax-1" />);
    await screen.findByTestId("taxonomy-vision-text");

    await user.click(screen.getByTestId("taxonomy-vision-edit"));
    const input = screen.getByTestId("taxonomy-vision-input");
    expect(input).toHaveAttribute("aria-label", "Vision");
    await user.clear(input);
    await user.type(input, "# Revised");
    await user.click(screen.getByTestId("taxonomy-vision-save"));

    await vi.waitFor(() => expect(saved).toEqual({ vision: "# Revised" }));
    expect(screen.queryByTestId("taxonomy-vision-input")).not.toBeInTheDocument();
  });

  it("shows not found for an unknown taxonomy", async () => {
    render(<TaxonomyPage id="missing" />);
    expect(await screen.findByText("Taxonomy not found")).toBeInTheDocument();
  });

  it("dispatches an ask-about event for chat", async () => {
    const listener = vi.fn();
    window.addEventListener(ASK_ABOUT_EVENT, listener);
    const user = userEvent.setup();
    render(<TaxonomyPage id="tax-1" />);
    await screen.findByRole("heading", { name: "Documentation Robotics" });

    await user.click(screen.getByTestId("entity-ask-about"));

    expect(listener).toHaveBeenCalledTimes(1);
    expect((listener.mock.calls[0][0] as CustomEvent).detail).toEqual({
      kind: "taxonomy",
      id: "tax-1",
      title: "Documentation Robotics",
    });
    window.removeEventListener(ASK_ABOUT_EVENT, listener);
  });
});

describe("SchemePage", () => {
  it("renders the classes table with definitions and counts", async () => {
    render(<SchemePage id="scheme-1" />);

    expect(await screen.findByRole("heading", { name: "Application Layer" })).toBeInTheDocument();
    const parent = await screen.findByTestId("entity-parent-link");
    expect(parent).toHaveAttribute("href", "/app/schema/taxonomies/tax-1");

    const classLink = await screen.findByTestId("scheme-class-link-class-1");
    expect(classLink).toHaveAttribute("href", "/app/schema/classes/class-1");
    const panel = screen.getByTestId("scheme-classes-panel");
    expect(within(panel).getByText("Modular, deployable part of a system")).toBeInTheDocument();
    expect(screen.getByTestId("entity-create")).toHaveTextContent("New class");
  });

  it("shows the scope note and edits it in place", async () => {
    let saved: unknown;
    server.use(
      http.put("*/api/schemes/:id", async ({ request }) => {
        saved = await request.json();
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    render(<SchemePage id="scheme-1" />);

    const note = await screen.findByTestId("scheme-scope-note-text");
    expect(note).toHaveTextContent("Application layer");
    await user.click(screen.getByTestId("scheme-scope-note-edit"));
    const input = screen.getByTestId("scheme-scope-note-input");
    await user.clear(input);
    await user.type(input, "Application services and components");
    await user.click(screen.getByTestId("scheme-scope-note-save"));

    await vi.waitFor(() =>
      expect(saved).toEqual({ description: "Application services and components" }),
    );
  });
});

describe("ClassPage", () => {
  it("renders the definition, individuals and relationship types", async () => {
    render(<ClassPage id="class-1" />);

    expect(
      await screen.findByRole("heading", { name: "ApplicationComponent" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("class-definition-text")).toHaveClass("entity-definition");
    expect(screen.getByTestId("class-definition-text")).toHaveTextContent(
      "Modular, deployable part of a system",
    );

    const individualLink = await screen.findByTestId("class-individual-link-ind-1");
    expect(individualLink).toHaveAttribute("href", "/app/data/individuals/ind-1");

    const types = screen.getByTestId("class-relationship-types-panel");
    expect(await within(types).findByText("realizes")).toHaveClass("entity-predicate");
    const target = await within(types).findByRole("link", { name: "ApplicationService" });
    expect(target).toHaveAttribute("href", "/app/schema/classes/class-2");
    expect(await within(types).findByText("Application Layer")).toBeInTheDocument();
    expect(screen.getByText("documentation_robotics ·", { exact: false })).toBeInTheDocument();
  });

  it("edits the definition inline", async () => {
    let saved: unknown;
    server.use(
      http.put("*/api/classes/:id", async ({ request }) => {
        saved = await request.json();
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    render(<ClassPage id="class-1" />);
    await screen.findByRole("heading", { name: "ApplicationComponent" });

    await user.click(screen.getByTestId("class-definition-edit"));
    const input = screen.getByTestId("class-definition-input");
    await user.clear(input);
    await user.type(input, "A deployable unit");
    await user.click(screen.getByTestId("class-definition-save"));

    await vi.waitFor(() => expect(saved).toEqual({ description: "A deployable unit" }));
    expect(screen.queryByTestId("class-definition-input")).not.toBeInTheDocument();
  });

  it("shows not found for an unknown class", async () => {
    render(<ClassPage id="missing" />);
    expect(await screen.findByText("Class not found")).toBeInTheDocument();
  });
});
