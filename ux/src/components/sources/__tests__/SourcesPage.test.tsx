import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import type { ReactNode } from "react";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createDataset,
  createListTaxonomies,
  createTaxonomy,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import type { LastExtractionRun, Source } from "@/api/services/sources";
import { SourcesPage } from "../SourcesPage";
import { createLastExtraction, createLastExtractionRun, createSource } from "./fixtures";

const mockNavigate = vi.hoisted(() => vi.fn());
const { toastSpy } = vi.hoisted(() => ({ toastSpy: vi.fn() }));
vi.mock("@/components/ui/Toast", () => ({
  ToastProvider: ({ children }: { children: ReactNode }) => children,
  useToasts: () => ({ toast: toastSpy, toasts: [], dismiss: vi.fn() }),
}));
let mockSearch: { dataset?: string } = {};
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => mockNavigate, useSearch: () => mockSearch };
});

const house = createTaxonomy({ id: "tax-house", identifier: "house", title: "House" });
const home = createDataset({ id: "ds-home", taxonomy_id: "tax-house", identifier: "home" });
const cabin = createDataset({ id: "ds-cabin", taxonomy_id: "tax-house", identifier: "cabin" });

const manual = createSource();
const page = createSource({
  id: "src-web",
  kind: "web",
  title: "How to replace a furnace filter",
  origin: "https://energystar.gov/furnace-filter",
  pages: 1,
  chars: 9000,
});
const scanned = createSource({
  id: "src-scan",
  title: "Water heater installation guide",
  status: "failed",
  failure: "no_text",
  failure_detail: "The PDF has no text layer",
  chars: 0,
});

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  mockNavigate.mockClear();
  toastSpy.mockClear();
  mockSearch = {};
});
afterAll(() => server.close());

interface ServeOptions {
  sources?: Source[] | (() => Source[]);
  datasets?: ReturnType<typeof createDataset>[];
}

function serve({ sources = [manual, page, scanned], datasets = [home] }: ServeOptions = {}) {
  const listRequests: URL[] = [];
  const posts: Request[] = [];
  const deletes: string[] = [];
  server.use(
    http.get("*/api/taxonomies", () => HttpResponse.json(createListTaxonomies([house]))),
    http.get("*/api/datasets", () => HttpResponse.json(datasets)),
    http.get("*/api/sources", ({ request }) => {
      listRequests.push(new URL(request.url));
      const items = typeof sources === "function" ? sources() : sources;
      return HttpResponse.json({ items, total: items.length, limit: 50, offset: 0 });
    }),
    http.post("*/api/sources", async ({ request }) => {
      posts.push(request.clone());
      return HttpResponse.json(createSource({ id: "src-new", title: "New source" }), {
        status: 201,
      });
    }),
    http.delete("*/api/sources/:id", ({ params }) => {
      deletes.push(params.id as string);
      return HttpResponse.json(manual);
    }),
  );
  return { listRequests, posts, deletes };
}

const table = () => within(screen.getByTestId("sources-table"));

describe("SourcesPage", () => {
  it("lists each source with its detail, kind and status", async () => {
    serve();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);

    const row = await screen.findByTestId("source-row-src-1");
    expect(row).toHaveTextContent("Whirlpool refrigerator: use and care guide");
    expect(row).toHaveTextContent("wrf555sdfz-use-care.pdf · 4 pages · 20k chars");
    expect(screen.getByTestId("source-row-src-web")).toHaveTextContent(
      "energystar.gov/furnace-filter · 9k chars",
    );
    expect(table().getAllByText("pdf").length).toBe(2);
    expect(table().getByText("web")).toHaveClass("chip--id-tag");

    const ready = screen.getByTestId("source-status-src-1");
    expect(within(ready).getByText("ready")).toHaveClass("chip--emerald");
    const failed = screen.getByTestId("source-status-src-scan");
    expect(within(failed).getByText("failed")).toHaveClass("chip--rose");
    expect(failed).toHaveTextContent("No text layer (scanned?)");
    expect(failed).toHaveAttribute("title", "The PDF has no text layer");

    expect(screen.getByTestId("sources-count")).toHaveTextContent("3 sources");
    expect(screen.getByTestId("source-last-extraction-src-1")).toHaveTextContent(
      "Not extracted yet",
    );
    // A failed source can't be extracted, only removed.
    expect(screen.getByTestId("source-extract-src-1")).toHaveTextContent("Extract");
    expect(screen.queryByTestId("source-extract-src-scan")).not.toBeInTheDocument();
    expect(screen.getByTestId("source-remove-src-scan")).toHaveAccessibleName(
      "Remove Water heater installation guide",
    );
  });

  it("filters by dataset when the taxonomy has several", async () => {
    const { listRequests } = serve({ datasets: [home, cabin] });
    mockSearch = { dataset: "ds-cabin" };
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);

    const filter = await screen.findByTestId("sources-dataset-filter");
    expect(filter).toHaveAccessibleName("Dataset");
    const cabinOption = within(filter).getByRole("radio", { name: "cabin" });
    expect(cabinOption).toHaveAttribute("aria-checked", "true");
    await waitFor(() =>
      expect(listRequests.some((u) => u.searchParams.get("dataset") === "ds-cabin")).toBe(true),
    );
    expect(listRequests.at(-1)!.searchParams.get("taxonomy_id")).toBe("tax-house");
    expect(screen.getByTestId("sources-page")).toHaveTextContent("DATA · house · dataset cabin");

    await user.click(within(filter).getByRole("radio", { name: "All datasets" }));
    expect(mockNavigate).toHaveBeenCalledWith(expect.objectContaining({ to: "." }));
  });

  it("hides the dataset filter when the taxonomy has one dataset", async () => {
    serve();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);
    await screen.findByTestId("source-row-src-1");
    expect(screen.queryByTestId("sources-dataset-filter")).not.toBeInTheDocument();
  });

  it("re-reads the list while a web page is fetching, until it is ready", async () => {
    let calls = 0;
    const fetching = { ...page, status: "fetching" as const };
    serve({ sources: () => (++calls === 1 ? [fetching] : [page]) });
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);

    const status = await screen.findByTestId("source-status-src-web");
    expect(within(status).getByText("fetching")).toHaveClass("chip--cyan");
    expect(status).toHaveTextContent("Reading the page");
    await waitFor(
      () =>
        expect(
          within(screen.getByTestId("source-status-src-web")).getByText("ready"),
        ).toBeInTheDocument(),
      { timeout: 4000 },
    );
    expect(screen.getByTestId("source-status-src-web")).not.toHaveTextContent("Reading the page");
  });

  it("fetches a web page, with validation that clears as the address is typed", async () => {
    const { posts } = serve();
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);
    await screen.findByTestId("source-row-src-1");

    const mode = screen.getByTestId("add-source-mode");
    expect(mode).toHaveAccessibleName("Source type");
    await user.click(within(mode).getByRole("radio", { name: "Web page" }));

    await user.click(screen.getByTestId("add-source-fetch-button"));
    expect(screen.getByText("Enter the page's address.")).toBeInTheDocument();
    const input = screen.getByTestId("add-source-url-input");
    expect(input).toHaveAttribute("aria-invalid", "true");

    await user.type(input, "energystar.gov");
    expect(screen.queryByText("Enter the page's address.")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("add-source-fetch-button"));
    expect(screen.getByText("Enter an http or https address.")).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "https://www.lg.com/washer-cleaning");
    expect(screen.queryByText("Enter an http or https address.")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("add-source-fetch-button"));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(await posts[0].json()).toEqual({
      taxonomy_id: "tax-house",
      dataset: "ds-home",
      url: "https://www.lg.com/washer-cleaning",
    });
    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("adds pasted text with a title, and requires both", async () => {
    const { posts } = serve();
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);
    await screen.findByTestId("source-row-src-1");

    await user.click(
      within(screen.getByTestId("add-source-mode")).getByRole("radio", { name: "Text" }),
    );
    await user.click(screen.getByTestId("add-source-submit"));
    expect(screen.getByText("Enter a title.")).toBeInTheDocument();
    expect(screen.getByText("Paste the text.")).toBeInTheDocument();

    await user.type(screen.getByTestId("add-source-title-input"), "Water heater notes");
    expect(screen.queryByText("Enter a title.")).not.toBeInTheDocument();
    await user.type(screen.getByTestId("add-source-text-input"), "Flush the tank yearly.");
    expect(screen.queryByText("Paste the text.")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("add-source-submit"));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(await posts[0].json()).toEqual({
      taxonomy_id: "tax-house",
      dataset: "ds-home",
      title: "Water heater notes",
      text: "Flush the tank yearly.",
    });
    await waitFor(() =>
      expect(toastSpy).toHaveBeenCalledWith("success", "Added “New source”", undefined),
    );
  });

  it("uploads a chosen file as multipart", async () => {
    const { posts } = serve();
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);
    await screen.findByTestId("source-row-src-1");

    const dropzone = screen.getByTestId("add-source-dropzone");
    expect(dropzone).toHaveClass("add-source__drop");
    expect(dropzone).toHaveTextContent("Drop a file here, or choose one");
    const file = new File(["# Manual"], "manual.md", { type: "text/markdown" });
    await user.upload(screen.getByTestId("add-source-file-input"), file);

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].headers.get("content-type")).toMatch(/^multipart\/form-data/);
    const form = await posts[0].formData();
    expect(form.get("taxonomy_id")).toBe("tax-house");
    expect(form.get("dataset")).toBe("ds-home");
    expect(await (form.get("file") as Blob).text()).toBe("# Manual");
  });

  it("asks which dataset a new source goes to when all datasets are shown", async () => {
    const { posts } = serve({ datasets: [home, cabin] });
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);
    await screen.findByTestId("source-row-src-1");

    const choice = screen.getByTestId("add-source-dataset");
    expect(choice).toHaveAccessibleName("Add to dataset");
    await user.click(within(choice).getByRole("radio", { name: "cabin" }));
    await user.click(
      within(screen.getByTestId("add-source-mode")).getByRole("radio", { name: "Web page" }),
    );
    await user.type(screen.getByTestId("add-source-url-input"), "https://a.org/x");
    await user.click(screen.getByTestId("add-source-fetch-button"));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(await posts[0].json()).toMatchObject({ dataset: "ds-cabin" });
  });

  it("opens the extract page for a ready source", async () => {
    serve();
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);

    const extract = await screen.findByTestId("source-extract-src-1");
    expect(extract).toHaveAccessibleName("Extract Whirlpool refrigerator: use and care guide");
    await user.click(extract);
    expect(mockNavigate).toHaveBeenCalledWith(
      expect.objectContaining({
        to: "/app/data/sources/$sourceId/extract",
        params: { sourceId: "src-1" },
      }),
    );
  });

  it("shows a running extraction's progress and follows both its runs", async () => {
    const running = createSource({
      last_extraction: createLastExtraction([
        createLastExtractionRun({ items_done: 1, items_total: 3 }),
        createLastExtractionRun({ run_id: "run-schema", pipeline: "schema_extraction" }),
      ]),
    });
    serve({ sources: [running] });
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);

    const cell = await screen.findByTestId("source-last-extraction-src-1");
    expect(cell).toHaveTextContent("Extracting…");
    expect(cell).toHaveTextContent("chunk 2 of 3");
    expect(screen.getByTestId("source-extract-src-1")).toHaveTextContent("Extract again");

    await user.click(screen.getByTestId("source-follow-run-src-1"));
    const call = mockNavigate.mock.calls.at(-1)![0];
    expect(call.to).toBe("/app/data/sources/$sourceId/extract");
    expect(call.params).toEqual({ sourceId: "src-1" });
    expect(call.search({})).toEqual({ run: "run-1234abcd", schemaRun: "run-schema" });
  });

  it("re-reads the list while an extraction runs, and stops once it finishes", async () => {
    let calls = 0;
    const withRun = (status: LastExtractionRun["status"]) =>
      createSource({
        last_extraction: createLastExtraction([
          createLastExtractionRun({
            status,
            items_done: 3,
            proposal_id: status === "completed" ? "prop-1" : null,
            operations: status === "completed" ? 31 : null,
          }),
        ]),
      });
    const { listRequests } = serve({
      sources: () => [withRun(++calls === 1 ? "running" : "completed")],
    });
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);

    expect(await screen.findByTestId("source-follow-run-src-1")).toBeInTheDocument();
    expect(
      await screen.findByTestId("source-open-proposal-src-1", {}, { timeout: 4000 }),
    ).toBeInTheDocument();
    const settled = listRequests.length;
    await new Promise((resolve) => setTimeout(resolve, 2500));
    expect(listRequests.length).toBe(settled);
  });

  it("links a finished extraction to its proposals", async () => {
    const done = createSource({
      last_extraction: createLastExtraction([
        createLastExtractionRun({
          status: "completed",
          items_done: 3,
          proposal_id: "prop-1",
          operations: 31,
        }),
        createLastExtractionRun({
          run_id: "run-schema",
          pipeline: "schema_extraction",
          status: "completed",
          proposal_id: "prop-schema",
          operations: 4,
        }),
      ]),
    });
    serve({ sources: [done] });
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);

    const link = await screen.findByTestId("source-open-proposal-src-1");
    expect(link).toHaveTextContent("Open proposal");
    expect(screen.getByTestId("source-last-extraction-src-1")).toHaveTextContent("31 ops · 1h");
    await user.click(link);
    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/app/proposals/$proposalId",
      params: { proposalId: "prop-1" },
    });
    await user.click(screen.getByTestId("source-open-schema-proposal-src-1"));
    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/app/proposals/$proposalId",
      params: { proposalId: "prop-schema" },
    });
  });

  it.each([
    ["interrupted", "Stopped when the app closed"],
    ["cancelled", "Run cancelled"],
    ["failed", "Run failed"],
  ] as const)(
    "says a %s extraction ended without a proposal, and doesn't poll",
    async (status, text) => {
      const ended = createSource({
        last_extraction: createLastExtraction([createLastExtractionRun({ status })]),
      });
      const { listRequests } = serve({ sources: [ended] });
      render(<SourcesPage onTaxonomyChange={vi.fn()} />);

      expect(await screen.findByTestId("source-follow-run-src-1")).toHaveTextContent(text);
      expect(screen.getByTestId("source-extract-src-1")).toHaveTextContent("Extract again");
      await new Promise((resolve) => setTimeout(resolve, 2500));
      expect(listRequests).toHaveLength(1);
    },
  );

  it("removes a source after confirming", async () => {
    const { deletes } = serve();
    const user = userEvent.setup();
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);

    await user.click(await screen.findByTestId("source-remove-src-1"));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Entities already applied from it keep their provenance.");
    await user.click(within(dialog).getByRole("button", { name: "Remove" }));

    await waitFor(() => expect(deletes).toEqual(["src-1"]));
    await waitFor(() =>
      expect(toastSpy).toHaveBeenCalledWith(
        "success",
        "Removed “Whirlpool refrigerator: use and care guide”",
      ),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an empty state without sources", async () => {
    serve({ sources: [] });
    render(<SourcesPage onTaxonomyChange={vi.fn()} />);
    expect(await table().findByText("No sources yet")).toBeInTheDocument();
    expect(screen.getByTestId("sources-count")).toHaveTextContent("0 sources");
  });
});
