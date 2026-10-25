import { useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Panel, StatGrid, StatTile, Table, type Column } from "@tinkermonkey/heimdall-ui";
import { useScheme } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useClassCounts, useSchemeCounts } from "@/api/hooks/ontology/useContentCounts";
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
  IdentitySection,
  formatCount,
  formatDate,
  TableEmpty,
} from "@/components/entity/EntityPageParts";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { entityPath } from "@/lib/entityPaths";

interface ClassRow {
  id: string;
  title: string;
  description: string;
  individuals?: number;
}

const classColumns: Column<ClassRow>[] = [
  {
    key: "title",
    label: "Class",
    width: "200px",
    render: (_, row) => (
      <EntityLink kind="class" id={row.id} data-testid={`scheme-class-link-${row.id}`}>
        {row.title}
      </EntityLink>
    ),
  },
  {
    key: "description",
    label: "Definition",
    render: (value) => <span className="entity-muted-cell">{(value as string) || "—"}</span>,
  },
  {
    key: "individuals",
    label: "Individuals",
    width: "100px",
    render: (value) => <span className="entity-count-cell">{formatCount(value as number)}</span>,
  },
];

export function SchemePage({ id }: { id: string }) {
  const navigate = useNavigate();
  const { data: scheme, error, refetch } = useScheme(id);
  const { data: taxonomy } = useTaxonomy(scheme?.taxonomy_id ?? "");
  const { data: classesResponse } = useClasses({
    concept_scheme_id: id,
    limit: SMALL_SET_LIMIT,
    sort_by: "title",
  });
  const { data: classCounts } = useClassCounts(id);
  // Distinct individuals for the scheme (an individual can have several of its classes).
  const { data: schemeCounts } = useSchemeCounts(scheme?.taxonomy_id);

  const countsByClass = useMemo(
    () => new Map((classCounts ?? []).map((c) => [c.class_id, c])),
    [classCounts],
  );
  const classes = classesResponse?.items ?? [];
  const rows: ClassRow[] = classes.map((cls) => ({
    id: cls.id,
    title: cls.title,
    description: cls.description ?? "",
    individuals: countsByClass.get(cls.id)?.individual_count,
  }));
  const ownCounts = schemeCounts?.find((c) => c.scheme_id === id);
  const mostConnected = [...(classCounts ?? [])].sort(
    (a, b) =>
      b.individual_count - a.individual_count || b.relationship_count - a.relationship_count,
  )[0];
  const mostConnectedClass = mostConnected && classes.find((c) => c.id === mostConnected.class_id);

  usePageBreadcrumbs(
    entityPath("scheme", id),
    scheme && taxonomy
      ? [
          { label: "Schema", to: "/app/schema/taxonomies" },
          { label: taxonomy.title, to: entityPath("taxonomy", taxonomy.id) },
          { label: scheme.title },
        ]
      : null,
  );

  const navigator = (
    <EntityNavigator selectedId={id} expandIds={scheme ? [scheme.taxonomy_id, scheme.id] : [id]} />
  );

  if (error) {
    return (
      <EntityPageLayout navigator={navigator} data-testid="scheme-page">
        <EntityPageError kind="Concept scheme" error={error} onRetry={() => refetch()} />
      </EntityPageLayout>
    );
  }

  if (!scheme) {
    return (
      <EntityPageLayout navigator={navigator} data-testid="scheme-page">
        <div className="skeleton entity-page__skeleton" aria-busy="true" />
      </EntityPageLayout>
    );
  }

  const taxonomyLink = (testId?: string) =>
    taxonomy && (
      <EntityLink kind="taxonomy" id={taxonomy.id} data-testid={testId}>
        {taxonomy.title}
      </EntityLink>
    );

  return (
    <EntityPageLayout navigator={navigator} data-testid="scheme-page">
      <EntityHeader
        eyebrow={
          <EntityEyebrow
            parts={["Schema", "Concept scheme"]}
            parent={taxonomyLink("entity-parent-link")}
            status={scheme.status}
            version={scheme.version}
          />
        }
        title={scheme.title}
        identifier={scheme.identifier}
        description={scheme.description}
        actions={
          <EntityActions
            entity={{ kind: "scheme", id, title: scheme.title }}
            graph={{ layers: [id] }}
            create={{
              label: "New class",
              onClick: () =>
                navigate({ to: "/app/schema/classes", search: { createForScheme: id } }),
            }}
          />
        }
      />

      <StatGrid columns={4} data-testid="entity-stats">
        <StatTile label="CLASSES" value={formatCount(classesResponse?.total)} color="violet" />
        <StatTile
          label="INDIVIDUALS"
          value={formatCount(ownCounts?.individual_count)}
          color="emerald"
          meta="typed by these classes"
        />
        <StatTile
          label="RELATIONSHIP TYPES"
          value={formatCount(ownCounts?.property_definition_count)}
          color="amber"
          meta="with a class here as domain"
        />
        <StatTile
          label="TAXONOMY"
          value={taxonomy?.identifier ?? "—"}
          color="cyan"
          meta={taxonomy?.title}
        />
      </StatGrid>

      <EntityBody
        identity={
          <IdentityCard
            rows={[
              { key: "id", value: <span className="mono">{scheme.id}</span> },
              { key: "identifier", value: <span className="mono">{scheme.identifier}</span> },
              { key: "taxonomy", value: taxonomyLink() ?? "—" },
              { key: "status", value: scheme.status },
              { key: "version", value: String(scheme.version) },
              { key: "created", value: formatDate(scheme.created_at) },
              { key: "modified", value: formatDate(scheme.last_modified) },
            ]}
          >
            {mostConnected && mostConnectedClass && mostConnected.individual_count > 0 && (
              <IdentitySection title="Most connected class">
                <p className="entity-note">
                  <EntityLink kind="class" id={mostConnectedClass.id}>
                    {mostConnectedClass.title}
                  </EntityLink>{" "}
                  has {mostConnected.individual_count} individuals and{" "}
                  {mostConnected.relationship_count} outgoing relationships.
                </p>
              </IdentitySection>
            )}
          </IdentityCard>
        }
      >
        <Panel
          title={`Classes · ${formatCount(classesResponse?.total)}`}
          subtitle="Sorted by title"
          noPadding
          data-testid="scheme-classes-panel"
        >
          <Table
            rowKey="id"
            columns={classColumns}
            data={rows}
            onRowClick={(row) => navigate({ to: entityPath("class", row.id) })}
            emptyState={
              <TableEmpty loaded={!!classesResponse}>No classes in this scheme yet.</TableEmpty>
            }
          />
        </Panel>
      </EntityBody>
    </EntityPageLayout>
  );
}

function SchemeRoute() {
  const { id } = Route.useParams();
  return <SchemePage id={id} />;
}

export const Route = createFileRoute("/app/schema/schemes_/$id")({
  component: SchemeRoute,
});
