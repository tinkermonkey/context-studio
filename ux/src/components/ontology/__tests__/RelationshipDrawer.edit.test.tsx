import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { RelationshipBuilderValue } from "@tinkermonkey/heimdall-ui";
import { render } from "@/test/test-utils";
import { RelationshipDrawer } from "../RelationshipDrawer";
import {
  createListProperties,
  createPropertyDefinition,
  createRelationship,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";

// The global setup stubs RelationshipBuilder as an empty div; this stub lets
// the test pick another predicate the way the real builder's select would.
vi.mock("@tinkermonkey/heimdall-ui", async () => {
  const actual = await vi.importActual<typeof import("@tinkermonkey/heimdall-ui")>(
    "@tinkermonkey/heimdall-ui",
  );
  return {
    ...actual,
    RelationshipBuilder: ({
      value,
      onChange,
    }: {
      value: RelationshipBuilderValue;
      onChange: (value: RelationshipBuilderValue) => void;
    }) => (
      <button type="button" onClick={() => onChange({ ...value, predicate: "needs" })}>
        Use needs
      </button>
    ),
  };
});

const requires = createPropertyDefinition({ id: "prop-req", identifier: "requires" });
const needs = createPropertyDefinition({ id: "prop-needs", identifier: "needs" });

const server = setupServer(
  http.get("*/api/properties", () => HttpResponse.json(createListProperties([requires, needs]))),
  http.get("*/api/classes", () => HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("RelationshipDrawer edit", () => {
  it("carries the attributes over when an edit replaces the relationship", async () => {
    const user = userEvent.setup();
    let posted: Record<string, unknown> | null = null;
    let deleted = false;
    server.use(
      http.post("*/api/relationships", async ({ request }) => {
        posted = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(createRelationship({ id: "rel-2" }), { status: 201 });
      }),
      http.delete("*/api/relationships/rel-1", () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    render(
      <RelationshipDrawer
        relationship={createRelationship({
          id: "rel-1",
          source_id: "a",
          target_id: "b",
          property_definition_id: "prop-req",
          attributes: { quantity: 2, unit: "each" },
        })}
        sourceName="Hang a picture"
        targetName="Picture hooks"
        propertyName="requires"
      />,
    );

    await user.click(await screen.findByTestId("inline-inspector-edit-button"));
    await user.click(await screen.findByRole("button", { name: "Use needs" }));
    await user.click(screen.getByTestId("relationship-edit-save"));

    await waitFor(() => expect(deleted).toBe(true));
    expect(posted).toEqual({
      source_id: "a",
      target_id: "b",
      relationship_type: "needs",
      attributes: { quantity: 2, unit: "each" },
    });
  });
});
