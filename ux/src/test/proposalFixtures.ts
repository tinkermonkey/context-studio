/**
 * A review-queue proposal on the entity page ontology (see entityPageHandlers):
 * "proposal-1" on taxonomy "tax-1" renames prop-1 (Component realizes Service),
 * deletes it (stale), creates Service uses Component (applied) and edits the
 * Component class's description; "proposal-2" is done.
 */
import { http, HttpResponse } from "msw";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";

export const renameOperation = createProposedOperation({
  id: "op-rename",
  seq: 1,
  op: "update",
  kind: "property",
  target_id: "prop-1",
  fields: {
    canonical_predicate: "serves",
    identifier: "component_serves_service",
  },
  base: {
    canonical_predicate: "realizes",
    identifier: "component_realizes_service",
  },
  rationale: "Rename the predicate. Plan kind rename-predicate, p 0.82; claims node:x#3.",
  evidence: [
    { quote: "realizes and serves say the same thing here.", claim_id: "node:x#3" },
    { quote: "See the spec.", url: "https://example.com/spec" },
  ],
  probability: 0.819,
  scope: "breaking",
  status: "pending",
});

export const deleteOperation = createProposedOperation({
  id: "op-delete",
  seq: 2,
  op: "delete",
  kind: "property",
  target_id: "prop-1",
  fields: {},
  base: {
    id: "prop-1",
    identifier: "component_realizes_service",
    title: "application.component realizes application.service",
    canonical_predicate: "realizes",
    domain_class_id: "class-1",
    range_class_id: "class-2",
    version: 3,
  },
  rationale: "Remove it. Plan kind reverse, p 0.41.",
  evidence: [],
  probability: 0.407,
  scope: "breaking",
  status: "pending",
  stale: true,
});

export const createOperation = createProposedOperation({
  id: "op-create",
  seq: 3,
  op: "create",
  kind: "property",
  target_id: null,
  ref: "c1",
  fields: {
    identifier: "service_uses_component",
    canonical_predicate: "uses",
    domain_class_id: "class-2",
    range_class_id: "class-1",
  },
  base: {},
  rationale: "Needed for CBM edges.",
  evidence: [],
  probability: null,
  scope: "additive",
  status: "applied",
});

export const classOperation = createProposedOperation({
  id: "op-class",
  seq: 4,
  op: "update",
  kind: "class",
  target_id: "class-1",
  fields: { description: "A deployable part" },
  base: { description: "Modular, deployable part of a system" },
  rationale: null,
  evidence: [],
  probability: 0.9,
  scope: "editorial",
  status: "pending",
});

export const openProposal = createChangeProposal({
  id: "proposal-1",
  taxonomy_id: "tax-1",
  title: "DR reflection plan: application layer",
  rationale: "Relationship schemas the triage wants changed.",
  source: "pipeline",
  source_detail: "documentation_robotics proposal-export.ts",
  created_at: new Date(Date.now() - 6 * 24 * 3600 * 1000).toISOString(),
  status: "open",
  operations: [renameOperation, deleteOperation, createOperation, classOperation],
});

export const doneProposal = createChangeProposal({
  id: "proposal-2",
  taxonomy_id: "tax-2",
  title: "Sharpen a definition",
  source: "mcp",
  source_detail: "Claude Code",
  created_at: new Date(Date.now() - 3 * 3600 * 1000).toISOString(),
  status: "done",
  operations: [createProposedOperation({ id: "op-done", status: "applied", scope: "additive" })],
});

const PROPOSALS = [openProposal, doneProposal];

export const DECIDED_AT = "2026-11-06T12:53:08+00:00";

/** A gold list page for the decided operations among `operations`, all decided by the user at DECIDED_AT. */
export function goldPage(operations: ProposedOperation[]) {
  const items = operations
    .filter((o) => o.status === "applied" || o.status === "rejected")
    .map((o) => ({
      id: `gold-${o.id}`,
      operation_id: o.id,
      proposal_id: "proposal-1",
      taxonomy_id: "tax-1",
      seq: o.seq,
      kind: o.kind,
      op: o.op,
      decision: o.status === "rejected" ? "rejected" : "applied",
      decided_at: DECIDED_AT,
      decided_by: "user",
      proposed: {},
    }));
  return { items, total: items.length, limit: 500, offset: 0 };
}

/**
 * GET /api/proposals (status and taxonomy_id filters), GET /api/proposals/:id
 * and GET /api/taxonomies/:id/gold?proposal_id= (each decided operation decided by the user at DECIDED_AT).
 */
export const proposalHandlers = [
  http.get("*/api/taxonomies/:id/gold", ({ request }) => {
    const proposalId = new URL(request.url).searchParams.get("proposal_id");
    const proposal = PROPOSALS.find((p) => p.id === proposalId);
    return HttpResponse.json(goldPage(proposal?.operations ?? []));
  }),
  http.get("*/api/proposals/:id", ({ params }) => {
    const proposal = PROPOSALS.find((p) => p.id === params.id);
    return proposal
      ? HttpResponse.json(proposal)
      : HttpResponse.json({ detail: "Change proposal not found" }, { status: 404 });
  }),
  http.get("*/api/proposals", ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const taxonomyId = url.searchParams.get("taxonomy_id");
    const landed = url.searchParams.get("landed");
    const items = PROPOSALS.filter(
      (p) =>
        (!status || p.status === status) &&
        (!taxonomyId || p.taxonomy_id === taxonomyId) &&
        (landed === null || !!p.landed === (landed === "true")),
    );
    return HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });
  }),
];
