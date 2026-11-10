/**
 * The class drawer's operational-definition section (#1523): read-only in
 * view mode, an editor in edit mode that stays open across its saves.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { useState } from "react";
import { render } from "@/test/test-utils";
import { component, entityPageHandlers } from "@/test/entityPageHandlers";
import type { components } from "@/api/types";
import { ClassDrawer } from "../ClassDrawer";

type ClassResponse = components["schemas"]["ClassResponse"];

const server = setupServer(...entityPageHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const defined: ClassResponse = {
  ...component,
  distinguish_from: [{ class_id: "class-2", when: "it is the exposed behaviour" }],
  evidence_signals: ["Is deployed on its own"],
  standard_reference: "ArchiMate 3.2",
};

/** The drawer as the classes page shows it: the class it gets is replaced after each save. */
function DrawerHost({ initial }: { initial: ClassResponse }) {
  const [classData, setClassData] = useState(initial);
  server.use(
    http.put("*/api/classes/class-1", async ({ request }) => {
      const updated = { ...classData, ...((await request.json()) as object) };
      setClassData(updated);
      return HttpResponse.json(updated);
    }),
  );
  return <ClassDrawer classData={classData} />;
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

  it("edits it in edit mode and stays in edit mode after a save", async () => {
    const user = userEvent.setup();
    render(<DrawerHost initial={defined} />);

    await user.click(screen.getByTestId("inline-inspector-edit-button"));
    expect(screen.getByTestId("class-definition-editor")).toBeInTheDocument();

    await user.type(screen.getByTestId("class-evidence-signal-new"), "Exposes an API{Enter}");

    await waitFor(() =>
      expect(screen.getByTestId("class-evidence-signal-input-1")).toHaveValue("Exposes an API"),
    );
    // The refetched class replaces the old one; the drawer keeps editing.
    expect(screen.getByTestId("class-definition-editor")).toBeInTheDocument();
    expect(screen.queryByTestId("class-definition-view")).not.toBeInTheDocument();
  });
});
