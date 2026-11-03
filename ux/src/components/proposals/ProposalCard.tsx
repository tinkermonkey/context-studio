import { Chip } from "@tinkermonkey/heimdall-ui";
import { useChangeProposal } from "@/api/hooks/proposals";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { ProposalLink } from "./ProposalLink";
import { PROPOSAL_STATUS_VARIANT, tallyOperations } from "./proposalModel";
import "./proposals.css";

interface ProposalCardProps {
  proposalId: string;
}

/**
 * A proposal under the chat tool block that stored it: its current status and
 * counts, and a link to its review page. Chat can only propose; decisions are
 * made on the proposal page.
 */
export function ProposalCard({ proposalId }: ProposalCardProps) {
  const { data: proposal, error } = useChangeProposal(proposalId);
  const { data: taxonomy } = useTaxonomy(proposal?.taxonomy_id ?? "");

  if (error || !proposal) {
    return (
      <div className="proposal-card" data-testid="chat-proposal-card">
        <span className="proposal-card__eyebrow">Proposal</span>
        <ProposalLink proposalId={proposalId} data-testid="chat-proposal-link">
          {error ? "Open the proposal" : "Loading proposal…"}
        </ProposalLink>
      </div>
    );
  }

  const tally = tallyOperations(proposal.operations);
  const counts = [
    `${tally.total} operation${tally.total === 1 ? "" : "s"}`,
    `${tally.applied} applied`,
    `${tally.pending} pending`,
    ...(tally.failed ? [`${tally.failed} failed`] : []),
  ].join(" · ");

  return (
    <div className="proposal-card" data-testid="chat-proposal-card">
      <div className="proposal-card__head">
        <span className="proposal-card__eyebrow">Proposal</span>
        <Chip variant={PROPOSAL_STATUS_VARIANT[proposal.status]}>{proposal.status}</Chip>
        <Chip form="id-tag">{taxonomy?.identifier ?? proposal.taxonomy_id}</Chip>
      </div>
      <ProposalLink
        proposalId={proposalId}
        className="entity-link proposal-cell__title"
        data-testid="chat-proposal-link"
      >
        {proposal.title}
      </ProposalLink>
      <span className="proposal-card__counts" data-testid="chat-proposal-counts">
        {counts}
      </span>
      <div>
        <ProposalLink
          proposalId={proposalId}
          className="btn btn--primary btn--sm"
          data-testid="chat-proposal-review"
        >
          {/* Failed operations still await a decision (apply again or reject). */}
          {tally.awaiting > 0 ? `Review ${tally.awaiting}` : "Open proposal"}
        </ProposalLink>
      </div>
    </div>
  );
}
