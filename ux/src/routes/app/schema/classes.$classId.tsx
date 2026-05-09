import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Panel } from "@/components/ui/Panel";
import { HierarchyTree } from "@/components/ontology/HierarchyTree";
import { useClass, useClasses } from "@/api/hooks/ontology/useClasses";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];
type RelationshipResponse = components["schemas"]["RelationshipResponse"];

interface ClassDetailContentProps {
  classId: string;
}

function ClassDetailContent({ classId }: ClassDetailContentProps) {
  const { data: classData, isLoading: classLoading, error: classError, refetch: refetchClass } = useClass(classId);
  const { data: classesResponse, isLoading: classesLoading, error: classesError, refetch: refetchClasses } = useClasses();
  const classes = classesResponse?.items || [];

  const { data: relationshipsResponse, isLoading: relLoading, error: relError, refetch: refetchRel } = useRelationships();
  const allRelationships = relationshipsResponse?.items || [];

  const isLoading = classLoading || classesLoading || relLoading;
  const error = classError || classesError || relError;

  if (isLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
        <Skeleton height={32} width={200} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
          <Skeleton height={300} />
          <Skeleton height={300} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <ErrorBanner
          error={error}
          onRetry={() => {
            refetchClass();
            refetchClasses();
            refetchRel();
          }}
          message="Failed to load class details"
        />
      </div>
    );
  }

  if (!classData) {
    return (
      <EmptyState
        title="Class not found"
        description="The class you're looking for doesn't exist."
      />
    );
  }

  const propertyCount = classData.data_properties?.length ?? 0;
  const relationshipsForClass = allRelationships.filter(
    (rel: RelationshipResponse) =>
      rel.source_id === classId || rel.target_id === classId
  );

  const descendantIds = new Set<string>();
  const ancestorIds = new Set<string>();

  function findDescendants(parentId: string) {
    classes.forEach((cls: ClassResponse) => {
      if (cls.parent_class_id === parentId) {
        descendantIds.add(cls.id);
        findDescendants(cls.id);
      }
    });
  }

  function findAncestors(childId: string) {
    const parent = classes.find((cls: ClassResponse) => cls.id === childId);
    if (parent?.parent_class_id) {
      ancestorIds.add(parent.parent_class_id);
      findAncestors(parent.parent_class_id);
    }
  }

  findDescendants(classId);
  findAncestors(classId);

  const hierarchyClasses = classes.filter(
    (cls: ClassResponse) =>
      cls.id === classId ||
      descendantIds.has(cls.id) ||
      ancestorIds.has(cls.id) ||
      cls.parent_class_id === classId
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)", marginBottom: "var(--space-3)" }}>
          {classData.title}
        </h1>
        <p style={{ margin: 0, color: "var(--canvas-fg-3)", fontSize: "var(--text-sm)" }}>
          <span className="mono">{classData.id}</span>
        </p>
      </div>

      {classData.description && (
        <div
          style={{
            padding: "var(--space-3) var(--space-4)",
            background: "var(--canvas-bg-2)",
            borderRadius: "var(--radius-md, 6px)",
            fontSize: "var(--text-sm)",
            color: "var(--canvas-fg-2)",
            lineHeight: 1.5,
          }}
        >
          {classData.description}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
        <Panel title="Hierarchy">
          {hierarchyClasses.length > 0 ? (
            <HierarchyTree
              classes={hierarchyClasses}
              maxDepth={5}
            />
          ) : (
            <div
              style={{
                padding: "var(--space-4)",
                color: "var(--canvas-fg-3)",
                fontSize: "var(--text-sm)",
                textAlign: "center",
              }}
            >
              No hierarchy data available
            </div>
          )}
        </Panel>

        <Panel title="Properties & Relationships">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            <div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)", marginBottom: "var(--space-2)" }}>
                Properties
              </div>
              {propertyCount > 0 ? (
                <div style={{ fontSize: "var(--text-sm)" }}>
                  {propertyCount} propert{propertyCount === 1 ? "y" : "ies"}
                </div>
              ) : (
                <div style={{ color: "var(--canvas-fg-3)", fontSize: "var(--text-sm)" }}>
                  No properties
                </div>
              )}
            </div>

            <div style={{ borderTop: "1px solid var(--canvas-fg-4)" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)", marginBottom: "var(--space-2)", marginTop: "var(--space-3)" }}>
                Relationships
              </div>
              {relationshipsForClass.length > 0 ? (
                <div style={{ fontSize: "var(--text-sm)" }}>
                  {relationshipsForClass.length} relationship{relationshipsForClass.length === 1 ? "" : "s"}
                </div>
              ) : (
                <div style={{ color: "var(--canvas-fg-3)", fontSize: "var(--text-sm)" }}>
                  No relationships
                </div>
              )}
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

interface RouteParams {
  classId: string;
}

function ClassDetailPage() {
  const { classId } = Route.useParams() as RouteParams;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <ClassDetailContent classId={classId} />
    </div>
  );
}

export const Route = createFileRoute("/app/schema/classes/$classId")({
  component: ClassDetailPage as any,
});
