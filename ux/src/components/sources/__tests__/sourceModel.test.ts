import { describe, it, expect } from "vitest";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import {
  charsInPages,
  chunkRange,
  configurationPrice,
  emptyChunksWarning,
  estimateCost,
  extractionRunIds,
  failedChunks,
  failedChunksWarning,
  isPartlyRead,
  formatCount,
  formatRange,
  formatUsd,
  noProposalSummary,
  pageRangeLabel,
  pagesSpec,
  parsePages,
  proposalCounts,
  runChunks,
  skippedText,
  skipReasonLabel,
  sourceDetail,
  statusNote,
} from "../sourceModel";
import { createConfiguration, createRun, createSource } from "./fixtures";

describe("sourceModel", () => {
  it.each([
    [940, "940"],
    [2400, "2.4k"],
    [2000, "2k"],
    [118_400, "118k"],
    [1_200_000, "1.2M"],
  ])("formats %d characters as %s", (n, text) => {
    expect(formatCount(n)).toBe(text);
  });

  it("describes a file, a web page and pasted text by origin and size", () => {
    expect(sourceDetail(createSource())).toBe("wrf555sdfz-use-care.pdf · 4 pages · 20k chars");
    expect(
      sourceDetail(
        createSource({ kind: "web", origin: "https://energystar.gov/filters/", pages: 1 }),
      ),
    ).toBe("energystar.gov/filters · 20k chars");
    expect(sourceDetail(createSource({ kind: "text", origin: null, pages: 1, chars: 2400 }))).toBe(
      "pasted text · 2.4k chars",
    );
    // No size until it is read.
    expect(
      sourceDetail(createSource({ kind: "web", origin: "https://a.org/x", status: "fetching" })),
    ).toBe("a.org/x");
  });

  it("notes why a source failed, and that a web page is still being read", () => {
    expect(statusNote(createSource({ status: "failed", failure: "no_text" }))).toBe(
      "No text layer (scanned?)",
    );
    expect(statusNote(createSource({ status: "fetching" }))).toBe("Reading the page");
    expect(statusNote(createSource({ kind: "web", status: "failed", failure: "no_text" }))).toBe(
      "No text found",
    );
    expect(statusNote(createSource())).toBe("");
  });

  it("parses page lists and ranges, and rejects bad ones", () => {
    expect(parsePages("", 10)).toEqual({ pages: [] });
    expect(parsePages("1-3, 7, 2", 10)).toEqual({ pages: [1, 2, 3, 7] });
    // An en dash reads as "-".
    expect(parsePages("3–4", 10)).toEqual({ pages: [3, 4] });
    expect(parsePages("all", 10)).toEqual({
      error: "Use page numbers and ranges, like 1-12, 15.",
    });
    expect(parsePages("1-12", 10)).toEqual({ error: "Pages run from 1 to 10." });
    expect(parsePages("5-2", 10)).toEqual({ error: "Pages run from 1 to 10." });
    expect(parsePages("one", 10)).toEqual({
      error: "Use page numbers and ranges, like 1-12, 15.",
    });
  });

  it("builds the server's page spec from the parsed pages", () => {
    expect(pagesSpec([1, 2, 3, 7], 10)).toBe("1-3,7");
    expect(pagesSpec([2, 4, 5, 6, 9], 10)).toBe("2,4-6,9");
    expect(pagesSpec([5], 10)).toBe("5");
    // Every page, or none chosen, sends no spec.
    expect(pagesSpec([], 10)).toBeUndefined();
    expect(pagesSpec([1, 2, 3], 3)).toBeUndefined();
    const parsed = parsePages(" 3 – 4 ,1", 10);
    expect("pages" in parsed && pagesSpec(parsed.pages, 10)).toBe("1,3-4");
  });

  it("counts the characters on chosen pages and the range of chunks they make", () => {
    const source = createSource({ chars: 20_000, page_starts: [0, 5000, 10000, 18000] });
    expect(charsInPages(source, [])).toBe(20_000);
    expect(charsInPages(source, [1, 2])).toBe(10_000);
    expect(charsInPages(source, [4])).toBe(2000);
    // Full chunks at best, half-full ones (broken early at a heading or page) at worst.
    expect(chunkRange(20_000)).toEqual({ min: 3, max: 5 });
    expect(chunkRange(10)).toEqual({ min: 1, max: 1 });
    expect(formatRange(3, 5)).toBe("3–5");
    expect(formatRange(1, 1)).toBe("1");
  });

  it("estimates a cost only when the configuration carries a price", () => {
    expect(configurationPrice(createConfiguration())).toBeUndefined();
    const priced = createConfiguration({
      parameters: { price_per_mtok_in: 3, price_per_mtok_out: 15 } as never,
    });
    const price = configurationPrice(priced)!;
    expect(price).toEqual({ input: 3, output: 15 });
    // 8000 chars: 2000 text tokens + 1500 prompt in, 800 out → (3500·3 + 800·15) / 1e6
    expect(estimateCost(8000, 1, 1, price)).toBeCloseTo(0.0225);
    expect(estimateCost(8000, 1, 2, price)).toBeCloseTo(0.045);
    // Two half-full chunks: 2000 + 3000 tokens in, 1600 out.
    expect(estimateCost(8000, 2, 1, price)).toBeCloseTo(0.039);
    expect(formatUsd(0.0225)).toBe("$0.02");
    expect(formatUsd(0.004)).toBe("under $0.01");
  });

  it("labels page ranges", () => {
    expect(pageRangeLabel(3, 3)).toBe("p. 3");
    expect(pageRangeLabel(3, 5)).toBe("pp. 3–5");
    expect(pageRangeLabel(null, null)).toBe("");
  });

  it("warns about chunks that gave no candidates", () => {
    const run = createRun({
      status: "completed",
      output_summary: {
        metadata: {
          chunks: [
            { index: 0, start: 0, end: 8000, heading: "Safety", triples: 4 },
            { index: 1, start: 8000, end: 16000, heading: "Warranty", triples: 0 },
            { index: 2, start: 16000, end: 20000, heading: "Index", triples: 0 },
          ],
        },
      },
    });
    const chunks = runChunks(run);
    expect(chunks).toHaveLength(3);
    expect(emptyChunksWarning(chunks)).toBe("Chunks 2 and 3 (Warranty, Index) gave no candidates.");
    expect(emptyChunksWarning(chunks.slice(0, 2))).toBe("Chunk 2 (Warranty) gave no candidates.");
    expect(emptyChunksWarning(chunks.slice(0, 1))).toBe("");
    expect(runChunks(createRun())).toEqual([]);
  });

  describe("chunks whose extraction failed", () => {
    const chunksOf = (...chunks: Array<{ heading?: string; triples: number; failed?: string }>) =>
      runChunks(
        createRun({
          status: "completed",
          output_summary: {
            metadata: {
              chunks: chunks.map((c, index) => ({
                index,
                start: index * 8000,
                end: (index + 1) * 8000,
                heading: c.heading ?? null,
                triples: c.triples,
                failure_reason: c.failed ?? null,
              })),
            },
          },
        }),
      );

    it("says nothing when every chunk was read", () => {
      const chunks = chunksOf({ triples: 4 }, { triples: 2 }, { triples: 0 });
      expect(failedChunks(chunks)).toEqual([]);
      expect(failedChunksWarning(chunks)).toBe("");
      expect(emptyChunksWarning(chunks)).toBe("Chunk 3 gave no candidates.");
    });

    it("names one failed chunk of three, and never calls it empty", () => {
      const chunks = chunksOf(
        { heading: "Parts", triples: 4 },
        { heading: "Warranty", triples: 0, failed: "The response was cut short." },
        { heading: "Index", triples: 0 },
      );
      expect(failedChunks(chunks).map((c) => c.index)).toEqual([1]);
      expect(failedChunksWarning(chunks)).toBe(
        "Extraction failed for 1 of 3 chunks: chunk 2 (Warranty). What it holds is missing.",
      );
      // Only the chunk that was read and held nothing gave no candidates.
      expect(emptyChunksWarning(chunks)).toBe("Chunk 3 (Index) gave no candidates.");
    });

    it("names two failed chunks of three", () => {
      const chunks = chunksOf(
        { triples: 0 },
        { triples: 0, failed: "The response was cut short." },
        { triples: 0, failed: "Connection reset" },
      );
      expect(failedChunksWarning(chunks)).toBe(
        "Extraction failed for 2 of 3 chunks: chunks 2 and 3. What they hold is missing.",
      );
      expect(emptyChunksWarning(chunks)).toBe("Chunk 1 gave no candidates.");
    });

    it("says a failed chunk that still gave candidates lacks only part of what it holds", () => {
      const chunks = chunksOf(
        { triples: 4 },
        { heading: "Parts", triples: 3, failed: "Its relationships could not be read: cut short." },
        { triples: 2 },
      );
      expect(failedChunks(chunks).map(isPartlyRead)).toEqual([true]);
      expect(failedChunksWarning(chunks)).toBe(
        "Extraction failed in part for 1 of 3 chunks: chunk 2 (Parts). Part of what it holds is missing.",
      );
      expect(emptyChunksWarning(chunks)).toBe("");
    });

    it("says so of several chunks, and covers both kinds when they are mixed", () => {
      const partly = {
        triples: 3,
        failed: "1 of its 4 mentions could not be typed (Acme): cut short.",
      };
      expect(failedChunksWarning(chunksOf(partly, partly, { triples: 1 }))).toBe(
        "Extraction failed in part for 2 of 3 chunks: chunks 1 and 2. Part of what they hold is missing.",
      );
      const whole = { triples: 0, failed: "The response was cut short." };
      expect(chunksOf(whole).map(isPartlyRead)).toEqual([false]);
      expect(failedChunksWarning(chunksOf(partly, whole, { triples: 1 }))).toBe(
        "Extraction failed for 2 of 3 chunks: chunks 1 and 2. What they hold, or part of it, is missing.",
      );
    });
  });

  it("counts a proposal's operations, new individuals, relationships and near matches", () => {
    const proposal = createChangeProposal({
      operations: [
        createProposedOperation({ id: "a", op: "create", kind: "individual" }),
        createProposedOperation({
          id: "b",
          op: "create",
          kind: "individual",
          alternatives: [{ kind: "existing", entity_id: "i-9" }],
        }),
        createProposedOperation({ id: "c", op: "create", kind: "relationship" }),
      ],
    });
    expect(proposalCounts(proposal)).toEqual({
      operations: 3,
      individuals: 2,
      relationships: 1,
      nearMatches: 1,
    });
  });

  it("picks the individual and schema run ids out of an extraction's runs", () => {
    expect(
      extractionRunIds([
        { run_id: "s", pipeline: "schema_extraction" },
        { run_id: "i", pipeline: "individual_extraction" },
      ]),
    ).toEqual({ run: "i", schemaRun: "s" });
    expect(extractionRunIds([{ run_id: "i", pipeline: "individual_extraction" }])).toEqual({
      run: "i",
      schemaRun: undefined,
    });
  });

  describe("noProposalSummary", () => {
    const chunk = (triples: number, index = 0) => ({ index, start: 0, end: 1, triples });

    it("counts skipped candidates and refused operations by reason, most first", () => {
      const summary = noProposalSummary(
        createRun({
          status: "completed",
          output_summary: {
            metadata: { chunks: [chunk(4), chunk(3, 1)] },
            skipped_candidates: [
              { label: "a", reason: "missing_class" },
              { label: "b", reason: "exists" },
              { label: "c", reason: "exists" },
              { label: "d" },
            ],
            refused_operations: [{ label: "e", error: "Title taken" }],
          },
        }),
      );
      expect(summary).toEqual({
        found: 7,
        reason: undefined,
        candidatesFound: true,
        failedNote: "",
        skipped: [
          { reason: "exists", count: 2 },
          { reason: "missing_class", count: 1 },
          { reason: "invalid", count: 1 },
          { reason: "refused", count: 1 },
        ],
      });
      expect(skippedText(summary.skipped)).toBe(
        "2 already exist, 1 no matching class, 1 refused as invalid, 1 refused",
      );
    });

    it.each([
      ["exists", "already exist"],
      ["missing_class", "no matching class"],
      ["unresolved_predicate", "unknown relationship type"],
      ["unresolved_endpoint", "an end wasn't proposed"],
      ["literal", "values, not entities"],
      ["derived_type", "derived relationship type"],
      ["self_loop", "points at itself"],
      ["invalid", "refused as invalid"],
      ["no_scheme", "no concept scheme"],
      ["identifier_taken", "identifier already in use"],
      // An unknown code reads as words.
      ["some_new_reason", "some new reason"],
    ])("words the skip reason %s as %s", (code, words) => {
      expect(skipReasonLabel(code)).toBe(words);
    });

    it("prefers the server's reason, as it is, and its counts by reason", () => {
      const sentence =
        "None of the 3 candidates made an operation (missing_class 2, unresolved_endpoint 1).";
      const summary = noProposalSummary(
        createRun({
          output_summary: {
            no_proposal_reason: sentence,
            skipped_by_reason: { exists: 2, some_new_reason: 5, ignored: "x" },
            skipped_candidates: [{ label: "a", reason: "invalid" }],
          },
        }),
      );
      expect(summary.reason).toBe(sentence);
      expect(summary.skipped).toEqual([
        { reason: "some_new_reason", count: 5 },
        { reason: "exists", count: 2 },
      ]);
      expect(skippedText(summary.skipped)).toBe("5 some new reason, 2 already exist");
      // No chunks counted, but skipped candidates mean some were found.
      expect(summary.found).toBe(0);
      expect(summary.candidatesFound).toBe(true);
    });

    it("finds nothing when no chunk found a candidate and none were skipped", () => {
      const summary = noProposalSummary(
        createRun({ output_summary: { metadata: { chunks: [chunk(0)] } } }),
      );
      expect(summary).toEqual({
        found: 0,
        reason: undefined,
        skipped: [],
        candidatesFound: false,
        failedNote: "",
      });
      expect(noProposalSummary(undefined).candidatesFound).toBe(false);
    });

    it("says which chunks failed, so finding nothing is not the text holding nothing", () => {
      const summary = noProposalSummary(
        createRun({
          output_summary: {
            metadata: {
              chunks: [
                chunk(0),
                { ...chunk(0, 1), failure_reason: "The response was cut short." },
                { ...chunk(0, 2), failure_reason: "The response was cut short." },
              ],
            },
          },
        }),
      );
      expect(summary.candidatesFound).toBe(false);
      expect(summary.failedNote).toBe(
        "Extraction failed for 2 of 3 chunks: chunks 2 and 3. What they hold is missing.",
      );
    });
  });
});
