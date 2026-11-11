/**
 * Extraction proposals beside their sources (#1555), in the browser: source
 * passages in evidence, a quote placed in its page's text, near matches, the
 * ends of a relationship create, and what a bulk accept leaves for a choice.
 */
import { describe, it, expect } from "vitest";
import { createProposedOperation } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import {
  CREATE_NEW,
  alsoOnLabel,
  chosenAlternative,
  defaultNearMatchChoice,
  isNearMatch,
  matchedAlternative,
  nearMatchHeldIds,
  nearMatchHeldNote,
  nearMatchesOf,
  pageAt,
  placePassage,
  plainEvidenceOf,
  relationshipEnds,
  relationshipEndsNote,
  sectionAt,
  sourcePassagesOf,
  type SourcePassage,
} from "../sourceModel";

const passage = (page: number | null, start = 10, end = 20, quote?: string): SourcePassage => ({
  sourceId: "src-1",
  page,
  start,
  end,
  quote,
});

const fridge = createProposedOperation({
  id: "op-fridge",
  seq: 1,
  op: "create",
  kind: "individual",
  target_id: null,
  ref: "fridge",
  fields: { title: "Whirlpool WRF555SDFZ", class_ids: ["class-1"] },
  alternatives: [
    { kind: "existing", entity_id: "ind-2", similarity: 0.81, title: "Garage fridge" },
    { kind: "existing", entity_id: "ind-1", similarity: 0.93, title: "Kitchen refrigerator" },
  ],
});
const filter = createProposedOperation({
  id: "op-filter",
  seq: 2,
  op: "create",
  kind: "individual",
  target_id: null,
  ref: "filter",
  fields: { title: "EveryDrop Filter 1", class_ids: ["class-1"] },
});
const uses = createProposedOperation({
  id: "op-uses",
  seq: 3,
  op: "create",
  kind: "relationship",
  target_id: null,
  fields: { property_definition_id: "prop-1", source_id: "$fridge", target_id: "$filter" },
});
const madeBy = createProposedOperation({
  id: "op-made-by",
  seq: 4,
  op: "create",
  kind: "relationship",
  target_id: null,
  fields: { property_definition_id: "prop-1", source_id: "ind-9", target_id: "$filter" },
});

describe("source passages in evidence", () => {
  const op = createProposedOperation({
    evidence: [
      { source_id: "src-1", page: 5, start: 100, end: 135, quote: "French door refrigerator" },
      { quote: "A plain quote", url: "https://example.com" },
      { source_id: "src-1", page: 54, start: 9000, end: 9040 },
    ],
  });

  it("reads passages apart from plain evidence, in their order", () => {
    expect(sourcePassagesOf(op)).toEqual([
      { sourceId: "src-1", page: 5, start: 100, end: 135, quote: "French door refrigerator" },
      { sourceId: "src-1", page: 54, start: 9000, end: 9040, quote: undefined },
    ]);
    expect(plainEvidenceOf(op)).toEqual([{ quote: "A plain quote", url: "https://example.com" }]);
  });

  it("names the further passages' pages, leaving out the first's", () => {
    expect(alsoOnLabel([passage(5)])).toBeUndefined();
    expect(alsoOnLabel([passage(5), passage(55)])).toBe("Also on p. 55");
    expect(alsoOnLabel([passage(5), passage(54), passage(1), passage(5)])).toBe(
      "Also on pp. 1, 54",
    );
    expect(alsoOnLabel([passage(5), passage(5)])).toBe("Also 1 more passage on this page");
    expect(alsoOnLabel([passage(null), passage(null), passage(null)])).toBe("Also 2 more passages");
  });

  it("lists only the shown passage's source's pages, and counts the other sources", () => {
    const other = (sourceId: string, page: number): SourcePassage => ({
      ...passage(page),
      sourceId,
    });
    // Page 9 of another source is not "p. 9" of this one.
    expect(alsoOnLabel([passage(5), other("src-2", 9)])).toBe("Also in 1 other source");
    expect(alsoOnLabel([passage(5), passage(54), other("src-2", 9), other("src-3", 1)])).toBe(
      "Also on p. 54; also in 2 other sources",
    );
    expect(alsoOnLabel([passage(5), other("src-2", 9), other("src-2", 12)])).toBe(
      "Also in 1 other source",
    );
  });

  it("finds a passage's page and section from the source's offsets", () => {
    expect(pageAt(0, [0, 100, 200])).toBe(1);
    expect(pageAt(150, [0, 100, 200])).toBe(2);
    expect(pageAt(250, [0, 100, 200])).toBe(3);
    expect(pageAt(5, [])).toBeNull();
    const headings = [
      { start: 0, title: "Safety" },
      { start: 120, title: "Parts and features" },
    ];
    expect(sectionAt(130, headings)).toBe("Parts and features");
    expect(sectionAt(10, headings)).toBe("Safety");
  });
});

describe("placing a quote in its page's text", () => {
  const page = { text: "Thank you. Your French door fridge is here.", start: 1000 };

  it("highlights the quote at its offsets, with the text around it", () => {
    const placed = placePassage(passage(5, 1016, 1034, "French door fridge"), { text: page });
    expect(placed).toEqual({
      before: "Thank you. Your ",
      quote: "French door fridge",
      after: " is here.",
      placed: true,
    });
  });

  it("shows the quote alone when the text at its offsets differs", () => {
    const placed = placePassage(passage(5, 1016, 1033, "Something else"), { text: page });
    expect(placed).toEqual({ before: "", quote: "Something else", after: "", placed: false });
  });

  it("shows the quote alone without the source's text, or outside it", () => {
    expect(placePassage(passage(5, 1016, 1033, "French door fridge")).placed).toBe(false);
    expect(placePassage(passage(5, 5000, 5010, "x"), { text: page }).placed).toBe(false);
  });

  it("cuts long text either side at a word", () => {
    const long = { text: `${"word ".repeat(100)}QUOTE${" more".repeat(100)}`, start: 0 };
    const placed = placePassage(passage(1, 500, 505, "QUOTE"), { text: long });
    expect(placed.placed).toBe(true);
    expect(placed.before.startsWith("…word")).toBe(true);
    expect(placed.after.endsWith("more…")).toBe(true);
  });
});

describe("near matches", () => {
  it("lists an individual create's alternatives, most alike first", () => {
    expect(isNearMatch(fridge)).toBe(true);
    expect(isNearMatch(filter)).toBe(false);
    expect(nearMatchesOf(fridge).map((a) => a.entity_id)).toEqual(["ind-1", "ind-2"]);
  });

  it("opens on the most alike existing individual, and sends it as the chosen alternative", () => {
    expect(defaultNearMatchChoice(fridge)).toBe("ind-1");
    expect(chosenAlternative("ind-1")).toEqual({ kind: "existing", entity_id: "ind-1" });
    expect(chosenAlternative(CREATE_NEW)).toBeUndefined();
  });

  it("opens on Create new when no alternative still exists", () => {
    const gone = { ...fridge, alternatives: [{ kind: "existing" as const, entity_id: "x" }] };
    expect(defaultNearMatchChoice(gone)).toBe(CREATE_NEW);
  });

  it("knows the existing individual a matched create applied as", () => {
    const applied = {
      ...fridge,
      status: "applied" as const,
      matched: true,
      result_entity_id: "ind-1",
    };
    expect(matchedAlternative(applied)?.title).toBe("Kitchen refrigerator");
    expect(matchedAlternative(fridge)).toBeUndefined();
  });
});

describe("a relationship create's ends", () => {
  const ops = [fridge, filter, uses, madeBy];

  it("says which ends are new in the proposal and which follow a near match", () => {
    const ends = relationshipEnds(uses, ops);
    expect(ends.map((e) => [e.role, e.kind, e.seq])).toEqual([
      ["source", "near", 1],
      ["target", "new", 2],
    ]);
    expect(relationshipEndsNote(ends)).toBe(
      "Source is #1, a near match: it follows the choice made there; target is new in this proposal (#2). Rejecting #1 or #2 leaves this relationship unable to apply.",
    );
  });

  it("names an existing end and a matched one", () => {
    expect(relationshipEnds(madeBy, ops)[0].kind).toBe("existing");
    const matched = {
      ...fridge,
      status: "applied" as const,
      matched: true,
      result_entity_id: "ind-1",
    };
    const ends = relationshipEnds(uses, [matched, filter, uses]);
    expect(relationshipEndsNote(ends)).toContain(
      "Source is #1, which used the existing Kitchen refrigerator",
    );
  });

  it("has no ends for other operations", () => {
    expect(relationshipEnds(fridge, ops)).toEqual([]);
  });
});

describe("what a bulk accept leaves for a near-match choice", () => {
  it("holds awaiting near matches and the operations that name them", () => {
    expect([...nearMatchHeldIds([fridge, filter, uses, madeBy])]).toEqual(["op-fridge", "op-uses"]);
  });

  it("looks for the near match's $ref only in a relationship's ends", () => {
    // A title that happens to read like the ref is just text: "$ref" resolves only in ends.
    const named = createProposedOperation({
      id: "op-named",
      op: "create",
      kind: "individual",
      target_id: null,
      fields: { title: "$fridge", description: "$fridge" },
    });
    expect(nearMatchHeldIds([fridge, named]).has("op-named")).toBe(false);
  });

  it("holds nothing once the near match is decided", () => {
    const decided = { ...fridge, status: "applied" as const };
    expect(nearMatchHeldIds([decided, filter, uses]).size).toBe(0);
  });

  it("says what it left", () => {
    expect(nearMatchHeldNote([])).toBeUndefined();
    expect(nearMatchHeldNote([fridge])).toBe("1 near match is left for you to decide.");
    expect(nearMatchHeldNote([fridge, fridge, uses])).toBe(
      "2 near matches are left for you to decide, with 1 operation that names one.",
    );
  });
});
