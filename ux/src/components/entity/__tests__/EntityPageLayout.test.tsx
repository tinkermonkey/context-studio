import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EntityBody, EntityPageLayout } from "../EntityPageParts";

describe("EntityPageLayout", () => {
  it("wraps the page in the size-container frame the column breakpoints query", () => {
    const { container } = render(
      <EntityPageLayout navigator={<div>tree</div>} data-testid="class-page">
        <EntityBody identity={<aside data-testid="entity-identity">identity</aside>}>
          <section>sections</section>
        </EntityBody>
      </EntityPageLayout>,
    );

    // Breakpoints are container queries on .entity-page-frame (navigator column)
    // and .entity-page__main (Identity card, header actions): the chat column
    // narrows the canvas, not the viewport, so media queries can't see it.
    const frame = container.firstElementChild as HTMLElement;
    expect(frame).toHaveClass("entity-page-frame");
    const page = screen.getByTestId("class-page");
    expect(page).toHaveClass("entity-page");
    expect(page.parentElement).toBe(frame);

    const navigator = page.querySelector(":scope > aside.entity-page__navigator");
    const main = page.querySelector(":scope > .entity-page__main");
    expect(navigator).toHaveTextContent("tree");
    expect(main?.querySelector(".entity-page__body > .entity-page__sections")).toHaveTextContent(
      "sections",
    );
    expect(main?.querySelector(".entity-page__body")).toContainElement(
      screen.getByTestId("entity-identity"),
    );
  });
});
