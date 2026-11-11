import { Chip } from "@tinkermonkey/heimdall-ui";
import { useEntitySources, type ProvenanceKind } from "@/api/hooks/ontology/useEntitySources";
import { useSourcesByIds } from "@/api/hooks/sources/useSource";
import { ProposalLink } from "@/components/proposals/ProposalLink";
import { charsLabel, pageLabel } from "@/components/proposals/sourceModel";
import { formatDate } from "@/components/entity/EntityPageParts";
import { SourcesPageLink } from "@/components/sources/SourcesPageLink";
import "./EntitySources.css";

interface EntitySourcesProps {
  kind: ProvenanceKind;
  id: string;
}

/** "3 passages in 2 sources" */
export function passagesSummary(passages: number, sources: number): string {
  return `${passages} passage${passages === 1 ? "" : "s"} in ${sources} source${sources === 1 ? "" : "s"}`;
}

/**
 * Where an individual or relationship came from: each source passage a
 * proposal applied it from, with its source, page, quote and the proposal.
 */
export function EntitySources({ kind, id }: EntitySourcesProps) {
  const { data: passages, isLoading, isError } = useEntitySources(kind, id);
  const sources = useSourcesByIds((passages ?? []).map((p) => p.source_id));

  if (isLoading) {
    return (
      <p className="entity-note" aria-busy="true" data-testid="entity-sources-loading">
        Loading sources…
      </p>
    );
  }
  if (isError) {
    return (
      <p className="entity-note" data-testid="entity-sources-error">
        The sources couldn&apos;t be loaded.
      </p>
    );
  }
  if (!passages || passages.length === 0) {
    return (
      <p className="entity-note" data-testid="entity-sources-empty">
        No source passages. They are recorded when a proposal applies this {kind} from a source.
      </p>
    );
  }

  const sourceCount = new Set(passages.map((p) => p.source_id)).size;
  return (
    <div className="entity-sources" data-testid="entity-sources">
      <p className="entity-sources__summary" data-testid="entity-sources-summary">
        {passagesSummary(passages.length, sourceCount)} · written when a proposal applies
      </p>
      <ul className="entity-sources__list" aria-label="Source passages">
        {passages.map((passage) => {
          const source = sources.get(passage.source_id);
          const where = [pageLabel(passage.page ?? null), charsLabel(passage)]
            .filter(Boolean)
            .join(" · ");
          return (
            <li
              key={passage.id}
              className="entity-source"
              data-testid={`entity-source-row-${passage.id}`}
            >
              <div className="entity-source__head">
                {source && <Chip form="id-tag">{source.kind}</Chip>}
                {/* A listed source links to its taxonomy's Sources page; a removed
                    or unreadable one isn't listed there, so it stays text. */}
                {source && !source.removed_at ? (
                  <SourcesPageLink
                    taxonomyId={source.taxonomy_id}
                    className="entity-link entity-source__title"
                    data-testid={`entity-source-title-${passage.id}`}
                  >
                    {source.title}
                  </SourcesPageLink>
                ) : (
                  <span
                    className="entity-source__title"
                    data-testid={`entity-source-title-${passage.id}`}
                  >
                    {source?.title ?? `Source ${passage.source_id.slice(0, 8)}`}
                  </span>
                )}
                <span className="entity-source__where">{where}</span>
                {source?.removed_at && <Chip variant="neutral">removed source</Chip>}
              </div>
              {passage.quote && (
                <blockquote className="entity-source__quote">{passage.quote}</blockquote>
              )}
              <span className="entity-source__via">
                proposal{" "}
                <ProposalLink
                  proposalId={passage.proposal_id}
                  data-testid={`entity-source-proposal-${passage.id}`}
                >
                  {passage.proposal_id.slice(0, 8)}
                </ProposalLink>{" "}
                op #{passage.op_seq} · {formatDate(passage.created_at)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
