import { useMemo, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  Button,
  Chip,
  Panel,
  StatGrid,
  StatTile,
  Table,
  TextArea,
  type Column,
} from "@tinkermonkey/heimdall-ui";
import {
  useClass,
  useClassAttributeDefinitions,
  useClassesByIds,
  useUpdateClass,
} from "@/api/hooks/ontology/useClasses";
import { useScheme, useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useIndividuals } from "@/api/hooks/ontology/useIndividuals";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useClassCounts } from "@/api/hooks/ontology/useContentCounts";
import { ApiError } from "@/api/client/interceptors";
import { SMALL_SET_LIMIT } from "@/api/config";
import { useToasts } from "@/components/ui/Toast";
import { EntityNavigator } from "@/components/entity/EntityNavigator";
import { EntityLink } from "@/components/entity/EntityLink";
import {
  EntityActions,
  EntityBody,
  EntityEyebrow,
  EntityHeader,
  EntityPageError,
  EntityPageLayout,
  ExternalReferences,
  IdentityCard,
  formatCount,
  formatDate,
  predicateLabel,
  TableEmpty,
} from "@/components/entity/EntityPageParts";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { entityPath } from "@/lib/entityPaths";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];
type AttributeDefinitionResponse = components["schemas"]["AttributeDefinitionResponse"];

/** Rows shown per section before "Show all". */
const PREVIEW_ROWS = 8;

interface IndividualRow {
  id: string;
  title: string;
  description: string;
}

interface RelationshipTypeRow {
  id: string;
  predicate: string;
  targetId?: string;
  targetTitle?: string;
  layer?: string;
}

const individualColumns: Column<IndividualRow>[] = [
  {
    key: "title",
    label: "Individual",
    width: "260px",
    render: (_, row) => (
      <EntityLink kind="individual" id={row.id} data-testid={`class-individual-link-${row.id}`}>
        {row.title}
      </EntityLink>
    ),
  },
  {
    key: "description",
    label: "Description",
    render: (value) => <span className="entity-muted-cell">{(value as string) || "—"}</span>,
  },
];

const relationshipTypeColumns: Column<RelationshipTypeRow>[] = [
  {
    key: "predicate",
    label: "Predicate",
    render: (value) => <span className="entity-predicate">{value as string}</span>,
  },
  {
    key: "targetTitle",
    label: "Target class",
    render: (_, row) =>
      row.targetId ? (
        <EntityLink kind="class" id={row.targetId}>
          {row.targetTitle ?? row.targetId}
        </EntityLink>
      ) : (
        <span className="entity-muted-cell">any</span>
      ),
  },
  {
    key: "layer",
    label: "Layer",
    render: (value) => (value ? <Chip variant="neutral">{value as string}</Chip> : "—"),
  },
];

const attributeColumns: Column<AttributeDefinitionResponse>[] = [
  {
    key: "identifier",
    label: "Identifier",
    render: (value) => <span className="mono">{value as string}</span>,
  },
  { key: "title", label: "Title" },
  {
    key: "datatype",
    label: "Type",
    width: "110px",
    render: (value) => <span className="entity-muted-cell mono">{value as string}</span>,
  },
  {
    key: "is_required",
    label: "Required",
    width: "90px",
    render: (value) => (value ? "yes" : "no"),
  },
];

function ShowAllButton({
  shown,
  total,
  onClick,
  testId,
}: {
  shown: number;
  total?: number;
  onClick: () => void;
  testId: string;
}) {
  if (total === undefined || total <= shown) return null;
  return (
    <Button variant="ghost" size="sm" onClick={onClick} data-testid={testId}>
      Show all {total}
    </Button>
  );
}

function DefinitionPanel({ cls }: { cls: ClassResponse }) {
  const { toast } = useToasts();
  const updateMutation = useUpdateClass();
  const [draft, setDraft] = useState<string | null>(null);
  const editing = draft !== null;

  const save = async () => {
    if (draft === null) return;
    const value = draft.trim();
    try {
      await updateMutation.mutateAsync({ id: cls.id, data: { description: value || null } });
      setDraft(null);
    } catch (error) {
      toast("error", error instanceof ApiError ? error.detail : "Failed to save the definition");
    }
  };

  return (
    <Panel
      title="Definition"
      data-testid="class-definition-panel"
      headerAction={
        editing ? undefined : (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDraft(cls.description ?? "")}
            data-testid="class-definition-edit"
          >
            Edit definition
          </Button>
        )
      }
    >
      {editing ? (
        <div className="stack">
          <TextArea
            aria-label="Definition"
            value={draft}
            rows={3}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            data-testid="class-definition-input"
          />
          <div className="row">
            <Button
              variant="primary"
              size="sm"
              onClick={() => void save()}
              disabled={updateMutation.isPending}
              data-testid="class-definition-save"
            >
              Save
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDraft(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="stack">
          <p className="entity-definition" data-testid="class-definition-text">
            {cls.description || "No definition yet."}
          </p>
          <p className="entity-note">
            The definition, not the title, drives matching during extraction and recognition.
          </p>
        </div>
      )}
    </Panel>
  );
}

export function ClassPage({ id }: { id: string }) {
  const navigate = useNavigate();
  const [allIndividuals, setAllIndividuals] = useState(false);
  const [allRelationshipTypes, setAllRelationshipTypes] = useState(false);

  const { data: cls, error, refetch } = useClass(id);
  const { data: scheme } = useScheme(cls?.concept_scheme_id ?? "");
  const { data: taxonomy } = useTaxonomy(cls?.taxonomy_id ?? "");
  const { data: schemesResponse } = useSchemes(undefined, { limit: SMALL_SET_LIMIT });
  const { data: classCounts } = useClassCounts(cls?.concept_scheme_id);
  const { data: individualsResponse } = useIndividuals(
    { class_id: id, limit: allIndividuals ? SMALL_SET_LIMIT : PREVIEW_ROWS, sort_by: "title" },
    { keepPrevious: true },
  );
  const { data: propertiesResponse } = useProperties(
    undefined,
    {
      domain_class_id: id,
      limit: allRelationshipTypes ? SMALL_SET_LIMIT : PREVIEW_ROWS,
      sort_by: "title",
    },
    { keepPrevious: true },
  );
  const { data: attributesResponse } = useClassAttributeDefinitions(id);
  const properties = useMemo(() => propertiesResponse?.items ?? [], [propertiesResponse]);
  const { data: relatedClasses } = useClassesByIds([
    cls?.parent_class_id,
    ...properties.map((p) => p.range_class_id),
  ]);

  const classById = new Map((relatedClasses?.items ?? []).map((c) => [c.id, c]));
  const schemeTitleById = new Map((schemesResponse?.items ?? []).map((s) => [s.id, s.title]));
  const ownCounts = classCounts?.find((c) => c.class_id === id);
  const parentClass = cls?.parent_class_id ? classById.get(cls.parent_class_id) : undefined;

  const individualRows: IndividualRow[] = (individualsResponse?.items ?? []).map((ind) => ({
    id: ind.id,
    title: ind.title,
    description: ind.description ?? "",
  }));
  const relationshipTypeRows: RelationshipTypeRow[] = properties.map((prop) => {
    const target = prop.range_class_id ? classById.get(prop.range_class_id) : undefined;
    return {
      id: prop.id,
      predicate: predicateLabel(prop),
      targetId: prop.range_class_id ?? undefined,
      targetTitle: target?.title,
      layer: target ? schemeTitleById.get(target.concept_scheme_id) : undefined,
    };
  });

  usePageBreadcrumbs(
    entityPath("class", id),
    cls && scheme && taxonomy
      ? [
          { label: "Schema", to: "/app/schema/taxonomies" },
          { label: taxonomy.title, to: entityPath("taxonomy", taxonomy.id) },
          { label: scheme.title, to: entityPath("scheme", scheme.id) },
          { label: cls.title },
        ]
      : null,
  );

  const navigator = (
    <EntityNavigator
      selectedId={id}
      expandIds={cls ? [cls.taxonomy_id, cls.concept_scheme_id] : []}
    />
  );

  if (error) {
    return (
      <EntityPageLayout navigator={navigator} data-testid="class-page">
        <EntityPageError kind="Class" error={error} onRetry={() => refetch()} />
      </EntityPageLayout>
    );
  }

  if (!cls) {
    return (
      <EntityPageLayout navigator={navigator} data-testid="class-page">
        <div className="skeleton entity-page__skeleton" aria-busy="true" />
      </EntityPageLayout>
    );
  }

  const schemeLink = (testId?: string) =>
    scheme && (
      <EntityLink kind="scheme" id={scheme.id} data-testid={testId}>
        {scheme.title}
      </EntityLink>
    );

  return (
    <EntityPageLayout navigator={navigator} data-testid="class-page">
      <EntityHeader
        eyebrow={
          <EntityEyebrow
            parts={["Schema", "Class"]}
            parent={schemeLink("entity-parent-link")}
            status={cls.status}
            version={cls.version}
          />
        }
        title={cls.title}
        identifier={cls.identifier}
        actions={
          <EntityActions
            entity={{ kind: "class", id, title: cls.title }}
            graph={{ focus: id }}
            create={{
              label: "New individual",
              onClick: () =>
                navigate({ to: "/app/data/individuals", search: { createForClass: id } }),
            }}
          />
        }
      />

      <DefinitionPanel cls={cls} />

      <StatGrid columns={4} data-testid="entity-stats">
        <StatTile
          label="INDIVIDUALS"
          value={formatCount(individualsResponse?.total)}
          color="emerald"
        />
        <StatTile
          label="RELATIONSHIP TYPES"
          value={formatCount(propertiesResponse?.total)}
          color="amber"
          meta="with this class as domain"
        />
        <StatTile
          label="RELATIONSHIPS"
          value={formatCount(ownCounts?.relationship_count)}
          color="cyan"
          meta="outgoing, across individuals"
        />
        <StatTile
          label="ATTRIBUTES"
          value={formatCount(attributesResponse?.total)}
          color="violet"
        />
      </StatGrid>

      <EntityBody
        identity={
          <IdentityCard
            rows={[
              { key: "id", value: <span className="mono">{cls.id}</span> },
              { key: "identifier", value: <span className="mono">{cls.identifier}</span> },
              { key: "scheme", value: schemeLink() ?? "—" },
              {
                key: "taxonomy",
                value: taxonomy ? (
                  <EntityLink kind="taxonomy" id={taxonomy.id}>
                    {taxonomy.title}
                  </EntityLink>
                ) : (
                  "—"
                ),
              },
              {
                key: "parent_class",
                value: parentClass ? (
                  <EntityLink kind="class" id={parentClass.id}>
                    {parentClass.title}
                  </EntityLink>
                ) : (
                  "—"
                ),
              },
              { key: "status", value: cls.status },
              { key: "version", value: String(cls.version) },
              { key: "created", value: formatDate(cls.created_at) },
              { key: "modified", value: formatDate(cls.last_modified) },
            ]}
          >
            <ExternalReferences references={cls.external_references} />
          </IdentityCard>
        }
      >
        <Panel
          title={`Individuals · ${formatCount(individualsResponse?.total)}`}
          noPadding
          data-testid="class-individuals-panel"
          headerAction={
            <ShowAllButton
              shown={individualRows.length}
              total={individualsResponse?.total}
              onClick={() => setAllIndividuals(true)}
              testId="class-individuals-show-all"
            />
          }
        >
          <Table
            rowKey="id"
            columns={individualColumns}
            data={individualRows}
            onRowClick={(row) => navigate({ to: entityPath("individual", row.id) })}
            emptyState={
              <TableEmpty loaded={!!individualsResponse}>
                No individuals of this class yet.
              </TableEmpty>
            }
          />
        </Panel>

        <Panel
          title={`Relationship types · ${formatCount(propertiesResponse?.total)} outgoing`}
          noPadding
          data-testid="class-relationship-types-panel"
          headerAction={
            <ShowAllButton
              shown={relationshipTypeRows.length}
              total={propertiesResponse?.total}
              onClick={() => setAllRelationshipTypes(true)}
              testId="class-relationship-types-show-all"
            />
          }
        >
          <Table
            rowKey="id"
            columns={relationshipTypeColumns}
            data={relationshipTypeRows}
            emptyState={
              <TableEmpty loaded={!!propertiesResponse}>
                No property definitions have this class as domain.
              </TableEmpty>
            }
          />
        </Panel>

        <Panel
          title={`Attributes · ${formatCount(attributesResponse?.total)}`}
          noPadding
          data-testid="class-attributes-panel"
        >
          <Table
            rowKey="id"
            columns={attributeColumns}
            data={attributesResponse?.items ?? []}
            emptyState={
              <TableEmpty loaded={!!attributesResponse}>No attribute definitions.</TableEmpty>
            }
          />
        </Panel>
      </EntityBody>
    </EntityPageLayout>
  );
}

function ClassRoute() {
  const { id } = Route.useParams();
  return <ClassPage id={id} />;
}

export const Route = createFileRoute("/app/schema/classes_/$id")({
  component: ClassRoute,
});
