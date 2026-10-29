import { useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Chip, Panel, Table, type Column } from "@tinkermonkey/heimdall-ui";
import { useIndividual, useIndividuals } from "@/api/hooks/ontology/useIndividuals";
import { useClassesByIds } from "@/api/hooks/ontology/useClasses";
import { useScheme } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import { SMALL_SET_LIMIT } from "@/api/config";
import { EntityNavigator } from "@/components/entity/EntityNavigator";
import { EntityLink } from "@/components/entity/EntityLink";
import { RelationshipAttributes } from "@/components/ontology/RelationshipAttributes";
import {
  EntityActions,
  EntityBody,
  EntityEyebrow,
  EntityHeader,
  EntityPageError,
  EntityPageLayout,
  ExternalReferences,
  IdentityCard,
  formatDate,
  predicateLabel,
} from "@/components/entity/EntityPageParts";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { entityPath } from "@/lib/entityPaths";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];
type DataPropertyValueResponse = components["schemas"]["DataPropertyValueResponse"];

interface Endpoint {
  id: string;
  title: string;
  kind: "individual" | "class";
  classId?: string;
}

const dataPropertyColumns: Column<DataPropertyValueResponse>[] = [
  {
    key: "property_identifier",
    label: "Property",
    width: "220px",
    render: (value) => <span className="mono">{value as string}</span>,
  },
  { key: "value", label: "Value", render: (value) => String(value ?? "—") },
  {
    key: "datatype",
    label: "Type",
    width: "110px",
    render: (value) => <span className="entity-muted-cell mono">{(value as string) || "—"}</span>,
  },
];

function EndpointLabel({
  endpoint,
  classTitles,
}: {
  endpoint: Endpoint | undefined;
  classTitles: Map<string, string>;
}) {
  if (!endpoint) return <span className="entity-muted-cell">Unknown entity</span>;
  return (
    <>
      <EntityLink kind={endpoint.kind} id={endpoint.id}>
        {endpoint.title}
      </EntityLink>
      {endpoint.classId && classTitles.has(endpoint.classId) && (
        <Chip variant="neutral">{classTitles.get(endpoint.classId)}</Chip>
      )}
    </>
  );
}

export function IndividualPage({ id }: { id: string }) {
  const { data: individual, error, refetch } = useIndividual(id);
  const relationshipPage = { limit: SMALL_SET_LIMIT };
  const { data: outgoingResponse } = useRelationships({ ...relationshipPage, source_id: id });
  const { data: incomingResponse } = useRelationships({ ...relationshipPage, target_id: id });
  const outgoing = useMemo(() => outgoingResponse?.items ?? [], [outgoingResponse]);
  const incoming = useMemo(() => incomingResponse?.items ?? [], [incomingResponse]);

  const endpointIds = useMemo(
    () => [...new Set([...outgoing.map((r) => r.target_id), ...incoming.map((r) => r.source_id)])],
    [outgoing, incoming],
  );
  const { data: endpointIndividuals } = useIndividuals(
    { ids: endpointIds, limit: Math.max(endpointIds.length, 1) },
    { enabled: endpointIds.length > 0, keepPrevious: true },
  );
  const endpointClassIds = (endpointIndividuals?.items ?? []).map((i) => i.class_ids[0]);
  // Own classes, endpoint individuals' classes, and endpoints that are classes themselves.
  const { data: classesResponse } = useClassesByIds([
    ...(individual?.class_ids ?? []),
    ...endpointClassIds,
    ...endpointIds,
  ]);
  const { data: predicates } = usePropertiesByIds([
    ...outgoing.map((r) => r.property_definition_id),
    ...incoming.map((r) => r.property_definition_id),
  ]);

  const classById = new Map((classesResponse?.items ?? []).map((c) => [c.id, c]));
  const classTitles = new Map((classesResponse?.items ?? []).map((c) => [c.id, c.title]));
  const predicateById = new Map((predicates?.items ?? []).map((p) => [p.id, predicateLabel(p)]));
  const endpoints = new Map<string, Endpoint>();
  for (const ind of endpointIndividuals?.items ?? []) {
    endpoints.set(ind.id, {
      id: ind.id,
      title: ind.title,
      kind: "individual",
      classId: ind.class_ids[0],
    });
  }
  for (const endpointId of endpointIds) {
    const cls = classById.get(endpointId);
    if (cls && !endpoints.has(endpointId)) {
      endpoints.set(endpointId, { id: cls.id, title: cls.title, kind: "class" });
    }
  }

  const ownClasses = (individual?.class_ids ?? [])
    .map((classId) => classById.get(classId))
    .filter((c): c is NonNullable<typeof c> => !!c);
  const primaryClass = ownClasses[0];
  const { data: scheme } = useScheme(primaryClass?.concept_scheme_id ?? "");
  const { data: taxonomy } = useTaxonomy(primaryClass?.taxonomy_id ?? "");

  usePageBreadcrumbs(
    entityPath("individual", id),
    individual && primaryClass && scheme && taxonomy
      ? [
          { label: "Data", to: "/app/data/individuals" },
          { label: taxonomy.title, to: entityPath("taxonomy", taxonomy.id) },
          { label: scheme.title, to: entityPath("scheme", scheme.id) },
          { label: primaryClass.title, to: entityPath("class", primaryClass.id) },
          { label: individual.title },
        ]
      : null,
  );

  // Data mode shows the individual under its (first) class. Individuals are
  // data, so switching to Schema opens that class's page instead.
  const navigator = (
    <EntityNavigator
      defaultMode="data"
      selectedId={id}
      schemaSelectedId={primaryClass?.id}
      modeLinks={{
        schema: primaryClass ? entityPath("class", primaryClass.id) : "/app/schema/classes",
      }}
      expandIds={
        primaryClass
          ? [primaryClass.taxonomy_id, primaryClass.concept_scheme_id, primaryClass.id]
          : []
      }
    />
  );

  if (error) {
    return (
      <EntityPageLayout navigator={navigator} data-testid="individual-page">
        <EntityPageError kind="Individual" error={error} onRetry={() => refetch()} />
      </EntityPageLayout>
    );
  }

  if (!individual) {
    return (
      <EntityPageLayout navigator={navigator} data-testid="individual-page">
        <div className="skeleton entity-page__skeleton" aria-busy="true" />
      </EntityPageLayout>
    );
  }

  const classChips = ownClasses.map((cls) => (
    <EntityLink
      key={cls.id}
      kind="class"
      id={cls.id}
      className="entity-link"
      data-testid={`individual-class-chip-${cls.id}`}
    >
      <Chip variant="violet">{cls.title}</Chip>
    </EntityLink>
  ));

  const self = <span className="entity-sentence__self">{individual.title}</span>;
  const sentence = (rel: RelationshipResponse, direction: "outgoing" | "incoming") => (
    <div key={rel.id} className="entity-sentence" data-testid={`individual-relationship-${rel.id}`}>
      {direction === "outgoing" ? (
        <>
          {self}
          <span className="entity-sentence__predicate">
            — {predicateById.get(rel.property_definition_id) ?? "related to"} →
          </span>
          <EndpointLabel endpoint={endpoints.get(rel.target_id)} classTitles={classTitles} />
        </>
      ) : (
        <>
          <EndpointLabel endpoint={endpoints.get(rel.source_id)} classTitles={classTitles} />
          <span className="entity-sentence__predicate">
            — {predicateById.get(rel.property_definition_id) ?? "related to"} →
          </span>
          {self}
        </>
      )}
      <RelationshipAttributes
        attributes={rel.attributes}
        data-testid={`individual-relationship-attributes-${rel.id}`}
      />
    </div>
  );
  const relationshipTotal = (outgoingResponse?.total ?? 0) + (incomingResponse?.total ?? 0);
  const importSource = individual.external_references?.[0]?.source;
  const dataProperties = individual.data_properties ?? [];

  return (
    <EntityPageLayout navigator={navigator} data-testid="individual-page">
      <EntityHeader
        eyebrow={
          <EntityEyebrow
            parts={["Data", "Individual"]}
            parent={<span className="entity-eyebrow__chips">{classChips}</span>}
            status={individual.status}
            version={individual.version}
          />
        }
        title={individual.title}
        description={individual.description}
        actions={
          <EntityActions
            entity={{ kind: "individual", id, title: individual.title }}
            graph={{ focus: id }}
          />
        }
      />

      <EntityBody
        identity={
          <IdentityCard
            rows={[
              { key: "id", value: <span className="mono">{individual.id}</span> },
              {
                key: "classes",
                value: ownClasses.length ? (
                  <span className="entity-eyebrow__chips">
                    {ownClasses.map((cls) => (
                      <EntityLink key={cls.id} kind="class" id={cls.id}>
                        {cls.title}
                      </EntityLink>
                    ))}
                  </span>
                ) : (
                  "—"
                ),
              },
              {
                key: "layer",
                value: scheme ? (
                  <EntityLink kind="scheme" id={scheme.id}>
                    {scheme.title}
                  </EntityLink>
                ) : (
                  "—"
                ),
              },
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
              { key: "status", value: individual.status },
              { key: "version", value: String(individual.version) },
              { key: "created", value: formatDate(individual.created_at) },
              { key: "modified", value: formatDate(individual.last_modified) },
            ]}
          >
            <ExternalReferences references={individual.external_references} />
          </IdentityCard>
        }
      >
        <Panel
          title={`Relationships · ${relationshipTotal}`}
          data-testid="individual-relationships-panel"
        >
          {relationshipTotal === 0 ? (
            <p className="entity-note">
              {outgoingResponse && incomingResponse ? "No relationships yet." : "Loading…"}
            </p>
          ) : (
            <div>
              {outgoing.length > 0 && (
                <>
                  <h3 className="entity-relationships__group">Outgoing</h3>
                  {outgoing.map((rel) => sentence(rel, "outgoing"))}
                </>
              )}
              {incoming.length > 0 && (
                <>
                  <h3 className="entity-relationships__group">Incoming</h3>
                  {incoming.map((rel) => sentence(rel, "incoming"))}
                </>
              )}
            </div>
          )}
        </Panel>

        <Panel
          title={`Data properties · ${dataProperties.length}`}
          noPadding
          data-testid="individual-data-properties-panel"
        >
          <Table
            rowKey="property_identifier"
            columns={dataPropertyColumns}
            data={dataProperties}
            emptyState={<span className="entity-note">No property values.</span>}
          />
        </Panel>

        <Panel title="Provenance" data-testid="individual-provenance-panel">
          <p className="entity-note">
            {importSource
              ? `Imported from ${importSource} on ${formatDate(individual.created_at)}.`
              : `Created on ${formatDate(individual.created_at)}.`}{" "}
            Last modified {formatDate(individual.last_modified)}.
          </p>
        </Panel>
      </EntityBody>
    </EntityPageLayout>
  );
}

function IndividualRoute() {
  const { id } = Route.useParams();
  return <IndividualPage id={id} />;
}

export const Route = createFileRoute("/app/data/individuals_/$id")({
  component: IndividualRoute,
});
