import { useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Panel, StatGrid, StatTile, Table, type Column } from "@tinkermonkey/heimdall-ui";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useSchemeCounts } from "@/api/hooks/ontology/useContentCounts";
import { SMALL_SET_LIMIT } from "@/api/config";
import { EntityNavigator } from "@/components/entity/EntityNavigator";
import { EntityLink } from "@/components/entity/EntityLink";
import {
  EntityActions,
  EntityBody,
  EntityEyebrow,
  EntityHeader,
  EntityPageError,
  EntityPageLayout,
  IdentityCard,
  formatCount,
  formatDate,
  TableEmpty,
} from "@/components/entity/EntityPageParts";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { entityPath } from "@/lib/entityPaths";

interface SchemeRow {
  id: string;
  title: string;
  identifier: string;
  classes?: number;
  individuals?: number;
  relationshipTypes?: number;
}

const schemeColumns: Column<SchemeRow>[] = [
  {
    key: "title",
    label: "Scheme",
    width: "220px",
    render: (_, row) => (
      <EntityLink kind="scheme" id={row.id} data-testid={`taxonomy-scheme-link-${row.id}`}>
        {row.title}
      </EntityLink>
    ),
  },
  {
    key: "identifier",
    label: "Identifier",
    render: (value) => <span className="entity-muted-cell mono">{value as string}</span>,
  },
  {
    key: "classes",
    label: "Classes",
    width: "90px",
    render: (value) => <span className="entity-count-cell">{formatCount(value as number)}</span>,
  },
  {
    key: "individuals",
    label: "Individuals",
    width: "100px",
    render: (value) => <span className="entity-count-cell">{formatCount(value as number)}</span>,
  },
  {
    key: "relationshipTypes",
    label: "Relationship types",
    width: "150px",
    render: (value) => <span className="entity-count-cell">{formatCount(value as number)}</span>,
  },
];

export function TaxonomyPage({ id }: { id: string }) {
  const navigate = useNavigate();
  const { data: taxonomy, error, refetch } = useTaxonomy(id);
  const { data: schemesResponse } = useSchemes(id, { limit: SMALL_SET_LIMIT, sort_by: "title" });
  const { data: counts } = useSchemeCounts(id);

  const schemes = useMemo(() => schemesResponse?.items ?? [], [schemesResponse]);
  const countsByScheme = useMemo(
    () => new Map((counts ?? []).map((c) => [c.scheme_id, c])),
    [counts],
  );
  const rows: SchemeRow[] = schemes.map((scheme) => {
    const c = countsByScheme.get(scheme.id);
    return {
      id: scheme.id,
      title: scheme.title,
      identifier: scheme.identifier,
      classes: c?.class_count,
      individuals: c?.individual_count,
      relationshipTypes: c?.property_definition_count,
    };
  });
  const sum = (pick: (c: NonNullable<typeof counts>[number]) => number) =>
    counts ? counts.reduce((total, c) => total + pick(c), 0) : undefined;

  usePageBreadcrumbs(
    entityPath("taxonomy", id),
    taxonomy
      ? [{ label: "Schema", to: "/app/schema/taxonomies" }, { label: taxonomy.title }]
      : null,
  );

  const navigator = <EntityNavigator selectedId={id} expandIds={[id]} />;

  if (error) {
    return (
      <EntityPageLayout navigator={navigator} data-testid="taxonomy-page">
        <EntityPageError kind="Taxonomy" error={error} onRetry={() => refetch()} />
      </EntityPageLayout>
    );
  }

  if (!taxonomy) {
    return (
      <EntityPageLayout navigator={navigator} data-testid="taxonomy-page">
        <div className="skeleton entity-page__skeleton" aria-busy="true" />
      </EntityPageLayout>
    );
  }

  return (
    <EntityPageLayout navigator={navigator} data-testid="taxonomy-page">
      <EntityHeader
        eyebrow={
          <EntityEyebrow
            parts={["Schema", "Taxonomy"]}
            status={taxonomy.status}
            version={taxonomy.version}
          />
        }
        title={taxonomy.title}
        identifier={taxonomy.identifier}
        description={taxonomy.description}
        actions={
          <EntityActions
            entity={{ kind: "taxonomy", id, title: taxonomy.title }}
            graph={{ layers: schemes.map((s) => s.id) }}
            create={{
              label: "New concept scheme",
              onClick: () =>
                navigate({ to: "/app/schema/schemes", search: { createForTaxonomy: id } }),
            }}
          />
        }
      />

      <StatGrid columns={4} data-testid="entity-stats">
        <StatTile
          label="CONCEPT SCHEMES"
          value={formatCount(schemesResponse?.total)}
          color="cyan"
        />
        <StatTile label="CLASSES" value={formatCount(sum((c) => c.class_count))} color="violet" />
        <StatTile
          label="RELATIONSHIP TYPES"
          value={formatCount(sum((c) => c.property_definition_count))}
          color="amber"
          meta="property definitions"
        />
        <StatTile
          label="INDIVIDUALS"
          value={formatCount(sum((c) => c.individual_count))}
          color="emerald"
        />
      </StatGrid>

      <EntityBody
        identity={
          <IdentityCard
            rows={[
              { key: "id", value: <span className="mono">{taxonomy.id}</span> },
              { key: "identifier", value: <span className="mono">{taxonomy.identifier}</span> },
              { key: "status", value: taxonomy.status },
              { key: "version", value: String(taxonomy.version) },
              { key: "created", value: formatDate(taxonomy.created_at) },
              { key: "modified", value: formatDate(taxonomy.last_modified) },
            ]}
          />
        }
      >
        <Panel
          title={`Concept schemes · ${formatCount(schemesResponse?.total)}`}
          subtitle="Open a scheme to see its classes"
          noPadding
          data-testid="taxonomy-schemes-panel"
        >
          <Table
            rowKey="id"
            columns={schemeColumns}
            data={rows}
            onRowClick={(row) => navigate({ to: entityPath("scheme", row.id) })}
            emptyState={<TableEmpty loaded={!!schemesResponse}>No concept schemes yet.</TableEmpty>}
          />
        </Panel>
      </EntityBody>
    </EntityPageLayout>
  );
}

function TaxonomyRoute() {
  const { id } = Route.useParams();
  return <TaxonomyPage id={id} />;
}

export const Route = createFileRoute("/app/schema/taxonomies_/$id")({
  component: TaxonomyRoute,
});
