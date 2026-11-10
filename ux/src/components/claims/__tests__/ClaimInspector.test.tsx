import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { claimHandlers, claimOne, claimTwo } from "@/test/claimFixtures";
import { ClaimInspector } from "../ClaimInspector";

// The real components, for their ARIA (radio groups, listbox selects, labelled fields).
vi.mock("@tinkermonkey/heimdall-ui", async () => vi.importActual("@tinkermonkey/heimdall-ui"));

const toast = vi.fn();
vi.mock("@/components/ui/Toast", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/ui/Toast")>()),
  useToasts: () => ({ toast, toasts: [], dismiss: vi.fn() }),
}));

const navigate = vi.fn();
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => navigate };
});

const { handlers, requests } = claimHandlers();
const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  requests.verdicts.length = 0;
  requests.schemes.length = 0;
  navigate.mockReset();
  toast.mockReset();
});
afterAll(() => server.close());

const taxonomy = { id: "tax-1", label: "dr_spec" };

describe("ClaimInspector", () => {
  it("shows the claim, its source note and the entities it names", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ClaimInspector claim={claimOne} taxonomy={taxonomy} onClose={onClose} />);

    const inspector = screen.getByTestId("claim-inspector");
    expect(inspector).toHaveClass("claim-inspector");
    expect(screen.getByTestId("claim-text")).toHaveClass("claim-text");
    expect(screen.getByTestId("claim-note")).toHaveTextContent("Its name should be required.");
    expect(screen.getByTestId("claim-note")).toHaveClass("claim-note");

    // Plain mono text until the lookup resolves the id, then a link.
    await waitFor(() =>
      expect(screen.getByTestId("claim-entity-cls-actor")).toHaveAttribute(
        "href",
        "/app/schema/classes/cls-actor",
      ),
    );
    const classLink = screen.getByTestId("claim-entity-cls-actor");
    expect(classLink).toHaveClass("entity-link");
    expect(classLink).toHaveTextContent("business.businessactor");

    // An attribute and a property link to the class page that lists them.
    await waitFor(() =>
      expect(screen.getByTestId("claim-entity-attr-name")).toHaveTextContent(
        "business.businessactor.name",
      ),
    );
    expect(screen.getByTestId("claim-entity-attr-name")).toHaveAttribute(
      "href",
      "/app/schema/classes/cls-actor",
    );
    // Every id resolved as a class, property or attribute: none is tried as a scheme
    expect(requests.schemes).toEqual([]);
    const property = screen.getByTestId("claim-entity-prop-serves");
    expect(property).toHaveTextContent("actor_serves_service");
    expect(property).toHaveAttribute("href", "/app/schema/classes/cls-actor");

    const unresolved = screen.getByTestId("claim-unresolved-refs");
    expect(unresolved.tagName).toBe("UL");
    expect(within(unresolved).getByText("business.businessactor.nickname")).toHaveClass(
      "claim-ref",
    );
    expect(within(unresolved).queryByRole("link")).not.toBeInTheDocument();

    expect(screen.getByTestId("claim-subject-link-cls-actor")).toHaveAttribute(
      "href",
      "/app/schema/classes/cls-actor",
    );

    await user.click(screen.getByRole("button", { name: "Close claim" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("shows the triage with its probabilities, the chosen answer marked", () => {
    render(<ClaimInspector claim={claimOne} taxonomy={taxonomy} onClose={vi.fn()} />);

    const triage = screen.getByTestId("claim-triage");
    const chosen = screen.getByTestId("claim-triage-validity-real_defect");
    expect(chosen).toHaveClass("claim-probability--chosen");
    expect(within(chosen).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "82");
    expect(within(chosen).getByText("0.82")).toHaveClass("claim-probability__p");
    expect(screen.getByTestId("claim-triage-validity-out_of_scope")).not.toHaveClass(
      "claim-probability--chosen",
    );
    expect(within(triage).getByRole("list", { name: "Validity probabilities" })).toBeVisible();
    expect(screen.getByTestId("claim-triage-category-attribute_typing")).toHaveClass(
      "claim-probability--chosen",
    );
    expect(within(triage).getByText("2 · significant")).toBeInTheDocument();
    expect(within(triage).getByText("1 · additive")).toBeInTheDocument();
  });

  it("says when a claim is not triaged", () => {
    render(<ClaimInspector claim={claimTwo} taxonomy={taxonomy} onClose={vi.fn()} />);

    expect(screen.getByTestId("claim-untriaged")).toHaveTextContent("Not triaged yet.");
    expect(screen.queryByTestId("claim-triage")).not.toBeInTheDocument();
    expect(screen.getByTestId("claim-note")).toHaveTextContent("No note text recorded.");
  });
});

describe("ClaimVerdictForm", () => {
  it("requires a validity, and clears the error as soon as one is chosen", async () => {
    const user = userEvent.setup();
    render(<ClaimInspector claim={claimOne} taxonomy={taxonomy} onClose={vi.fn()} />);

    const form = screen.getByRole("form", { name: "Verdict" });
    expect(form).toHaveAttribute("data-testid", "claim-verdict-form");
    expect(form).toHaveClass("claim-verdict");

    await user.click(screen.getByTestId("claim-verdict-submit"));
    expect(screen.getByText("Choose a validity.")).toBeInTheDocument();
    const trigger = screen.getByRole("button", { name: "Validity" });
    expect(trigger).toHaveAttribute("aria-invalid", "true");
    expect(trigger).toHaveAttribute("aria-haspopup", "listbox");
    expect(requests.verdicts).toHaveLength(0);

    await user.click(trigger);
    await user.click(screen.getByRole("option", { name: "judgment call" }));

    expect(screen.queryByText("Choose a validity.")).not.toBeInTheDocument();
    expect(trigger).not.toHaveAttribute("aria-invalid");
  });

  it("saves the verdict through the claims API", async () => {
    const user = userEvent.setup();
    render(<ClaimInspector claim={claimOne} taxonomy={taxonomy} onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Validity" }));
    await user.click(screen.getByRole("option", { name: "real defect" }));
    // The triage's category is offered among DR's categories.
    await user.click(screen.getByRole("button", { name: "Category" }));
    await user.click(screen.getByRole("option", { name: "attribute_typing" }));
    await user.click(screen.getByRole("button", { name: "Severity" }));
    await user.click(screen.getByRole("option", { name: "3 · blocking" }));
    await user.type(screen.getByTestId("claim-verdict-rationale"), "  Names are required.  ");
    await user.click(screen.getByTestId("claim-verdict-submit"));

    await waitFor(() => expect(requests.verdicts).toHaveLength(1));
    expect(requests.verdicts[0]).toEqual({
      method: "PUT",
      id: "claim-1",
      body: {
        validity: "real_defect",
        category: "attribute_typing",
        severity: 3,
        fix_scope: null,
        rationale: "Names are required.",
      },
    });
    await waitFor(() => expect(toast).toHaveBeenCalledWith("success", "Verdict saved"));
  });

  it("starts from the recorded verdict and can clear it", async () => {
    const user = userEvent.setup();
    render(<ClaimInspector claim={claimTwo} taxonomy={taxonomy} onClose={vi.fn()} />);

    const recorded = screen.getByTestId("claim-verdict-recorded");
    expect(recorded).toHaveTextContent("by dr-bench-gold");
    expect(within(recorded).getByText("works as designed")).toHaveClass("chip--emerald");
    expect(screen.getByRole("button", { name: "Validity" })).toHaveTextContent("works as designed");
    expect(screen.getByRole("button", { name: "Category" })).toHaveTextContent(
      "relationship_redundant",
    );
    expect(screen.getByTestId("claim-verdict-rationale")).toHaveValue("They differ by direction.");

    await user.click(screen.getByTestId("claim-verdict-clear"));

    await waitFor(() => expect(requests.verdicts).toEqual([{ method: "DELETE", id: "claim-2" }]));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("success", "Verdict cleared"));
    expect(screen.getByTestId("claim-verdict-rationale")).toHaveValue("");
  });
});
