/**
 * Test fixtures for ProposalsService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

type ChangeProposal = components["schemas"]["ChangeProposalResponse"];
type ProposedOperation = components["schemas"]["ProposedOperationResponse"];
type OperationCount = components["schemas"]["OperationCountResponse"];

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
    matched: false,
    stale: false,
    no_passage: false,
    added_by_reviewer: false,
    ...overrides,
  };
}

/** A proposal; its `counts` follow its operations unless given. */
export function createChangeProposal(overrides?: Partial<ChangeProposal>): ChangeProposal {
  const proposal: ChangeProposal = {
    id: "proposal-1",
    taxonomy_id: "tax-1",
    title: "Clearer rooms",
    source: "mcp",
    created_at: "2026-10-28T12:00:00Z",
    status: "open",
    dry_run: false,
    operations: [createProposedOperation()],
    counts: [],
    ...overrides,
  };
  return overrides?.counts ? proposal : { ...proposal, counts: countsOf(proposal.operations) };
}

/** The server's counts for these operations: one entry per op, kind, status and scope. */
export function countsOf(operations: ProposedOperation[]): OperationCount[] {
  const byKey = new Map<string, OperationCount>();
  for (const { op, kind, status, scope } of operations) {
    const key = [op, kind, status, scope].join("|");
    const entry = byKey.get(key) ?? { op, kind, status, scope, count: 0 };
    entry.count += 1;
    byKey.set(key, entry);
  }
  return [...byKey.values()];
}
