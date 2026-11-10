import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Chip,
  FilterDropdown,
  Icon,
  PageHeader,
  SegmentedControl,
  Table,
  type Column,
} from "@tinkermonkey/heimdall-ui";
import { SMALL_SET_LIMIT, LIST_PAGE_SIZES } from "@/api/config";
import { useClaim, useClaims, useExportClaims } from "@/api/hooks/claims";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import type { Claim } from "@/api/services/claims";
import { ListPager } from "@/components/crud/ListPager";
import { EntitySearchPicker } from "@/components/pipeline/EntitySearchPicker";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import { downloadText } from "@/lib/download";
import {
  FIX_SCOPE_LABELS,
  SEVERITY_LABELS,
  VALIDITIES,
  VALIDITY_LABELS,
  VALIDITY_VARIANT,
  apiFilters,
  formatProbability,
  formatScore,
  isValidity,
  triageConfidence,
  type ClaimsSearch,
  type TriageFilter,
  type VerdictFilter,
} from "./claimModel";
import { ClaimInspector } from "./ClaimInspector";
import { useClaimEntities, type ClaimEntity } from "./useClaimEntities";
import "./claims.css";

const ALL = "all";
const DEFAULT_PAGE_SIZE: number = LIST_PAGE_SIZES[0];

const TRIAGE_OPTIONS = [
  { value: ALL, label: "All" },
  { value: "triaged", label: "Triaged" },
  { value: "untriaged", label: "Untriaged" },
];

const VERDICT_OPTIONS = [
  { value: ALL, label: "All" },
  { value: "with", label: "With verdict" },
  { value: "without", label: "No verdict" },
];

/** A table row: the claim, with its subject resolved for display. */
interface ClaimRow {
  id: string;
  claim: Claim;
  subject?: ClaimEntity;
  triage: Claim["triage"];
  severity: string;
  fixScope: string;
  verdict: Claim["verdict"];
}

const columns: Column<ClaimRow>[] = [
  {
    key: "claim",
    label: "Claim",
    render: (_, { claim }) => (
      <div className="claim-cell" data-testid={`claim-row-${claim.id}`}>
        <span className="claim-cell__text">{claim.text}</span>
        <span className="claim-cell__key">{claim.key}</span>
      </div>
    ),
  },
  {
    key: "subject",
    label: "Subject",
    width: "150px",
    render: (_, { claim, subject }) =>
      claim.subject_id ? (
        <span
          className="claim-cell__subject"
          title={subject ? `${subject.label} — ${subject.title}` : claim.subject_id}
        >
          {subject?.label ?? claim.subject_id}
        </span>
      ) : (
        <span className="entity-muted-cell">—</span>
      ),
  },
  {
    key: "triage",
    label: "Triage",
    width: "170px",
    render: (_, { claim }) =>
      claim.triage ? (
        <div className="claim-cell__triage" data-testid={`claim-triage-cell-${claim.id}`}>
          <Chip variant={VALIDITY_VARIANT[claim.triage.validity]}>
            {VALIDITY_LABELS[claim.triage.validity]}
          </Chip>
          <span className="claim-cell__p">p {formatProbability(triageConfidence(claim))}</span>
        </div>
      ) : (
        <span className="entity-muted-cell">untriaged</span>
      ),
  },
  {
    key: "severity",
    label: "Severity · fix",
    width: "130px",
    render: (_, { severity, fixScope }) => (
      <div className="claim-cell">
        <span className="claim-cell__score" title="Severity">
          {severity}
        </span>
        <span className="claim-cell__score" title="Fix scope">
          {fixScope}
        </span>
      </div>
    ),
  },
  {
    key: "verdict",
    label: "Verdict",
    width: "140px",
    render: (_, { claim }) =>
      claim.verdict ? (
        <Chip
          variant={VALIDITY_VARIANT[claim.verdict.validity]}
          title={`by ${claim.verdict.adjudicated_by}`}
          data-testid={`claim-verdict-cell-${claim.id}`}
        >
          {VALIDITY_LABELS[claim.verdict.validity]}
        </Chip>
      ) : (
        <span className="entity-muted-cell">—</span>
      ),
  },
];

const columnsBesideInspector = columns.filter((column) => column.key !== "subject");

interface ClaimsPageProps {
  search: ClaimsSearch;
  /** Replace the URL's filters and selection. */
  onSearchChange: (search: ClaimsSearch) => void;
}

/**
 * A taxonomy's claims, filtered on the server and paged: work through them in
 * the inspector, recording verdicts that become benchmark gold. Export JSONL
 * downloads every claim that matches the filters.
 */
export function ClaimsPage({ search, onSearchChange }: ClaimsPageProps) {
  const { toast } = useToasts();
  const { taxonomy: taxonomyId, selected } = search;
  const filters = apiFilters(search);
  // The page starts over whenever the taxonomy or a filter changes.
  const filterKey = JSON.stringify({ taxonomyId, ...filters });
  const [paging, setPaging] = useState({ filterKey, offset: 0, limit: DEFAULT_PAGE_SIZE });
  const page = {
    limit: paging.limit,
    offset: paging.filterKey === filterKey ? paging.offset : 0,
  };

  const { data: taxonomies } = useTaxonomies({ limit: SMALL_SET_LIMIT });
  const taxonomyItems = useMemo(() => taxonomies?.items ?? [], [taxonomies]);
  const taxonomy = taxonomyItems.find((t) => t.id === taxonomyId);
  const taxonomyLabel = taxonomy ? taxonomy.identifier || taxonomy.title : taxonomyId;
  const taxonomyRef = useMemo(
    () => (taxonomyId ? { id: taxonomyId, label: taxonomyLabel ?? taxonomyId } : undefined),
    [taxonomyId, taxonomyLabel],
  );

  const { data, isLoading, error, refetch } = useClaims(taxonomyId, { ...filters, ...page });
  const claims = useMemo(() => data?.items ?? [], [data]);
  const total = data?.total ?? 0;
  // A verdict can empty the last page (it leaves a "No verdict" list): step back
  // to the last page that still has claims.
  const pastTheEnd = !!data && data.items.length === 0 && page.offset > 0 && total > 0;
  useEffect(() => {
    if (pastTheEnd) {
      const lastPage = Math.floor((total - 1) / page.limit) * page.limit;
      setPaging({ filterKey, offset: lastPage, limit: page.limit });
    }
  }, [pastTheEnd, total, page.limit, filterKey]);
  // The selected claim stays open when a verdict moves it out of the filters or the page.
  const { data: selectedClaim } = useClaim(selected);
  const layoutData = useMemo(
    () =>
      selectedClaim && !claims.some((c) => c.id === selectedClaim.id)
        ? [...claims, selectedClaim]
        : claims,
    [claims, selectedClaim],
  );

  const subjectIds = useMemo(
    () => [
      ...new Set(
        [...claims.map((c) => c.subject_id), search.subject].filter((id): id is string => !!id),
      ),
    ],
    [claims, search.subject],
  );
  const subjects = useClaimEntities(subjectIds, taxonomyRef);
  const rows: ClaimRow[] = claims.map((claim) => ({
    id: claim.id,
    claim,
    subject: claim.subject_id ? subjects.get(claim.subject_id) : undefined,
    triage: claim.triage,
    severity: formatScore(claim.triage?.severity, SEVERITY_LABELS),
    fixScope: formatScore(claim.triage?.fix_scope, FIX_SCOPE_LABELS),
    verdict: claim.verdict,
  }));

  const exportClaims = useExportClaims();
  const handleExport = () => {
    if (!taxonomyId) return;
    exportClaims.mutate(
      { taxonomyId, filters },
      {
        onSuccess: (text) => {
          downloadText(`claims-${taxonomyLabel}.jsonl`, text, "application/x-ndjson");
          toast("success", "Claims exported");
        },
      },
    );
  };

  const update = (change: Partial<ClaimsSearch>) => onSearchChange({ ...search, ...change });

  return (
    <div className="stack-lg" data-testid="claims-page">
      <PageHeader
        eyebrow="VERSIONING · claim"
        title="Claims"
        idChip="/app/claims"
        subtitle="Atomic statements split from reviewer and maintainer notes about a taxonomy, with a decision model's triage. Your verdicts are benchmark gold; claims change nothing in the taxonomy."
        actions={
          <Button
            variant="ghost"
            onClick={handleExport}
            disabled={!taxonomyId || exportClaims.isPending}
            data-testid="claims-export-button"
          >
            <Icon name="download" size={13} /> Export JSONL
          </Button>
        }
      />

      <div className="claims-filters" data-testid="claims-filters">
        <div className="claims-filters__controls">
          <FilterDropdown
            mode="radio"
            value={taxonomyId ? [taxonomyId] : []}
            onChange={(values) =>
              onSearchChange({ taxonomy: values[0] || undefined, selected: undefined })
            }
          >
            <FilterDropdown.Trigger
              label="Taxonomy"
              summary={taxonomyLabel ?? "Choose…"}
              data-testid="claims-taxonomy-filter"
            />
            <FilterDropdown.Panel>
              <FilterDropdown.Section>
                {taxonomyItems.map((t) => (
                  <FilterDropdown.Radio
                    key={t.id}
                    value={t.id}
                    label={t.identifier || t.title}
                    description={t.identifier ? t.title : undefined}
                  />
                ))}
              </FilterDropdown.Section>
            </FilterDropdown.Panel>
          </FilterDropdown>

          <FilterDropdown
            mode="radio"
            value={[search.validity ?? ALL]}
            onChange={(values) =>
              update({ validity: isValidity(values[0]) ? values[0] : undefined })
            }
          >
            <FilterDropdown.Trigger
              label="Triage validity"
              summary={search.validity ? VALIDITY_LABELS[search.validity] : "Any"}
              disabled={!taxonomyId}
              data-testid="claims-validity-filter"
            />
            <FilterDropdown.Panel>
              <FilterDropdown.Section>
                <FilterDropdown.Radio value={ALL} label="Any" />
                {VALIDITIES.map((v) => (
                  <FilterDropdown.Radio key={v} value={v} label={VALIDITY_LABELS[v]} />
                ))}
              </FilterDropdown.Section>
            </FilterDropdown.Panel>
          </FilterDropdown>

          <SegmentedControl
            value={search.triage ?? ALL}
            onChange={(value) =>
              update({ triage: value === ALL ? undefined : (value as TriageFilter) })
            }
            options={TRIAGE_OPTIONS}
            disabled={!taxonomyId}
            aria-label="Triage"
            data-testid="claims-triage-filter"
          />
          <SegmentedControl
            value={search.verdict ?? ALL}
            onChange={(value) =>
              update({ verdict: value === ALL ? undefined : (value as VerdictFilter) })
            }
            options={VERDICT_OPTIONS}
            disabled={!taxonomyId}
            aria-label="Verdict"
            data-testid="claims-verdict-filter"
          />
          <div className="claims-filters__subject">
            <EntitySearchPicker
              entityType="Class"
              selectedId={search.subject}
              onSelect={(entity) => update({ subject: entity?.id })}
              placeholder="Subject…"
              disabled={!taxonomyId}
              data-testid="claims-subject-filter"
            />
          </div>
        </div>
        {taxonomyId && (
          <span className="claims-count" data-testid="claims-count">
            {total} {total === 1 ? "claim" : "claims"}
          </span>
        )}
      </div>

      {!taxonomyId ? (
        <p className="entity-note" data-testid="claims-pick-taxonomy">
          Choose a taxonomy to work through its claims.
        </p>
      ) : error ? (
        <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load claims" />
      ) : (
        <SchemaPageLayout
          data={layoutData}
          selectedId={selected}
          renderInspectorContent={(claim) => (
            <ClaimInspector
              key={claim.id}
              claim={selectedClaim?.id === claim.id ? selectedClaim : claim}
              taxonomy={taxonomyRef}
              onClose={() => update({ selected: undefined })}
            />
          )}
        >
          <div className="schema-table-wrap" data-testid="claims-table">
            <Table<ClaimRow>
              rowKey="id"
              // The inspector shows the subject, so the narrower table drops it
              columns={selected ? columnsBesideInspector : columns}
              data={rows}
              selectedRows={selected ? [selected] : []}
              onRowClick={(row) => update({ selected: row.id })}
              emptyState={
                <span className="entity-note" data-testid="claims-empty">
                  {isLoading ? "Loading…" : "No claims match these filters."}
                </span>
              }
            />
            <ListPager
              total={total}
              limit={page.limit}
              offset={page.offset}
              pageSizes={LIST_PAGE_SIZES}
              onPageChange={(offset) => setPaging({ filterKey, offset, limit: page.limit })}
              onPageSizeChange={(limit) => setPaging({ filterKey, offset: 0, limit })}
            />
          </div>
        </SchemaPageLayout>
      )}
    </div>
  );
}
