import { useQueries } from "@tanstack/react-query";
import { Button, FormCallout, Panel } from "@tinkermonkey/heimdall-ui";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type {
  ChangeProposal,
  ChangeProposalRevertConflict,
  RevertBlocker,
} from "@/api/services/proposals";
import { EntityLink } from "@/components/entity/EntityLink";
import type { EntityKind } from "@/lib/entityPaths";
import { operationSubject } from "./proposalModel";
import "./proposals.css";

const PAGE_KINDS: Record<string, EntityKind> = {
  taxonomy: "taxonomy",
  concept_scheme: "scheme",
  scheme: "scheme",
  class: "class",
  individual: "individual",
};

/**
 * A blocker's dependent, linked to its entity page. A relationship has no page
 * of its own, so it links to its source individual's.
 */
function Dependent({
  blocker,
  sourceOf,
}: {
  blocker: RevertBlocker;
  sourceOf: Map<string, string>;
}) {
  const label = blocker.dependent_id;
  const kind = PAGE_KINDS[blocker.kind];
  if (kind) {
    return (
      <EntityLink kind={kind} id={blocker.dependent_id} className="entity-link revert-conflict__id">
        {label}
      </EntityLink>
    );
  }
  const source = blocker.kind === "relationship" ? sourceOf.get(blocker.dependent_id) : undefined;
  return source ? (
    <EntityLink kind="individual" id={source} className="entity-link revert-conflict__id">
      {label}
    </EntityLink>
  ) : (
    <span className="revert-conflict__id">{label}</span>
  );
}

interface RevertConflictProps {
  proposal: ChangeProposal;
  conflict: ChangeProposalRevertConflict;
  onDismiss: () => void;
}

/**
 * Why a revert was refused (409): entities made after the proposal depend on
 * ones it created. Nothing was changed; it names each dependent (linked to its
 * page) and the created entity it points at, and what to do first.
 */
export function RevertConflict({ proposal, conflict, onDismiss }: RevertConflictProps) {
  const blocking = conflict.blocking ?? [];
  const relationshipIds = blocking
    .filter((b) => b.kind === "relationship")
    .map((b) => b.dependent_id);
  const relationships = useQueries({
    queries: relationshipIds.map((id) => ({
      queryKey: [...QUERY_KEYS.relationshipsRoot, "by-id", id],
      queryFn: () => ontologyService.getRelationship(id),
    })),
  });
  const sourceOf = new Map(
    relationships.flatMap((r) => (r.data ? [[r.data.id, r.data.source_id] as const] : [])),
  );
  const createdBy = new Map(
    proposal.operations
      .filter((o) => o.status === "applied" && o.result_entity_id)
      .map((o) => [o.result_entity_id as string, operationSubject(o)]),
  );
  const count = blocking.length;

  return (
    <Panel
      title="Revert blocked"
      subtitle="Nothing was changed"
      headerAction={
        <Button variant="ghost" size="sm" onClick={onDismiss} data-testid="revert-conflict-dismiss">
          Close
        </Button>
      }
      data-testid="revert-conflict"
    >
      <div className="stack-lg">
        <FormCallout variant="error" icon="lock" data-testid="revert-conflict-message">
          {count > 0
            ? `Can't revert ${proposal.title}. ${count} ${count === 1 ? "entity" : "entities"} made after it ${count === 1 ? "depends" : "depend"} on what it created. Nothing was changed.`
            : `Can't revert ${proposal.title}: ${conflict.message} Nothing was changed.`}
        </FormCallout>
        {count > 0 && (
          <table className="revert-conflict__table" data-testid="revert-conflict-blockers">
            <thead>
              <tr>
                <th scope="col">Depends</th>
                <th scope="col">On what it created</th>
              </tr>
            </thead>
            <tbody>
              {blocking.map((b) => (
                <tr key={`${b.kind}-${b.dependent_id}-${b.referenced_id}`}>
                  <td>
                    <span className="revert-conflict__kind">{b.kind}</span>{" "}
                    <Dependent blocker={b} sourceOf={sourceOf} />
                  </td>
                  <td>
                    {createdBy.get(b.referenced_id) && (
                      <span className="revert-conflict__created">
                        {createdBy.get(b.referenced_id)}{" "}
                      </span>
                    )}
                    <span className="revert-conflict__id">{b.referenced_id}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="revert-conflict__advice">
          {count > 0
            ? "Remove or retype those first (each links to its page), or revert the later proposal that made them. Then revert this one again."
            : "Undo whatever changed the entities this proposal touched, then revert it again."}
        </p>
      </div>
    </Panel>
  );
}
