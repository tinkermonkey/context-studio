/**
 * The proposal route's search (#1663): ?selected= names the operation in the
 * inspector, and an old link's ?op= redirects to it in place.
 */
import { describe, it, expect } from "vitest";
import { isRedirect } from "@tanstack/react-router";
import { Route, redirectFromOp } from "../proposals_.$proposalId";

describe("an old ?op= link", () => {
  it("goes to the same operation as ?selected=, keeping an open wide diff", () => {
    expect(redirectFromOp({ op: "op-1" })).toEqual({ selected: "op-1" });
    expect(redirectFromOp({ op: "op-1", diff: "description" })).toEqual({
      selected: "op-1",
      diff: "description",
    });
  });

  it("leaves a current link alone", () => {
    expect(redirectFromOp({ selected: "op-1" })).toBeUndefined();
    expect(redirectFromOp({})).toBeUndefined();
  });

  it("is redirected by the route before it loads, replacing the entry it came in on", () => {
    const validate = Route.options.validateSearch as (search: Record<string, unknown>) => unknown;
    const search = validate({ op: "op-1" }) as Record<string, unknown>;
    expect(search).toMatchObject({ op: "op-1", selected: undefined });
    let thrown: unknown;
    try {
      (Route.options.beforeLoad as (ctx: unknown) => void)({
        params: { proposalId: "proposal-1" },
        search,
      });
    } catch (error) {
      thrown = error;
    }
    expect(isRedirect(thrown)).toBe(true);
    const options = (thrown as { options: Record<string, unknown> }).options;
    expect(options).toMatchObject({
      to: "/app/proposals/$proposalId",
      params: { proposalId: "proposal-1" },
      search: { selected: "op-1" },
      replace: true,
    });
  });

  it("lets a current link load", () => {
    expect(() =>
      (Route.options.beforeLoad as (ctx: unknown) => void)({
        params: { proposalId: "proposal-1" },
        search: { selected: "op-1" },
      }),
    ).not.toThrow();
  });
});
