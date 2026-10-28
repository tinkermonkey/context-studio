/**
 * Test fixtures for ProposalsService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

type ChangeProposal = components["schemas"]["ChangeProposalResponse"];
type ProposedOperation = components["schemas"]["ProposedOperationResponse"];

export function createProposedOperation(overrides?: Partial<ProposedOperation>): ProposedOperation {
  return {
    id: "op-1",
    seq: 1,
    op: "update",
    kind: "class",
    target_id: "class-1",
    fields: { description: "Any room" },
    base: { description: "A room" },
    evidence: [],
    scope: "editorial",
    status: "pending",
    stale: false,
    ...overrides,
  };
}

export function createChangeProposal(overrides?: Partial<ChangeProposal>): ChangeProposal {
  return {
    id: "proposal-1",
    taxonomy_id: "tax-1",
    title: "Clearer rooms",
    source: "mcp",
    created_at: "2026-10-28T12:00:00Z",
    status: "open",
    operations: [createProposedOperation()],
    ...overrides,
  };
}
