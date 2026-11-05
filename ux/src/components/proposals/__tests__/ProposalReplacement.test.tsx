/**
 * A relationship-type delete's named replacement (#1398): the row chip and the
 * inspector callout flag a replacement that links a different pair of classes
 * (Gate B row 17), say so more quietly for a reversed or same pair, and the
 * in-use resolver marks the proposed replacement or says it doesn't fit.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { openProposal, proposalHandlers } from "@/test/proposalFixtures";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";
import { replacementEndLabel, replacementFlag, type ReplacementCheck } from "../proposalModel";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

let proposal: ChangeProposal;

const component = { id: "class-1", title: "Component" };
const service = { id: "class-2", title: "Service" };

function check(pair: ReplacementCheck["pair"], domain = component, range = component) {
  return {
    replacement_id: "prop-twin",
    property_id: "prop-twin",
    identifier: "component_uses_component",
    title: "uses",
    pair,
    deleted_domain: component,
    deleted_range: service,
    domain: pair === "missing" ? null : domain,
    range: pair === "missing" ? null : range,
  };
}

function theDelete(): ProposedOperation {
  return proposal.operations.find((o) => o.id === "op-delete")!;
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = structuredClone(openProposal);
  Object.assign(theDelete(), {
    stale: false,
    proposed_replacement_id: "prop-twin",
    replacement_check: check("different"),
  });
  server.use(http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)));
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage(selectedOperationId?: string) {
  return render(
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selectedOperationId}
      onSelectOperation={vi.fn()}
    />,
  );
}

const DIFFERENT =
  "Replacement links a different pair: application_component → application_component instead of application_component → application_service.";

describe("a delete naming its replacement", () => {
  it("flags a different pair on its row; other rows carry no flag", async () => {
    renderPage();

    const flag = await screen.findByTestId("operation-replacement-op-delete");
    expect(flag).toHaveAttribute("role", "note");
    expect(flag).toHaveAttribute("data-pair", "different");
    await waitFor(() => expect(flag).toHaveAccessibleName(expect.stringContaining(DIFFERENT)));
    expect(within(flag).getByText("different pair")).toHaveClass("chip--rose");
    expect(screen.queryByTestId("operation-replacement-op-rename")).not.toBeInTheDocument();
  });

  it("explains a different pair in the inspector as a warning", async () => {
    renderPage("op-delete");

    const section = await screen.findByTestId("operation-replacement");
    expect(section).toHaveAttribute("data-pair", "different");
    const callout = within(section).getByTestId("operation-replacement-callout");
    await waitFor(() => expect(callout).toHaveTextContent(DIFFERENT));
    expect(callout).toHaveTextContent(
      "component_uses_component can't take over this type's relationships as they are.",
    );
    expect(callout).toHaveAttribute("role", "alert");
    expect(within(section).getByText("component_uses_component")).toBeInTheDocument();
  });

  it("a same pair has no row flag, and an informational note in the inspector", async () => {
    theDelete().replacement_check = check("same", component, service);
    renderPage("op-delete");

    const callout = await screen.findByTestId("operation-replacement-callout");
    await waitFor(() =>
      expect(callout).toHaveTextContent(
        "Replacement component_uses_component links the same pair: application_component → application_service.",
      ),
    );
    expect(callout).not.toHaveAttribute("role", "alert");
    expect(screen.queryByTestId("operation-replacement-op-delete")).not.toBeInTheDocument();
  });

  it("a reversed pair gets an amber row chip", async () => {
    theDelete().replacement_check = check("reversed", service, component);
    renderPage();

    const flag = await screen.findByTestId("operation-replacement-op-delete");
    expect(within(flag).getByText("reversed pair")).toHaveClass("chip--amber");
  });

  it("an operation without a replacement has no Replacement section", async () => {
    theDelete().replacement_check = null;
    renderPage("op-delete");

    await screen.findByTestId("operation-inspector");
    expect(screen.queryByTestId("operation-replacement")).not.toBeInTheDocument();
  });
});

describe("the in-use resolver", () => {
  const blockers = (
    replacements: { property_id: string; identifier: string; title: string }[],
  ) => ({
    edges: [
      {
        relationship_id: "rel-1",
        source: {
          id: "ind-1",
          title: "Router",
          class_ids: ["class-1"],
          class_titles: ["Component"],
        },
        target: { id: "ind-2", title: "API", class_ids: ["class-2"], class_titles: ["Service"] },
        attributes: {},
      },
    ],
    replacements,
    move_unavailable_reason: replacements.length ? null : "no type fits",
  });

  it("marks the proposed replacement, listed first by the server", async () => {
    theDelete().replacement_check = check("same", component, service);
    theDelete().blockers = blockers([
      { property_id: "prop-twin", identifier: "component_uses_component", title: "uses" },
      { property_id: "prop-other", identifier: "relates_to", title: "relates to" },
    ]);
    renderPage("op-delete");

    const resolver = await screen.findByTestId("operation-in-use");
    expect(within(resolver).getByTestId("operation-resolution-apply")).toHaveTextContent(
      "move 1 relationship to component_uses_component",
    );
    expect(
      within(resolver).queryByTestId("operation-proposed-replacement-unfit"),
    ).not.toBeInTheDocument();
  });

  it("says when the proposed replacement doesn't fit", async () => {
    theDelete().blockers = blockers([
      { property_id: "prop-other", identifier: "relates_to", title: "relates to" },
    ]);
    renderPage("op-delete");

    expect(await screen.findByTestId("operation-proposed-replacement-unfit")).toHaveTextContent(
      "The proposed replacement component_uses_component doesn't fit every relationship",
    );
  });
});

describe("replacementFlag", () => {
  const label = (end: { id?: string | null }) => end.id ?? "any";

  it("falls back to the server's class title until the class loads", () => {
    const unresolved = (id: string | null) => id ?? "any";
    expect(replacementEndLabel({ id: "class-1", title: "Component" }, unresolved)).toBe(
      "Component",
    );
    expect(replacementEndLabel({ id: "class-1", title: "Component" }, () => "app_comp")).toBe(
      "app_comp",
    );
    expect(replacementEndLabel({ id: null, title: null }, unresolved)).toBe("any");
  });

  it("words each pair", () => {
    expect(replacementFlag(check("different"), label).text).toBe(
      "Replacement links a different pair: class-1 → class-1 instead of class-1 → class-2. component_uses_component can't take over this type's relationships as they are.",
    );
    expect(replacementFlag(check("reversed", service, component), label)).toMatchObject({
      chip: "reversed pair",
      warn: false,
      text: "Replacement component_uses_component links the same pair reversed: class-2 → class-1 instead of class-1 → class-2.",
    });
    expect(replacementFlag(check("missing"), label)).toMatchObject({
      chip: "replacement gone",
      warn: true,
    });
    const untyped = { ...check("different"), domain: { id: null, title: null } };
    expect(replacementFlag(untyped, label).text).toContain("any → class-1 instead of");
  });
});
