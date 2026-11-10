/**
 * The class drawer's operational-definition section (#1523): read-only in
 * view mode, an editor in edit mode that stays open across its saves.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { createTestQueryClient, render } from "@/test/test-utils";
import { component, entityPageHandlers } from "@/test/entityPageHandlers";
import { useClass } from "@/api/hooks/ontology/useClasses";
import { QUERY_KEYS } from "@/api/config";
import type { components } from "@/api/types";
import { ClassDrawer } from "../ClassDrawer";

type ClassResponse = components["schemas"]["ClassResponse"];
type ClassUpdateRequest = components["schemas"]["ClassUpdateRequest"];

const server = setupServer(...entityPageHandlers);

const defined: ClassResponse = {
  ...component,
  distinguish_from: [{ class_id: "class-2", when: "it is the exposed behaviour" }],
  evidence_signals: ["Is deployed on its own"],
  standard_reference: "ArchiMate 3.2",
};

// The class as the server holds it, the PUTs it got and how many times it was fetched.
let stored: ClassResponse;
let puts: ClassUpdateRequest[];
let gets: number;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  stored = defined;
  puts = [];
  gets = 0;
  server.use(
    http.get("*/api/classes/class-1", () => {
      gets += 1;
      return HttpResponse.json(stored);
    }),
    http.put("*/api/classes/class-1", async ({ request }) => {
      const body = (await request.json()) as ClassUpdateRequest;
      puts.push(body);
      stored = { ...stored, ...(body as Partial<ClassResponse>) };
      return HttpResponse.json(stored);
    }),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** The drawer fed by a class query, as a save's invalidation refetches it. */
function DrawerHost() {
  const { data } = useClass("class-1");
  return data ? <ClassDrawer classData={data} /> : null;
}

describe("ClassDrawer operational definition", () => {
  it("shows the definition in view mode, with sibling labels", async () => {
    render(<ClassDrawer classData={defined} />);

    const view = screen.getByTestId("class-definition-view");
    const entry = within(view).getByTestId("class-distinguish-entry-class-2");
    await waitFor(() => expect(entry).toHaveTextContent("ApplicationService"));
    expect(entry).toHaveTextContent("it is the exposed behaviour");
    expect(within(view).getByTestId("class-standard-reference")).toHaveTextContent("ArchiMate 3.2");
    expect(screen.queryByTestId("class-definition-editor")).not.toBeInTheDocument();
  });

  it("stays in edit mode when a save refetches the class", async () => {
    const user = userEvent.setup();
    render(<DrawerHost />);

    await user.click(await screen.findByTestId("inline-inspector-edit-button"));
    expect(screen.getByTestId("class-definition-editor")).toBeInTheDocument();

    // Rename: the field shows the new name only once the refetched class arrives.
    await user.click(screen.getByTestId("class-drawer-name-field-view"));
    const name = screen.getByTestId("class-drawer-name-field-input");
    await user.clear(name);
    await user.type(name, "AppComponent{Enter}");
    await waitFor(() => expect(puts).toEqual([{ title: "AppComponent" }]));
    await waitFor(() =>
      expect(screen.getByTestId("class-drawer-name-field-view")).toHaveTextContent("AppComponent"),
    );
    expect(screen.getByTestId("class-definition-editor")).toBeInTheDocument();
    expect(screen.queryByTestId("class-definition-view")).not.toBeInTheDocument();

    // A signal save refetches too; the editor stays and shows the saved list.
    const fetched = gets;
    await user.type(screen.getByTestId("class-evidence-signal-new"), "Exposes an API{Enter}");
    await waitFor(() => expect(puts).toHaveLength(2));
    await waitFor(() => expect(gets).toBeGreaterThan(fetched));
    await waitFor(() => expect(screen.getByTestId("class-evidence-signal-add")).not.toBeDisabled());
    expect(screen.getByTestId("class-definition-editor")).toBeInTheDocument();
    expect(screen.getByTestId("class-evidence-signal-input-1")).toHaveValue("Exposes an API");
  });

  it("keeps a description being typed when a refetch changes another field", async () => {
    const user = userEvent.setup();
    const queryClient = createTestQueryClient();
    render(<DrawerHost />, { queryClient });

    await user.click(await screen.findByTestId("inline-inspector-edit-button"));
    const description = screen.getByTestId("class-drawer-description-input");
    await user.clear(description);
    await user.type(description, "Half-typed defin");

    // Someone else's save lands: the class comes back with a new title, same description.
    stored = { ...stored, title: "AppComponent" };
    await queryClient.invalidateQueries({ queryKey: QUERY_KEYS.class("class-1") });
    await waitFor(() =>
      expect(screen.getByTestId("class-drawer-name-field-view")).toHaveTextContent("AppComponent"),
    );
    expect(description).toHaveValue("Half-typed defin");
    expect(puts).toEqual([]);
  });
});
