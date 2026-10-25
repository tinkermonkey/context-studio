import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { entityPath } from "@/lib/entityPaths";
import { EntityLink } from "../EntityLink";

describe("entityPath", () => {
  it.each([
    ["taxonomy", "/app/schema/taxonomies/x"],
    ["scheme", "/app/schema/schemes/x"],
    ["class", "/app/schema/classes/x"],
    ["individual", "/app/data/individuals/x"],
  ] as const)("maps %s to its page", (kind, path) => {
    expect(entityPath(kind, "x")).toBe(path);
  });

  it("encodes the id", () => {
    expect(entityPath("class", "a/b")).toBe("/app/schema/classes/a%2Fb");
  });
});

describe("EntityLink", () => {
  it("renders a real link to the entity page", () => {
    render(
      <EntityLink kind="scheme" id="s1" data-testid="entity-parent-link">
        Application Layer
      </EntityLink>,
    );
    const link = screen.getByRole("link", { name: "Application Layer" });
    expect(link).toHaveAttribute("href", "/app/schema/schemes/s1");
    expect(link).toHaveClass("entity-link");
    expect(link).toHaveAttribute("data-testid", "entity-parent-link");
  });
});
