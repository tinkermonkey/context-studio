/**
 * The server counts text offsets in code points (Python string indexes); the
 * browser counts UTF-16 units. They differ after any character outside the
 * Basic Multilingual Plane (an emoji, say), which takes two UTF-16 units.
 */

export interface OffsetMap {
  /** The UTF-16 index of a code-point offset into the text; undefined past its end. */
  toUtf16: (codePoint: number) => number | undefined;
  /** The code-point offset of a UTF-16 index into the text. */
  toCodePoint: (utf16: number) => number;
}

const SURROGATE = /[\uD800-\uDFFF]/;

/** Convert offsets into `text` between code points and UTF-16 units. */
export function offsetMap(text: string): OffsetMap {
  if (!SURROGATE.test(text)) {
    // Every character is one unit: the offsets are the same.
    return {
      toUtf16: (codePoint) => (codePoint >= 0 && codePoint <= text.length ? codePoint : undefined),
      toCodePoint: (utf16) => Math.max(0, Math.min(utf16, text.length)),
    };
  }
  // starts[n] is the UTF-16 index where code point n starts; the last entry is the length.
  const starts: number[] = [];
  for (let i = 0; i < text.length; ) {
    starts.push(i);
    i += (text.codePointAt(i) ?? 0) > 0xffff ? 2 : 1;
  }
  starts.push(text.length);
  return {
    toUtf16: (codePoint) =>
      codePoint >= 0 && codePoint < starts.length ? starts[codePoint] : undefined,
    toCodePoint: (utf16) => {
      // The last code point starting at or before the index.
      let low = 0;
      let high = starts.length - 1;
      while (low < high) {
        const mid = Math.ceil((low + high) / 2);
        if (starts[mid] <= utf16) low = mid;
        else high = mid - 1;
      }
      return low;
    },
  };
}
