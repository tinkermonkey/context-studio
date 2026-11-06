import { useMemo } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Chip,
  PageHeader,
  ProgressBar,
  SegmentedControl,
  Table,
  type Column,
} from "@tinkermonkey/heimdall-ui";
import { useChangeProposals } from "@/api/hooks/proposals";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { SMALL_SET_LIMIT } from "@/api/config";
import type { ChangeProposal } from "@/api/services/proposals";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ProposalLink } from "./ProposalLink";
import {
  PROPOSAL_STATUS_VARIANT,
  SCOPE_VARIANT,
  SOURCE_VARIANT,
  decidedPercent,
  formatAge,
  pendingLabel,
  strictestScope,
  tallyOperations,
  type ChangeScope,
  type OperationTally,
} from "./proposalModel";
import "./proposals.css";

export type ProposalStatusFilter = ChangeProposal["status"] | "all";

/** The list API's maximum page; the queue is small enough to load whole. */
const LIST_LIMIT = 500;

const STATUS_OPTIONS: Array<{ value: ProposalStatusFilter; label: string }> = [
  { value: "open", label: "Open" },
  { value: "done", label: "Done" },
  { value: "reverted", label: "Reverted" },
  { value: "all", label: "All" },
];

const ALL_TAXONOMIES = "all";

interface ProposalRow {
  id: string;
  title: string;
  sourceDetail: string;
  taxonomy: string;
  source: ChangeProposal["source"];
  status: ChangeProposal["status"];
  tally: OperationTally;
  scope?: ChangeScope;
  age: string;
}

const columns: Column<ProposalRow>[] = [
  {
    key: "title",
    label: "Proposal",
    render: (_, row) => (
      <div className="proposal-cell">
        <ProposalLink
          proposalId={row.id}
          className="entity-link proposal-cell__title"
          data-testid={`proposal-link-${row.id}`}
        >
          {row.title}
        </ProposalLink>
        {row.sourceDetail && <span className="proposal-cell__detail">{row.sourceDetail}</span>}
      </div>
    ),
  },
  {
    key: "taxonomy",
    label: "Taxonomy",
    width: "130px",
    render: (value) => <Chip form="id-tag">{value as string}</Chip>,
  },
  {
    key: "source",
    label: "Source",
    width: "110px",
    render: (value) => (
      <Chip variant={SOURCE_VARIANT[value as ChangeProposal["source"]]}>{value as string}</Chip>
    ),
  },
  {
    key: "status",
    label: "Status",
    width: "110px",
    render: (value) => (
      <Chip variant={PROPOSAL_STATUS_VARIANT[value as ChangeProposal["status"]]}>
        {value as string}
      </Chip>
    ),
  },
  {
    key: "tally",
    label: "Needs decision",
    width: "160px",
    render: (_, row) => (
      <div className="proposal-pending" data-testid={`proposal-pending-${row.id}`}>
        <span>{pendingLabel(row.tally)}</span>
        <ProgressBar
          percent={decidedPercent(row.tally)}
          color={row.tally.awaiting > 0 ? "amber" : "emerald"}
          height={4}
          label={`${row.tally.total - row.tally.awaiting} of ${row.tally.total} decided`}
        />
      </div>
    ),
  },
  {
    key: "scope",
    label: "Scope",
    width: "110px",
    render: (value) =>
      value ? <Chip variant={SCOPE_VARIANT[value as ChangeScope]}>{value as string}</Chip> : "—",
  },
  {
    key: "age",
    label: "Age",
    width: "70px",
    render: (value) => <span className="proposal-age">{value as string}</span>,
  },
];

interface ProposalsListPageProps {
  status: ProposalStatusFilter;
  /** A taxonomy id, or undefined for all. */
  taxonomyId?: string;
  onFiltersChange: (filters: { status: ProposalStatusFilter; taxonomyId?: string }) => void;
}

/**
 * The review queue: proposals filtered by status (server-side) and taxonomy,
 * with each one's pending count and strictest scope worked out from its
 * operations.
 */
export function ProposalsListPage({ status, taxonomyId, onFiltersChange }: ProposalsListPageProps) {
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useChangeProposals({
    status: status === "all" ? undefined : status,
    limit: LIST_LIMIT,
  });
  const { data: taxonomies } = useTaxonomies({ limit: SMALL_SET_LIMIT });

  const taxonomyName = useMemo(() => {
    const byId = new Map((taxonomies?.items ?? []).map((t) => [t.id, t.identifier || t.title]));
    return (id: string) => byId.get(id) ?? id;
  }, [taxonomies]);

  const proposals = useMemo(() => data?.items ?? [], [data]);
  // Offer the taxonomies that have proposals in this status, plus the selected one.
  const taxonomyIds = [...new Set(proposals.map((p) => p.taxonomy_id))];
  if (taxonomyId && !taxonomyIds.includes(taxonomyId)) taxonomyIds.push(taxonomyId);
  const taxonomyOptions = [
    { value: ALL_TAXONOMIES, label: "All taxonomies" },
    ...taxonomyIds.map((id) => ({ value: id, label: taxonomyName(id) })),
  ];

  const now = new Date();
  const rows: ProposalRow[] = proposals
    .filter((p) => !taxonomyId || p.taxonomy_id === taxonomyId)
    .map((p) => ({
      id: p.id,
      title: p.title,
      sourceDetail: p.source_detail ?? "",
      taxonomy: taxonomyName(p.taxonomy_id),
      source: p.source,
      status: p.status,
      tally: tallyOperations(p.operations),
      scope: strictestScope(p.operations),
      age: formatAge(p.created_at, now),
    }));

  return (
    <div className="stack-lg" data-testid="proposals-page">
      <PageHeader
        eyebrow="VERSIONING · change_proposal"
        title="Proposals"
        idChip="/app/proposals"
        subtitle="Changes proposed by pipelines, chat, Claude Code over MCP and bundle imports. Nothing changes the ontology until it is applied here, except what a taxonomy's approval policy applies by itself."
      />

      <div className="proposals-filters" data-testid="proposals-filters">
        <div className="proposals-filters__controls">
          <SegmentedControl
            value={status}
            onChange={(value) =>
              onFiltersChange({ status: value as ProposalStatusFilter, taxonomyId })
            }
            options={STATUS_OPTIONS}
            aria-label="Status"
            data-testid="proposals-status-filter"
          />
          <SegmentedControl
            value={taxonomyId ?? ALL_TAXONOMIES}
            onChange={(value) =>
              onFiltersChange({
                status,
                taxonomyId: value === ALL_TAXONOMIES ? undefined : String(value),
              })
            }
            options={taxonomyOptions}
            aria-label="Taxonomy"
            data-testid="proposals-taxonomy-filter"
          />
        </div>
        <span className="proposals-count" data-testid="proposals-count">
          {rows.length} of {data?.total ?? 0} proposals
        </span>
      </div>

      {error ? (
        <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load proposals" />
      ) : (
        <div className="schema-table-wrap" data-testid="proposals-table">
          <Table<ProposalRow>
            rowKey="id"
            columns={columns}
            data={rows}
            onRowClick={(row) =>
              navigate({ to: "/app/proposals/$proposalId", params: { proposalId: row.id } })
            }
            emptyState={
              <span className="entity-note" data-testid="proposals-empty">
                {isLoading ? "Loading…" : "No proposals match these filters."}
              </span>
            }
          />
        </div>
      )}

      <p className="proposals-footnote">
        Needs decision counts operations still waiting for one, failed ones included. Scope is the
        strictest scope in the proposal; breaking changes and deletes never apply by themselves.
      </p>
    </div>
  );
}
