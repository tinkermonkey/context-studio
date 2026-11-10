/**
 * Claims on taxonomy "tax-1" (identifier dr_spec): "claim-1" is triaged as a
 * real defect about class cls-actor, naming the class, its "name" attribute,
 * a property and an unresolved DR id; "claim-2" is untriaged and has DR's
 * bench-gold verdict. The handlers serve them, the ontology they name, and
 * record each claims request (list, export, verdict) for assertions.
 */
import { http, HttpResponse } from "msw";
import type { Claim } from "@/api/services/claims";
import {
  createClass,
  createPropertyDefinition,
  createTaxonomy,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";

export const claimOne: Claim = {
  id: "claim-1",
  taxonomy_id: "tax-1",
  key: "note-7#1",
  text: "BusinessActor's name attribute should be required.",
  note_ref: "note-7",
  note_source: "reviewer",
  note_text: "Several things about BusinessActor.\nIts name should be required.",
  subject_id: "cls-actor",
  category_hint: "attribute_typing",
  affected_ids: ["cls-actor", "attr-name", "prop-serves"],
  unresolved_refs: ["business.businessactor.nickname"],
  proposed_change: null,
  triage: {
    validity: "real_defect",
    validity_probabilities: {
      real_defect: 0.82,
      works_as_designed: 0.1,
      judgment_call: 0.05,
      out_of_scope: 0.03,
    },
    category: "attribute_typing",
    category_probabilities: { attribute_typing: 0.7, missing_attribute: 0.2, other: 0.1 },
    severity: 2,
    fix_scope: 1,
    addressed_by_proposal: null,
    model: "claude-test",
    calibrated: true,
    cost_usd: 0.0012,
    latency_ms: 840,
    triaged_at: "2026-11-08T10:00:00Z",
  },
  verdict: null,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-08T10:00:00Z",
};

export const claimTwo: Claim = {
  id: "claim-2",
  taxonomy_id: "tax-1",
  key: "note-8#1",
  text: "Two relationship types say the same thing.",
  note_ref: "note-8",
  note_source: "maintainer",
  note_text: null,
  subject_id: "cls-actor",
  affected_ids: [],
  unresolved_refs: [],
  triage: null,
  verdict: {
    validity: "works_as_designed",
    category: "relationship_redundant",
    severity: 0,
    fix_scope: 0,
    rationale: "They differ by direction.",
    adjudicated_by: "dr-bench-gold",
    adjudicated_at: "2026-11-02T10:00:00Z",
  },
  created_at: "2026-11-02T10:00:00Z",
  updated_at: "2026-11-02T10:00:00Z",
};

export const claimTaxonomies = [
  createTaxonomy({ id: "tax-1", identifier: "dr_spec", title: "DR spec" }),
  createTaxonomy({ id: "tax-2", identifier: "house", title: "House" }),
];

const actorClass = createClass({
  id: "cls-actor",
  identifier: "business.businessactor",
  title: "Business Actor",
  taxonomy_id: "tax-1",
});
const serviceClass = createClass({
  id: "cls-service",
  identifier: "business.businessservice",
  title: "Business Service",
  taxonomy_id: "tax-1",
});
const servesProperty = createPropertyDefinition({
  id: "prop-serves",
  identifier: "actor_serves_service",
  title: "serves",
  domain_class_id: "cls-actor",
  range_class_id: "cls-service",
});

export interface ClaimRequests {
  lists: URLSearchParams[];
  exports: URLSearchParams[];
  verdicts: Array<{ method: string; id: string; body?: unknown }>;
}

export function claimHandlers(claims: Claim[] = [claimOne, claimTwo]) {
  const requests: ClaimRequests = { lists: [], exports: [], verdicts: [] };
  const handlers = [
    http.get("*/api/taxonomies", () =>
      HttpResponse.json({ items: claimTaxonomies, total: 2, limit: 500, offset: 0 }),
    ),
    http.get("*/api/taxonomies/:taxonomyId/claims/export", ({ request }) => {
      requests.exports.push(new URL(request.url).searchParams);
      return new HttpResponse(claims.map((c) => JSON.stringify(c)).join("\n") + "\n", {
        headers: { "Content-Type": "application/x-ndjson" },
      });
    }),
    http.get("*/api/taxonomies/:taxonomyId/claims", ({ request }) => {
      const params = new URL(request.url).searchParams;
      requests.lists.push(params);
      return HttpResponse.json({ items: claims, total: claims.length, limit: 50, offset: 0 });
    }),
    http.get("*/api/claims/:claimId", ({ params }) => {
      const claim = claims.find((c) => c.id === params.claimId);
      return claim ? HttpResponse.json(claim) : HttpResponse.json({}, { status: 404 });
    }),
    http.put("*/api/claims/:claimId/verdict", async ({ params, request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      requests.verdicts.push({ method: "PUT", id: params.claimId as string, body });
      const claim = claims.find((c) => c.id === params.claimId)!;
      return HttpResponse.json({
        ...claim,
        verdict: { ...body, adjudicated_by: "user", adjudicated_at: "2026-11-09T12:00:00Z" },
      });
    }),
    http.delete("*/api/claims/:claimId/verdict", ({ params }) => {
      requests.verdicts.push({ method: "DELETE", id: params.claimId as string });
      const claim = claims.find((c) => c.id === params.claimId)!;
      return HttpResponse.json({ ...claim, verdict: null });
    }),
    http.get("*/api/classes", ({ request }) => {
      const ids = new URL(request.url).searchParams.getAll("ids");
      const items = [actorClass, serviceClass].filter((c) => ids.includes(c.id));
      return HttpResponse.json({ items, total: items.length, limit: 100, offset: 0 });
    }),
    http.get("*/api/properties", ({ request }) => {
      const ids = new URL(request.url).searchParams.getAll("ids");
      const items = [servesProperty].filter((p) => ids.includes(p.id));
      return HttpResponse.json({ items, total: items.length, limit: 100, offset: 0 });
    }),
    http.get("*/api/attribute-definitions/:id", ({ params }) =>
      params.id === "attr-name"
        ? HttpResponse.json({
            id: "attr-name",
            class_id: "cls-actor",
            identifier: "name",
            title: "Name",
            datatype: "string",
            is_required: false,
          })
        : HttpResponse.json({ detail: "not found" }, { status: 404 }),
    ),
    http.get("*/api/schemes/:id", () =>
      HttpResponse.json({ detail: "not found" }, { status: 404 }),
    ),
  ];
  return { handlers, requests };
}
