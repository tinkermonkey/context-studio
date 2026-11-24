import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { openProposal, proposalHandlers } from "@/test/proposalFixtures";
import { ProposalPage } from "../proposals_.$proposalId";

const server = setupServer(
  // Any id serves the open proposal under that id.
  http.get("*/api/proposals/:id", ({ params }) =>
    HttpResponse.json({ ...openProposal, id: params.id as string }),
  ),
  ...proposalHandlers,
  ...entityPageHandlers,
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("ProposalPage", () => {
  it("resets checked operations and the threshold when moving to another proposal", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ProposalPage proposalId="proposal-1" />);

    await user.click(await screen.findByTestId("review-bulk-select"));
    fireEvent.change(screen.getByTestId("proposal-threshold-slider"), {
      target: { value: "0.85" },
    });
    expect(screen.getByTestId("proposal-threshold-value")).toHaveTextContent("0.85");
    await user.click(screen.getByTestId("operation-check-op-rename"));
    expect(screen.getByTestId("proposal-selection-count")).toHaveTextContent("1 selected");

    rerender(<ProposalPage proposalId="proposal-3" />);

    expect(await screen.findByTestId("operation-check-op-rename")).not.toBeChecked();
    expect(screen.queryByTestId("proposal-selection-bar")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-bulk-select"));
    expect(screen.getByTestId("proposal-threshold-value")).toHaveTextContent("0.60");
  });
});
