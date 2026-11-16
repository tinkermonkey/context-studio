import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { PropertyDrawer } from "../PropertyDrawer";
import {
  createPropertyDefinition,
  createListClasses,
  createListRelationships,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

function setupDefaultHandlers() {
  server.use(
    http.get("*/api/classes", () => HttpResponse.json(createListClasses([]))),
    http.get("*/api/relationships", () => HttpResponse.json(createListRelationships([]))),
    http.get("*/api/properties/:id/attributes", () => HttpResponse.json([])),
  );
}

async function enterEditMode(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => {
    expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
  });
  await user.click(screen.getByTestId("inline-inspector-edit-button"));
}

describe("PropertyDrawer - canonical_predicate", () => {
  it("shows the canonical predicate in view mode", async () => {
    setupDefaultHandlers();

    render(
      <PropertyDrawer
        property={createPropertyDefinition({ id: "prop-001", canonical_predicate: "navigates-to" })}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("navigates-to")).toBeInTheDocument();
    });
  });

  it("autosaves the canonical predicate on edit", async () => {
    const user = userEvent.setup();
    let putBody: Record<string, unknown> | null = null;

    setupDefaultHandlers();
    server.use(
      http.put("*/api/properties/prop-001", async ({ request }) => {
        putBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          createPropertyDefinition({ id: "prop-001", canonical_predicate: "navigates-to" }),
        );
      }),
    );

    render(
      <PropertyDrawer
        property={createPropertyDefinition({
          id: "prop-001",
          title: "Test Property",
          canonical_predicate: null,
        })}
      />,
    );

    await enterEditMode(user);

    await user.click(screen.getByTestId("property-drawer-canonical-predicate-field-view"));
    const input = screen.getByTestId("property-drawer-canonical-predicate-field-input");
    await user.clear(input);
    await user.type(input, "navigates-to");
    await user.tab();

    await waitFor(
      () => {
        expect(putBody).toMatchObject({ canonical_predicate: "navigates-to" });
      },
      { timeout: 3000 },
    );
  });
});

describe("PropertyDrawer - predicate can't be cleared", () => {
  it("shows an error instead of saving an empty predicate, and clears it on typing", async () => {
    const user = userEvent.setup();
    let putCalled = false;

    setupDefaultHandlers();
    server.use(
      http.put("*/api/properties/prop-001", () => {
        putCalled = true;
        return HttpResponse.json(createPropertyDefinition({ id: "prop-001" }));
      }),
    );

    render(
      <PropertyDrawer
        property={createPropertyDefinition({ id: "prop-001", canonical_predicate: "navigates-to" })}
      />,
    );

    await enterEditMode(user);

    await user.click(screen.getByTestId("property-drawer-canonical-predicate-field-view"));
    const input = screen.getByTestId("property-drawer-canonical-predicate-field-input");
    await user.clear(input);
    await user.tab();

    expect(
      await screen.findByText("A relationship type's predicate can't be cleared"),
    ).toBeInTheDocument();
    expect(putCalled).toBe(false);

    await user.type(screen.getByTestId("property-drawer-canonical-predicate-field-input"), "u");
    expect(
      screen.queryByText("A relationship type's predicate can't be cleared"),
    ).not.toBeInTheDocument();
  });
});

describe("PropertyDrawer - structure (#1482)", () => {
  it("shows the cardinality, flags and edge attributes", async () => {
    setupDefaultHandlers();
    server.use(
      http.get("*/api/properties/prop-001/attributes", () =>
        HttpResponse.json([
          {
            id: "a1",
            class_id: null,
            property_definition_id: "prop-001",
            identifier: "unit",
            title: "Unit",
            datatype: "string",
            is_required: true,
            allowed_values: ["each", "kg"],
            default_value: "each",
            sort_order: 1,
          },
          {
            id: "a2",
            class_id: null,
            property_definition_id: "prop-001",
            identifier: "quantity",
            title: "Quantity",
            datatype: "number",
            is_required: false,
            sort_order: 0,
          },
        ]),
      ),
    );

    render(
      <PropertyDrawer
        property={createPropertyDefinition({
          id: "prop-001",
          max_per_source: 1,
          hierarchy: true,
        })}
      />,
    );

    expect(await screen.findByText("per source 0..1 · per target 0..∞")).toBeInTheDocument();
    expect(screen.getByText("yes (no cycles)")).toBeInTheDocument();
    const attributes = await screen.findByTestId("property-edge-attributes");
    expect(attributes).toHaveTextContent("quantitynumber");
    expect(attributes).toHaveTextContent("unitstring (each, kg) required default each");
  });

  it("leaves the edge attributes section out when there are none", async () => {
    setupDefaultHandlers();
    render(<PropertyDrawer property={createPropertyDefinition({ id: "prop-001" })} />);

    expect(await screen.findByText("per source 0..∞ · per target 0..∞")).toBeInTheDocument();
    expect(screen.queryByTestId("property-edge-attributes")).not.toBeInTheDocument();
  });
});

describe("PropertyDrawer - definition Suggest", () => {
  it("refines the property's own definition", async () => {
    const user = userEvent.setup();
    let runBody: Record<string, unknown> | null = null;

    setupDefaultHandlers();
    server.use(
      http.post("*/api/pipelines/schema_node_definition_refinement/run", async ({ request }) => {
        runBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "run-1", status: "pending" });
      }),
      http.get("*/api/pipelines/runs/run-1", () =>
        HttpResponse.json({ id: "run-1", status: "completed" }),
      ),
      http.get("*/api/pipelines/runs/run-1/candidates", () => HttpResponse.json([])),
    );

    render(<PropertyDrawer property={createPropertyDefinition({ id: "prop-001" })} />);
    await enterEditMode(user);
    await user.click(screen.getByRole("button", { name: /Suggest/ }));

    await waitFor(() => {
      expect(runBody).toMatchObject({ node_id: "prop-001" });
    });
    // The server's default implementation and configuration run: none is named.
    expect(runBody).not.toHaveProperty("implementation_id");
    expect(runBody).not.toHaveProperty("configuration_ref");
  });
});
