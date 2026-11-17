import { describe, it, expect } from "vitest";
import { createClass } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import {
  EMPTY_DRAFT,
  GOLD_COMMANDS,
  annotationOf,
  classRef,
  classesByRef,
  goldCheckOf,
  goldElementOf,
  goldRow,
  goldRows,
  goldTierOf,
} from "../goldModel";

const ORIGIN = {
  pipeline_type: "individual_extraction",
  implementation_id: "gold_check",
  configuration_ref: "gold",
  configuration_version: 1,
  digest: "abc123",
};

const element = (id: string, ref: string, status = "pending") =>
  createProposedOperation({
    id,
    op: "create",
    kind: "individual",
    target_id: null,
    ref,
    status: status as "pending",
  });
const relationship = (id: string, seq: number, status = "pending") =>
  createProposedOperation({
    id,
    seq,
    op: "create",
    kind: "relationship",
    target_id: null,
    status: status as "pending",
  });

function goldProposal(overrides: Partial<ChangeProposal> = {}): ChangeProposal {
  return createChangeProposal({
    id: "p-gold",
    source: "pipeline",
    origin: ORIGIN,
    client_metadata: {
      origin: ORIGIN,
      source_id: "src-1",
      gold_check: {
        document: "edit_check",
        split: "dev",
        elements: {
          edit: {
            key: "edit",
            tier: "core",
            acceptable_classes: ["product.feature"],
            aliases: ["EditCheck"],
          },
          tone: { key: "tone", tier: "supporting", acceptable_classes: [], aliases: [] },
        },
        relationships: {
          "3": { source: "tone", predicate: "realizes", target: "edit", tier: "supporting" },
        },
      },
    },
    operations: [element("op-1", "edit"), element("op-2", "tone"), relationship("op-3", 3)],
    ...overrides,
  });
}

describe("gold checks", () => {
  it("reads a gold check's mapping", () => {
    const gold = goldCheckOf(goldProposal())!;
    expect(gold.document).toBe("edit_check");
    expect(gold.split).toBe("dev");
    const [edit, , rel] = goldProposal().operations;
    expect(goldElementOf(gold, edit)).toEqual({
      key: "edit",
      tier: "core",
      acceptableClasses: ["product.feature"],
      aliases: ["EditCheck"],
    });
    expect(goldTierOf(gold, edit)).toBe("core");
    expect(goldTierOf(gold, rel)).toBe("supporting");
    expect(goldTierOf(gold, element("op-9", "added"))).toBeUndefined();
  });

  it("isn't a gold check without the gold_check origin or its mapping", () => {
    expect(
      goldCheckOf(goldProposal({ origin: { ...ORIGIN, implementation_id: "single_call" } })),
    ).toBeUndefined();
    expect(goldCheckOf(goldProposal({ client_metadata: { origin: ORIGIN } }))).toBeUndefined();
    expect(goldCheckOf(createChangeProposal())).toBeUndefined();
    expect(goldCheckOf(undefined)).toBeUndefined();
  });

  it("names classes by reference, as gold files do", () => {
    const dr = createClass({
      id: "c-1",
      identifier: "product_feature",
      external_references: [
        { source: "wikidata", identifier: "Q1" },
        { source: "documentation_robotics", identifier: "product.feature" },
      ],
    });
    const other = createClass({
      id: "c-2",
      identifier: "x",
      external_references: [{ source: "wikidata", identifier: "Q2" }],
    });
    const plain = createClass({ id: "c-3", identifier: "room", external_references: [] });
    expect(classRef(dr)).toBe("product.feature");
    expect(classRef(other)).toBe("Q2");
    expect(classRef(plain)).toBe("room");
    expect(
      classesByRef(["room", "unknown", "product.feature"], [dr, other, plain]).map((c) => c.id),
    ).toEqual(["c-3", "c-1"]);
  });
});

describe("annotations", () => {
  it("sends the tier only when changed, and the also defensible classes", () => {
    expect(annotationOf(EMPTY_DRAFT, { goldTier: "core" })).toBeUndefined();
    expect(annotationOf({ ...EMPTY_DRAFT, tier: "core" }, { goldTier: "core" })).toBeUndefined();
    expect(annotationOf({ ...EMPTY_DRAFT, tier: "supporting" }, { goldTier: "core" })).toEqual({
      tier: "supporting",
    });
    expect(
      annotationOf({ ...EMPTY_DRAFT, alsoDefensible: ["c-2", "c-2"] }, { goldTier: "core" }),
    ).toEqual({ also_defensible: ["c-2"] });
  });

  it("keeps the replaced class only when asked, never the new one", () => {
    const draft = { tier: undefined, alsoDefensible: ["c-new", "c-2"], keepOld: true };
    expect(annotationOf(draft, { oldClassId: "c-old", newClassId: "c-new" })).toEqual({
      also_defensible: ["c-2", "c-old"],
    });
    expect(
      annotationOf({ ...draft, keepOld: false }, { oldClassId: "c-old", newClassId: "c-new" }),
    ).toEqual({ also_defensible: ["c-2"] });
    // Correct (no new class): keepOld is about a replacement, so it adds nothing.
    expect(
      annotationOf({ ...EMPTY_DRAFT, keepOld: true }, { oldClassId: "c-old" }),
    ).toBeUndefined();
  });
});

describe("the Gold page's rows", () => {
  it("counts the check's progress and says what to do next", () => {
    const fresh = goldRow(goldProposal(), goldCheckOf(goldProposal())!);
    expect(fresh).toMatchObject({
      document: "edit_check",
      split: "dev",
      individuals: 2,
      relationships: 1,
      decided: 0,
      total: 3,
      percent: 0,
      status: "model-made",
      action: "Check gold",
    });
    const started = goldProposal({
      operations: [
        element("op-1", "edit", "applied"),
        element("op-2", "tone"),
        relationship("op-3", 3),
      ],
    });
    expect(goldRow(started, goldCheckOf(started)!)).toMatchObject({
      decided: 1,
      percent: 33,
      status: "model-made",
      action: "Continue",
    });
    const done = goldProposal({
      status: "done",
      operations: [
        element("op-1", "edit", "applied"),
        element("op-2", "tone", "rejected"),
        relationship("op-3", 3, "rejected"),
      ],
    });
    expect(goldRow(done, goldCheckOf(done)!)).toMatchObject({ status: "checked", action: "Open" });
    const reverted = goldProposal({ status: "reverted" });
    expect(goldRow(reverted, goldCheckOf(reverted)!).status).toBe("reverted");
  });

  it("lists only gold checks, newest first", () => {
    const older = goldProposal({ id: "p-old", created_at: "2026-11-01T00:00:00Z" });
    const newer = goldProposal({ id: "p-new", created_at: "2026-11-10T00:00:00Z" });
    const other = createChangeProposal({ id: "p-x", source: "pipeline" });
    expect(goldRows([older, other, newer]).map((r) => r.proposalId)).toEqual(["p-new", "p-old"]);
  });

  it("builds the scripts' commands", () => {
    expect(GOLD_COMMANDS.check("edit_check")).toBe(
      "python scripts/extraction_benchmark.py check --document edit_check",
    );
    expect(GOLD_COMMANDS.writeGold("edit_check", "p-1")).toBe(
      "python scripts/extraction_benchmark.py write-gold --document edit_check --proposal p-1",
    );
    expect(GOLD_COMMANDS.replay).toBe("python scripts/benchmark_replay.py --all");
    expect(GOLD_COMMANDS.replayExternal).toBe("python scripts/benchmark_external.py replay");
  });
});
