import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Heimdall's GraphCanvas sizes each node by measuring it inside an inline-block
 * wrapper. A `.graph-node` rule that takes the node out of flow collapses that
 * wrapper to 0x0, the canvas falls back to a default box, and every edge ends
 * off the node's outline. jsdom has no layout, so guard the stylesheet itself;
 * the E2E graph spec checks the real geometry.
 */
describe("graph.css", () => {
  const css = readFileSync(resolve(__dirname, "../../../design-system/graph.css"), "utf8");

  it("never sets position on a Heimdall .graph-node", () => {
    const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
    const offenders = [...withoutComments.matchAll(/([^{}]+)\{([^}]*)\}/g)]
      .filter(
        ([, selector, body]) =>
          /\.graph-node(?![\w-])/.test(selector) && /\bposition\s*:/.test(body),
      )
      .map(([, selector]) => selector.trim());
    expect(offenders).toEqual([]);
  });
});
