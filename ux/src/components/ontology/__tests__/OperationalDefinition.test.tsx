/**
 * A class's operational definition in the class drawer (#1523): read-only in
 * view mode, edited in place in edit mode. Each change PUTs the class.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createClass,
  createListClasses,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import type { components } from "@/api/types";
import { useToasts } from "@/components/ui/Toast";
import { OperationalDefinitionEditor, OperationalDefinitionView } from "../OperationalDefinition";

type ClassUpdateRequest = components["schemas"]["ClassUpdateRequest"];

/** The toasts raised so far, as text (the app renders them outside the provider). */
function ToastProbe() {
  const { toasts } = useToasts();
  return (
    <ul data-testid="toast-probe">
      {toasts.map((t) => (
        <li key={t.id} data-type={t.type}>
          {t.title}
        </li>
      ))}
    </ul>
  );
}

const component = createClass({
  id: "class-1",
  concept_scheme_id: "scheme-1",
  identifier: "application_component",
  title: "ApplicationComponent",
});
const service = createClass({
  id: "class-2",
  concept_scheme_id: "scheme-1",
  identifier: "application_service",
  title: "ApplicationService",
});
const serviceInterface = createClass({
  id: "class-3",
  concept_scheme_id: "scheme-1",
  identifier: "application_interface",
  title: "ApplicationInterface",
});
const node = createClass({
  id: "class-9",
  concept_scheme_id: "scheme-tech",
  identifier: "node",
  title: "Application Node",
});
const CLASSES = [component, service, serviceInterface, node];

/** GET /api/classes over CLASSES, by its ids, q and concept_scheme_id filters. */
function listClasses(request: Request) {
  const url = new URL(request.url);
  const ids = url.searchParams.getAll("ids");
  const q = url.searchParams.get("q")?.toLowerCase();
  const schemeId = url.searchParams.get("concept_scheme_id");
  return HttpResponse.json(
    createListClasses(
      CLASSES.filter(
        (c) =>
          (!ids.length || ids.includes(c.id)) &&
          (!q || c.title.toLowerCase().includes(q)) &&
          (!schemeId || c.concept_scheme_id === schemeId),
      ),
    ),
  );
}

const server = setupServer(http.get("*/api/classes", ({ request }) => listClasses(request)));

/** A promise the test resolves when it wants a held request to answer. */
function gate() {
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  return { held, release };
}

/** Hold the id lookups that include `classId` until the returned release is called. */
function holdLookupOf(classId: string) {
  const { held, release } = gate();
  server.use(
    http.get("*/api/classes", async ({ request }) => {
      if (new URL(request.url).searchParams.getAll("ids").includes(classId)) await held;
      return listClasses(request);
    }),
  );
  return release;
}

/** Wait for the editor's last save to land: its controls are enabled again. */
async function saved() {
  await waitFor(() => expect(screen.getByTestId("class-evidence-signal-add")).not.toBeDisabled());
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** Record each PUT /api/classes/class-1 body. */
function capturePuts(status = 200) {
  const puts: ClassUpdateRequest[] = [];
  server.use(
    http.put("*/api/classes/class-1", async ({ request }) => {
      const body = (await request.json()) as ClassUpdateRequest;
      puts.push(body);
      return status === 200
        ? HttpResponse.json({ ...component, ...body })
        : HttpResponse.json({ detail: "distinguish_from names class-2 twice" }, { status });
    }),
  );
  return puts;
}

const defined = createClass({
  ...component,
  distinguish_from: [
    { class_id: "class-2", when: "it is the behaviour, not the deployable part" },
    { class_id: "class-gone", when: "it was retired" },
  ],
  evidence_signals: ["Has its own repository", "Is deployed on its own", "Owns a database"],
  standard_reference: "ArchiMate 3.2 §9.2",
});

describe("OperationalDefinitionView", () => {
  it("shows distinctions by class title, signals in order and the standard", async () => {
    render(<OperationalDefinitionView classData={defined} />);

    const entry = await screen.findByTestId("class-distinguish-entry-class-2");
    await waitFor(() => expect(entry).toHaveTextContent("ApplicationService"));
    expect(entry).toHaveTextContent("it is the behaviour, not the deployable part");
    expect(entry).not.toHaveTextContent("class-2");
    expect(screen.getByTestId("class-definition-view")).toHaveClass("class-definition");

    const signals = within(screen.getByTestId("class-evidence-signals-list")).getAllByRole(
      "listitem",
    );
    expect(signals.map((s) => s.textContent)).toEqual([
      "Has its own repository",
      "Is deployed on its own",
      "Owns a database",
    ]);
    expect(screen.getByTestId("class-evidence-signals-list").tagName).toBe("OL");
    expect(screen.getByTestId("class-standard-reference")).toHaveTextContent("ArchiMate 3.2 §9.2");
  });

  it("keeps an entry whose class no longer exists, by its id", async () => {
    render(<OperationalDefinitionView classData={defined} />);

    const gone = screen.getByTestId("class-distinguish-entry-class-gone");
    expect(gone).toHaveTextContent("class-gone");
    expect(gone).toHaveTextContent("it was retired");
    await waitFor(() => expect(gone).toHaveTextContent("(class not found)"));
    expect(gone.querySelector(".class-definition__class--missing")).not.toBeNull();
  });

  it("doesn't call a newly named class missing while its lookup loads", async () => {
    const release = holdLookupOf("class-3");
    const { rerender } = render(<OperationalDefinitionView classData={defined} />);
    const gone = screen.getByTestId("class-distinguish-entry-class-gone");
    await waitFor(() => expect(gone).toHaveTextContent("(class not found)"));

    // A refetch adds class-3: the previous lookup stands in while the new one loads.
    rerender(
      <OperationalDefinitionView
        classData={{
          ...defined,
          distinguish_from: [
            ...defined.distinguish_from!,
            { class_id: "class-3", when: "it is the access point" },
          ],
        }}
      />,
    );
    const added = screen.getByTestId("class-distinguish-entry-class-3");
    expect(added).toHaveTextContent("class-3");
    expect(added).not.toHaveTextContent("(class not found)");

    release();
    await waitFor(() => expect(added).toHaveTextContent("ApplicationInterface"));
    expect(added).not.toHaveTextContent("(class not found)");
    expect(gone).toHaveTextContent("(class not found)");
  });

  it("says when the class has no operational definition", () => {
    render(<OperationalDefinitionView classData={component} />);
    expect(screen.getByTestId("class-definition-empty")).toHaveTextContent(
      "No operational definition",
    );
    expect(screen.queryByTestId("class-definition-view")).not.toBeInTheDocument();
  });
});

describe("OperationalDefinitionEditor", () => {
  it("adds a distinction to a sibling class of the same domain", async () => {
    const user = userEvent.setup();
    const puts = capturePuts();
    render(<OperationalDefinitionEditor classData={component} />);

    expect(screen.getByTestId("class-definition-editor")).toHaveClass("class-definition");
    const picker = within(screen.getByTestId("class-distinguish-picker"));
    await user.type(picker.getByRole("combobox"), "Application");

    // Siblings in the domain only: not the class itself, not a class of another domain.
    expect(await picker.findByRole("option", { name: "ApplicationService" })).toBeInTheDocument();
    expect(picker.getByRole("option", { name: "ApplicationInterface" })).toBeInTheDocument();
    expect(picker.queryByRole("option", { name: "ApplicationComponent" })).not.toBeInTheDocument();
    expect(picker.queryByRole("option", { name: "Application Node" })).not.toBeInTheDocument();

    await user.click(picker.getByRole("option", { name: "ApplicationService" }));
    await user.type(screen.getByTestId("class-distinguish-new-when"), "it is the behaviour");
    await user.click(screen.getByTestId("class-distinguish-add"));

    await waitFor(() =>
      expect(puts).toEqual([
        { distinguish_from: [{ class_id: "class-2", when: "it is the behaviour" }] },
      ]),
    );
    const entry = await screen.findByTestId("class-distinguish-entry-class-2");
    expect(entry).toHaveTextContent("ApplicationService");
    expect(screen.getByTestId("class-distinguish-new-when")).toHaveValue("");
  });

  it("requires a class and a when, and clears each error as it is corrected", async () => {
    const user = userEvent.setup();
    const puts = capturePuts();
    render(<OperationalDefinitionEditor classData={component} />);

    await user.click(screen.getByTestId("class-distinguish-add"));
    expect(screen.getAllByRole("alert").map((a) => a.textContent)).toEqual([
      "Pick a class from this domain",
      "Say when to use that class instead",
    ]);
    const whenInput = screen.getByTestId("class-distinguish-new-when");
    expect(whenInput).toHaveAttribute("aria-invalid", "true");
    // The input names its error message.
    const describedBy = whenInput.getAttribute("aria-describedby")!;
    expect(document.getElementById(describedBy)).toHaveTextContent(
      "Say when to use that class instead",
    );

    await user.type(screen.getByTestId("class-distinguish-new-when"), "i");
    expect(screen.queryByText("Say when to use that class instead")).not.toBeInTheDocument();
    expect(whenInput).not.toHaveAttribute("aria-describedby");
    expect(screen.getByText("Pick a class from this domain")).toBeInTheDocument();

    await user.type(
      within(screen.getByTestId("class-distinguish-picker")).getByRole("combobox"),
      "S",
    );
    expect(screen.queryByText("Pick a class from this domain")).not.toBeInTheDocument();
    expect(puts).toEqual([]);
  });

  it("shows an unknown class by id and can remove it", async () => {
    const user = userEvent.setup();
    const puts = capturePuts();
    render(<OperationalDefinitionEditor classData={defined} />);

    const gone = screen.getByTestId("class-distinguish-entry-class-gone");
    await waitFor(() => expect(gone).toHaveTextContent("class-gone (class not found)"));
    await user.click(screen.getByRole("button", { name: "Remove class-gone" }));

    await waitFor(() =>
      expect(puts).toEqual([
        {
          distinguish_from: [
            { class_id: "class-2", when: "it is the behaviour, not the deployable part" },
          ],
        },
      ]),
    );
    expect(screen.queryByTestId("class-distinguish-entry-class-gone")).not.toBeInTheDocument();
  });

  it("edits a distinction's when on blur, and won't save it empty", async () => {
    const user = userEvent.setup();
    const puts = capturePuts();
    render(<OperationalDefinitionEditor classData={defined} />);

    const when = screen.getByTestId("class-distinguish-when-class-2");
    await user.clear(when);
    await user.tab();
    expect(screen.getByRole("alert")).toHaveTextContent("Say when to use that class instead");
    expect(puts).toEqual([]);

    await user.type(when, "it is exposed behaviour");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await user.tab();

    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].distinguish_from?.[0]).toEqual({
      class_id: "class-2",
      when: "it is exposed behaviour",
    });
    // The entry for the missing class goes back unchanged.
    expect(puts[0].distinguish_from?.[1]).toEqual({
      class_id: "class-gone",
      when: "it was retired",
    });
  });

  it("reorders, adds and removes evidence signals", async () => {
    const user = userEvent.setup();
    const puts = capturePuts();
    render(<OperationalDefinitionEditor classData={defined} />);

    expect(screen.getByTestId("class-evidence-signal-up-0")).toBeDisabled();
    expect(screen.getByTestId("class-evidence-signal-down-2")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Move signal 1 down" }));
    await waitFor(() =>
      expect(puts.at(-1)).toEqual({
        evidence_signals: ["Is deployed on its own", "Has its own repository", "Owns a database"],
      }),
    );
    expect(screen.getByTestId("class-evidence-signal-input-0")).toHaveValue(
      "Is deployed on its own",
    );
    await saved();

    await user.click(screen.getByRole("button", { name: "Remove signal 3" }));
    await waitFor(() =>
      expect(puts.at(-1)).toEqual({
        evidence_signals: ["Is deployed on its own", "Has its own repository"],
      }),
    );
    await saved();

    await user.click(screen.getByTestId("class-evidence-signal-add"));
    expect(screen.getByText("Type a signal first")).toBeInTheDocument();
    await user.type(screen.getByTestId("class-evidence-signal-new"), "Exposes an API{Enter}");
    expect(screen.queryByText("Type a signal first")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(puts.at(-1)).toEqual({
        evidence_signals: ["Is deployed on its own", "Has its own repository", "Exposes an API"],
      }),
    );
    expect(puts).toHaveLength(3);
  });

  it("names a new distinction by its pick, never as a missing class", async () => {
    const user = userEvent.setup();
    const puts = capturePuts();
    const release = holdLookupOf("class-3");
    render(<OperationalDefinitionEditor classData={defined} />);
    const gone = screen.getByTestId("class-distinguish-entry-class-gone");
    await waitFor(() => expect(gone).toHaveTextContent("(class not found)"));

    const picker = within(screen.getByTestId("class-distinguish-picker"));
    await user.type(picker.getByRole("combobox"), "Interface");
    await user.click(await picker.findByRole("option", { name: "ApplicationInterface" }));
    await user.type(screen.getByTestId("class-distinguish-new-when"), "it is the access point");
    await user.click(screen.getByTestId("class-distinguish-add"));

    const added = screen.getByTestId("class-distinguish-entry-class-3");
    expect(added).toHaveTextContent("ApplicationInterface");
    expect(added).not.toHaveTextContent("(class not found)");
    await waitFor(() => expect(puts).toHaveLength(1));
    await saved();
    expect(added).not.toHaveTextContent("(class not found)");
    release();
  });

  it("blocks a second change while the first save is in flight", async () => {
    const user = userEvent.setup();
    const puts: ClassUpdateRequest[] = [];
    const { held, release } = gate();
    server.use(
      http.put("*/api/classes/class-1", async ({ request }) => {
        const body = (await request.json()) as ClassUpdateRequest;
        puts.push(body);
        await held;
        return HttpResponse.json({ ...defined, ...body });
      }),
    );
    render(<OperationalDefinitionEditor classData={defined} />);

    await user.click(screen.getByRole("button", { name: "Move signal 1 down" }));
    await waitFor(() => expect(puts).toHaveLength(1));

    // Every control that saves waits for the save in flight.
    expect(screen.getByRole("button", { name: "Remove signal 2" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move signal 2 down" })).toBeDisabled();
    expect(screen.getByTestId("class-evidence-signal-add")).toBeDisabled();
    expect(screen.getByTestId("class-distinguish-add")).toBeDisabled();
    expect(screen.getByTestId("class-distinguish-remove-class-2")).toBeDisabled();
    expect(screen.getByTestId("class-evidence-signal-input-0")).toHaveAttribute("readonly");
    expect(screen.getByTestId("class-distinguish-when-class-2")).toHaveAttribute("readonly");

    await user.click(screen.getByRole("button", { name: "Remove signal 2" }));
    await user.type(screen.getByTestId("class-evidence-signal-new"), "Exposes an API{Enter}");
    expect(puts).toHaveLength(1);
    expect(
      within(screen.getByTestId("class-evidence-signals-list")).getAllByRole("listitem"),
    ).toHaveLength(3);

    release();
    await saved();
    expect(puts).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Remove signal 2" })).not.toBeDisabled();

    // Once it lands, the next change saves on top of it.
    await user.click(screen.getByRole("button", { name: "Remove signal 2" }));
    await waitFor(() =>
      expect(puts.at(-1)).toEqual({
        evidence_signals: ["Is deployed on its own", "Owns a database"],
      }),
    );
  });

  it("saves the standard reference", async () => {
    const user = userEvent.setup();
    const puts = capturePuts();
    render(<OperationalDefinitionEditor classData={component} />);

    await user.click(screen.getByTestId("class-drawer-standard-reference-field-view"));
    await user.type(
      screen.getByTestId("class-drawer-standard-reference-field-input"),
      "ISO/IEC 42010{Enter}",
    );

    await waitFor(() => expect(puts).toEqual([{ standard_reference: "ISO/IEC 42010" }]));
  });

  it("puts the signals back and says why when a save fails", async () => {
    const user = userEvent.setup();
    capturePuts(422);
    render(
      <>
        <OperationalDefinitionEditor classData={defined} />
        <ToastProbe />
      </>,
    );

    await user.click(screen.getByRole("button", { name: "Remove signal 1" }));
    const toast = await within(screen.getByTestId("toast-probe")).findByText(
      "distinguish_from names class-2 twice",
    );
    expect(toast).toHaveAttribute("data-type", "error");
    expect(screen.getByTestId("class-evidence-signal-input-0")).toHaveValue(
      "Has its own repository",
    );
    expect(
      within(screen.getByTestId("class-evidence-signals-list")).getAllByRole("listitem"),
    ).toHaveLength(3);
  });
});
