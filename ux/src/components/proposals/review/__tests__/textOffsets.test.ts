import { describe, it, expect } from "vitest";
import { offsetMap } from "../textOffsets";

describe("offsetMap", () => {
  it("keeps the offsets of text without astral characters", () => {
    const map = offsetMap("Edit Check");
    expect(map.toUtf16(4)).toBe(4);
    expect(map.toUtf16(10)).toBe(10);
    expect(map.toUtf16(11)).toBeUndefined();
    expect(map.toCodePoint(4)).toBe(4);
  });

  it("counts an emoji as one code point and two UTF-16 units", () => {
    const text = "😀 Edit 😀Check";
    // Code points: 😀(0) ' '(1) E(2) d i t ' '(6) 😀(7) C(8) …
    const map = offsetMap(text);
    expect(map.toUtf16(0)).toBe(0);
    expect(map.toUtf16(2)).toBe(3);
    expect(map.toUtf16(8)).toBe(10);
    expect(text.slice(map.toUtf16(8), map.toUtf16(13))).toBe("Check");
    expect(map.toUtf16(13)).toBe(text.length);
    expect(map.toUtf16(14)).toBeUndefined();
    expect(map.toCodePoint(3)).toBe(2);
    expect(map.toCodePoint(10)).toBe(8);
    expect(map.toCodePoint(text.length)).toBe(13);
  });

  it("round-trips every code-point offset", () => {
    const text = "a😀b𝄞c";
    const map = offsetMap(text);
    for (let cp = 0; cp <= [...text].length; cp++) {
      expect(map.toCodePoint(map.toUtf16(cp)!)).toBe(cp);
    }
  });
});
