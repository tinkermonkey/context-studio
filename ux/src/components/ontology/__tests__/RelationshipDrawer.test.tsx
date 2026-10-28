import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { RelationshipDrawer } from "../RelationshipDrawer";
import {
  createListProperties,
  createPropertyDefinition,
  createRelationship,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";

const requires = createPropertyDefinition({ id: "prop-req", identifier: "requires" });

const server = setupServer(
  http.get("*/api/properties", () => HttpResponse.json(createListProperties([requires]))),
  http.get("*/api/classes", () => HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderDrawer(attributes?: Record<string, string | number | boolean | null>) {
  return render(
    <RelationshipDrawer
      relationship={createRelationship({
        id: "rel-1",
        source_id: "a",
        target_id: "b",
        property_definition_id: "prop-req",
        attributes,
      })}
      sourceName="Hang a picture"
      targetName="Picture hooks"
      propertyName="requires"
    />,
  );
}

describe("RelationshipDrawer attributes", () => {
  it("lists the relationship's attributes read-only", async () => {
    renderDrawer({ quantity: 2, unit: "each", optional: true });

    const grid = await screen.findByTestId("relationship-attributes-grid");
    expect(screen.getByTestId("relationship-inspector")).toBeInTheDocument();
    expect(within(grid).getByText("quantity")).toBeInTheDocument();
    expect(within(grid).getByText("2")).toBeInTheDocument();
    expect(within(grid).getByText("each")).toBeInTheDocument();
    expect(within(grid).getByText("yes")).toBeInTheDocument();
    expect(within(grid).queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("has no attributes section when there are none", async () => {
    renderDrawer();

    await screen.findByTestId("relationship-triple");
    expect(screen.queryByTestId("relationship-attributes-grid")).not.toBeInTheDocument();
  });
});
