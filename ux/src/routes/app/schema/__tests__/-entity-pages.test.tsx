import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { dataset, entityPageHandlers, router, taxonomy } from "@/test/entityPageHandlers";
import {
  createDataset,
  createIndividual,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { ASK_ABOUT_EVENT } from "@/components/entity/EntityPageParts";
import { ToastViewport, useToasts } from "@/components/ui/Toast";
import { useBreadcrumbStore } from "@/stores/breadcrumbs";
import { useNavigatorStore } from "@/stores/navigator";
import { TaxonomyPage } from "../taxonomies_.$id";
import { SchemePage } from "../schemes_.$id";
import { ClassPage } from "../classes_.$id";

const server = setupServer(...entityPageHandlers);

// The URL's search params (the `dataset` parameter), set per test.
let mockSearch: { dataset?: string } = {};
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => vi.fn(), useSearch: () => mockSearch };
});

/** The page plus the toast viewport, which outlives the page when `showPage` turns false. */
function TaxonomyPageWithToasts({ id, showPage = true }: { id: string; showPage?: boolean }) {
  const { toasts, dismiss } = useToasts();
  return (
    <>
      {showPage && <TaxonomyPage id={id} />}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </>
  );
}

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.readAsText(blob);
  });
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  mockSearch = {};
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

  describe("Mirrored DR spec", () => {
    it("shows the source revision a mirrored taxonomy follows", async () => {
      server.use(
        http.get("*/api/taxonomies/:id", () =>
          HttpResponse.json({
            ...taxonomy,
            mirrored: true,
            source_revision: {
              repo: "git@github.com:x/dr.git",
              commit: "b016a07412",
              spec_version: "0.11.0",
            },
          }),
        ),
      );
      render(<TaxonomyPage id="tax-1" />);

      const mirrors = await screen.findByTestId("taxonomy-mirrors");
      expect(mirrors).toHaveTextContent("0.11.0 · b016a074");
      expect(mirrors).toHaveClass("mono");
      expect(mirrors).toHaveAttribute("title", "git@github.com:x/dr.git");
    });

    it("opens the drift check from the DR taxonomy's header", async () => {
      const user = userEvent.setup();
      render(<TaxonomyPage id="tax-1" />);

      const button = await screen.findByTestId("taxonomy-check-drift");
      expect(button).toBe(screen.getByRole("button", { name: /Check drift/ }));
      expect(button).toHaveClass("btn", "btn--ghost");
      expect(screen.queryByTestId("taxonomy-mirrors")).not.toBeInTheDocument();

      await user.click(button);

      expect(screen.getByTestId("dr-drift-dialog")).toBeInTheDocument();
      expect(screen.getByTestId("dr-drift-spec-dir")).toBeInTheDocument();
    });

    it("offers no drift check on another taxonomy", async () => {
      server.use(
        http.get("*/api/taxonomies/:id", () =>
          HttpResponse.json({ ...taxonomy, identifier: "house" }),
        ),
      );
      render(<TaxonomyPage id="tax-1" />);

      expect(await screen.findByTestId("taxonomy-export-bundle")).toBeInTheDocument();
      expect(screen.queryByTestId("taxonomy-check-drift")).not.toBeInTheDocument();
    });
  });

  describe("Export bundle", () => {
    const bundle = {
      format: "context-studio-bundle",
      version: 0,
      source: "dr_spec",
      taxonomy: { identifier: "dr_spec", title: "Documentation Robotics" },
      classes: [],
    };
    let downloads: { filename: string; href: string }[];
    let blobs: Blob[];

    beforeEach(() => {
      downloads = [];
      blobs = [];
      vi.spyOn(URL, "createObjectURL").mockImplementation((blob) => {
        blobs.push(blob as Blob);
        return "blob:bundle";
      });
      vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
      vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
        this: HTMLAnchorElement,
      ) {
        downloads.push({ filename: this.download, href: this.href });
      });
    });
    afterEach(() => vi.restoreAllMocks());

    it("is a labelled header button", async () => {
      render(<TaxonomyPage id="tax-1" />);

      const button = await screen.findByTestId("taxonomy-export-bundle");
      expect(button).toBe(screen.getByRole("button", { name: /Export bundle/ }));
      expect(button).toHaveClass("btn", "btn--ghost");
      expect(button).toHaveAttribute("title", "Download dr_spec.bundle.json");
      expect(button).toHaveAttribute("aria-busy", "false");
      expect(button).toBeEnabled();
    });

    it("downloads <identifier>.bundle.json with the exported bundle", async () => {
      let requested: string | undefined;
      server.use(
        http.get("*/api/v1/interchange/bundles/:id", ({ params }) => {
          requested = params.id as string;
          return HttpResponse.json(bundle);
        }),
      );
      const user = userEvent.setup();
      render(<TaxonomyPageWithToasts id="tax-1" />);

      await user.click(await screen.findByTestId("taxonomy-export-bundle"));

      await vi.waitFor(() =>
        expect(downloads).toEqual([{ filename: "dr_spec.bundle.json", href: "blob:bundle" }]),
      );
      expect(requested).toBe("tax-1");
      expect(blobs[0].type).toBe("application/json");
      expect(await readBlob(blobs[0])).toBe(JSON.stringify(bundle, null, 2) + "\n");
      // Revoked on a later tick, after the browser has taken the download.
      await vi.waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:bundle"));
      expect(screen.queryByText("Bundle export failed")).not.toBeInTheDocument();
    });

    it("toasts the server's reason when the export is refused", async () => {
      server.use(
        http.get("*/api/v1/interchange/bundles/:id", () =>
          HttpResponse.json(
            { detail: "these have no stored identifier: Class 'Path'" },
            { status: 409 },
          ),
        ),
      );
      const user = userEvent.setup();
      render(<TaxonomyPageWithToasts id="tax-1" />);

      await user.click(await screen.findByTestId("taxonomy-export-bundle"));

      expect(await screen.findByText("Bundle export failed")).toBeInTheDocument();
      expect(screen.getAllByText("Bundle export failed")).toHaveLength(1);
      expect(screen.getByText("these have no stored identifier: Class 'Path'")).toBeInTheDocument();
      expect(downloads).toEqual([]);
      expect(screen.getByTestId("taxonomy-export-bundle")).toBeEnabled();
    });

    it("is busy and disabled while the export is pending", async () => {
      let release!: () => void;
      const held = new Promise<void>((resolve) => (release = resolve));
      server.use(
        http.get("*/api/v1/interchange/bundles/:id", async () => {
          await held;
          return HttpResponse.json(bundle);
        }),
      );
      const user = userEvent.setup();
      render(<TaxonomyPageWithToasts id="tax-1" />);
      const button = await screen.findByTestId("taxonomy-export-bundle");

      await user.click(button);

      await vi.waitFor(() => expect(button).toHaveAttribute("aria-busy", "true"));
      expect(button).toBeDisabled();
      expect(downloads).toEqual([]);
      release();
      await vi.waitFor(() => expect(button).toHaveAttribute("aria-busy", "false"));
      expect(button).toBeEnabled();
      expect(downloads).toHaveLength(1);
    });

    it("still toasts a failure that lands after the page has unmounted", async () => {
      let release!: () => void;
      const held = new Promise<void>((resolve) => (release = resolve));
      server.use(
        http.get("*/api/v1/interchange/bundles/:id", async () => {
          await held;
          return HttpResponse.json({ detail: "no stored identifier" }, { status: 409 });
        }),
      );
      const user = userEvent.setup();
      const { rerender } = render(<TaxonomyPageWithToasts id="tax-1" />);
      const button = await screen.findByTestId("taxonomy-export-bundle");
      await user.click(button);
      await vi.waitFor(() => expect(button).toHaveAttribute("aria-busy", "true"));

      rerender(<TaxonomyPageWithToasts id="tax-1" showPage={false} />);
      expect(screen.queryByTestId("taxonomy-page")).not.toBeInTheDocument();
      release();

      expect(await screen.findByText("Bundle export failed")).toBeInTheDocument();
      expect(screen.getByText("no stored identifier")).toBeInTheDocument();
    });
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

describe("Datasets on entity pages", () => {
  const sample = createDataset({
    id: "ds-2",
    taxonomy_id: "tax-1",
    identifier: "sample",
    title: "Sample",
  });
  const sampleRouter = createIndividual({
    id: "ind-9",
    title: "Sample Router",
    class_ids: ["class-1"],
    dataset_id: "ds-2",
  });

  function twoDatasets() {
    const requests: URL[] = [];
    server.use(
      http.get("*/api/datasets", () => HttpResponse.json([dataset, sample])),
      http.get("*/api/individuals", ({ request }) => {
        const url = new URL(request.url);
        requests.push(url);
        const datasetId = url.searchParams.get("dataset_id");
        const items = datasetId === "ds-2" ? [sampleRouter] : [router, sampleRouter];
        return HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });
      }),
      http.get("*/api/taxonomies/:id/scheme-counts", ({ request }) => {
        const url = new URL(request.url);
        requests.push(url);
        const scoped = url.searchParams.get("dataset_id") === "ds-2";
        return HttpResponse.json([
          {
            scheme_id: "scheme-1",
            class_count: 2,
            individual_count: scoped ? 4 : 9,
            property_definition_count: 1,
          },
        ]);
      }),
    );
    return requests;
  }

  it("the class page lists only the chosen dataset's individuals", async () => {
    mockSearch = { dataset: "ds-2" };
    const requests = twoDatasets();
    render(<ClassPage id="class-1" />);

    expect(await screen.findByTestId("class-individual-link-ind-9")).toBeInTheDocument();
    expect(screen.queryByTestId("class-individual-link-ind-1")).not.toBeInTheDocument();
    const classIndividuals = requests.filter((u) => u.searchParams.get("class_id") === "class-1");
    expect(classIndividuals.length).toBeGreaterThan(0);
    expect(classIndividuals.every((u) => u.searchParams.get("dataset_id") === "ds-2")).toBe(true);
  });

  it("the class page shows every dataset's individuals when none is chosen", async () => {
    twoDatasets();
    render(<ClassPage id="class-1" />);

    expect(await screen.findByTestId("class-individual-link-ind-1")).toBeInTheDocument();
    expect(screen.getByTestId("class-individual-link-ind-9")).toBeInTheDocument();
  });

  it("the taxonomy page counts the chosen dataset's individuals", async () => {
    mockSearch = { dataset: "ds-2" };
    const requests = twoDatasets();
    render(<TaxonomyPage id="tax-1" />);

    const stats = await screen.findByTestId("entity-stats");
    expect(await within(stats).findByText("4")).toBeInTheDocument();
    expect(within(stats).queryByText("9")).not.toBeInTheDocument();
    const counts = requests.filter((u) => u.pathname.endsWith("/scheme-counts"));
    expect(counts.some((u) => u.searchParams.get("dataset_id") === "ds-2")).toBe(true);
  });
});
