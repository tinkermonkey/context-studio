import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * The source text scrolls, so its box clips a highlight's surround (the selected
 * outline, the focus ring, the flash's shadow) on every side. The box keeps that
 * much room inside and pulls back by as much, so a passage at the start of a line
 * shows its whole surround and the text still lines up with the title (#1636).
 * jsdom has no layout, so guard the stylesheet itself.
 */
describe("review.css: the source text leaves room for a highlight's surround", () => {
  const css = readFileSync(resolve(__dirname, "../review.css"), "utf8").replace(
    /\/\*[\s\S]*?\*\//g,
    "",
  );

  /** The declarations of the first rule whose selector list includes `selector`. */
  const declarations = (selector: string): Record<string, string> => {
    const rule = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].find(([, selectors]) =>
      selectors.split(",").some((s) => s.trim() === selector),
    );
    if (!rule) throw new Error(`no rule for ${selector}`);
    return Object.fromEntries(
      rule[2]
        .split(";")
        .map((d) => d.split(":").map((part) => part.trim()))
        .filter(([property, value]) => property && value)
        .map(([property, ...value]) => [property, value.join(":")]),
    );
  };
  const px = (value: string) => {
    const match = /^(-?\d+(?:\.\d+)?)px$/.exec(value);
    if (!match) throw new Error(`not a single px length: ${value}`);
    return Number(match[1]);
  };
  /** How far an outline reaches outside its box: its width plus its offset. */
  const outlineReach = (selector: string) => {
    const rule = declarations(selector);
    return px(rule.outline.split(/\s+/)[0]) + px(rule["outline-offset"]);
  };

  const text = declarations(".review-source__text");
  const room = px(text.padding);

  it("pads the scroll box on every side and pulls it back by as much", () => {
    expect(room).toBeGreaterThan(0);
    expect(px(text.margin)).toBe(-room);
  });

  it("leaves room for the selected outline, the focus ring and the flash", () => {
    const flash = /@keyframes review-flash\s*\{([\s\S]*?\})\s*\}/.exec(css)?.[1] ?? "";
    const flashSpread = Math.max(
      0,
      ...[...flash.matchAll(/box-shadow:\s*0 0 0 (\d+(?:\.\d+)?)px/g)].map((m) => Number(m[1])),
    );
    expect(outlineReach(".review-mark--selected")).toBeLessThanOrEqual(room);
    expect(outlineReach(".review-mark:focus-visible")).toBeLessThanOrEqual(room);
    expect(flashSpread).toBeGreaterThan(0);
    expect(flashSpread).toBeLessThanOrEqual(room);
  });
});
