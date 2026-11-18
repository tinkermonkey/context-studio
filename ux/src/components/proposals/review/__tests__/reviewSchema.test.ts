import { describe, it, expect } from "vitest";
import {
  createClass,
  createPropertyDefinition,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { createProposedOperation } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import { buildReviewSchema } from "../reviewSchema";
import { endEntityId, relationshipEdit, relationshipEdited, verdictLabel } from "../reviewModel";

const feature = createClass({ id: "feature", identifier: "product.feature", title: "Feature" });
const subFeature = createClass({
  id: "sub",
  identifier: "product.subfeature",
  title: "Sub feature",
  parent_class_id: "feature",
});
const capability = createClass({ id: "cap", identifier: "product.cap", title: "Capability" });
const outside = createClass({ id: "out", identifier: "other.thing", title: "Thing" });
const realizes = createPropertyDefinition({
  id: "p-realizes",
  canonical_predicate: "realizes",
  description: "Makes it real.",
  domain_class_id: "feature",
  range_class_id: "cap",
});
const elsewhere = createPropertyDefinition({
  id: "p-elsewhere",
  canonical_predicate: "uses",
  domain_class_id: "x-not-in-taxonomy",
  range_class_id: "cap",
});

const schema = buildReviewSchema({
  classes: [feature, subFeature, capability],
  schemes: [],
  properties: [realizes, elsewhere],
  predicates: [],
  loading: false,
});

describe("the review schema", () => {
  it("allows a type from a class and the classes that inherit from it", () => {
    expect(schema.typesFrom("sub").map((p) => p.id)).toEqual(["p-realizes"]);
    expect(schema.typesTo("cap").map((p) => p.id)).toEqual(["p-realizes"]);
    expect(schema.allowedTypes("sub", "cap").map((p) => p.id)).toEqual(["p-realizes"]);
    expect(schema.allowedTypes("cap", "sub")).toEqual([]);
    expect(schema.fits("sub", "feature")).toBe(true);
    expect(schema.fits("feature", "sub")).toBe(false);
    expect(schema.fits(outside.id, null)).toBe(true);
  });

  it("names a type by its predicate and reads its definition", () => {
    expect(schema.predicateLabel("p-realizes")).toBe("realizes");
    expect(schema.predicateDefinition("p-realizes")).toBe("Makes it real.");
    expect(schema.classLabel("feature")).toBe("Feature");
    expect(schema.classLabel(undefined)).toBe("no class");
  });
});

describe("a relationship's edit", () => {
  const study = createProposedOperation({
    id: "op-study",
    op: "create",
    kind: "individual",
    ref: "study",
    status: "applied",
    result_entity_id: "ent-study",
    fields: { title: "Study", class_ids: ["feature"] },
  });
  const rel = createProposedOperation({
    id: "op-rel",
    op: "create",
    kind: "relationship",
    status: "pending",
    fields: { source_id: "$study", target_id: "ent-den", property_definition_id: "p-realizes" },
  });
  const ops = [study, rel];

  it("resolves an end to the entity it stands for", () => {
    expect(endEntityId("$study", ops)).toBe("ent-study");
    expect(endEntityId("ent-den", ops)).toBe("ent-den");
  });

  it("sends only what the reviewer changed", () => {
    expect(relationshipEdit(rel, ops, {})).toBeUndefined();
    expect(relationshipEdit(rel, ops, { source_id: "ent-study" })).toBeUndefined();
    expect(relationshipEdit(rel, ops, { target_id: "ent-hall" })).toEqual({
      target_id: "ent-hall",
    });
  });

  it("reads an applied edit as edited", () => {
    const applied = {
      ...rel,
      status: "applied" as const,
      applied_fields: { ...rel.fields, target_id: "ent-hall" },
    };
    expect(relationshipEdited(applied)).toBe(true);
    expect(verdictLabel(applied)).toBe("edited");
    expect(relationshipEdited({ ...applied, applied_fields: null })).toBe(false);
  });
});
