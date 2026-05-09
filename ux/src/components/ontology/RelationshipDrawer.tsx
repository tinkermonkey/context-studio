import { useState, useEffect } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { Input } from "@/components/ui/Input";
import { useDeleteRelationship } from "@/api/hooks/ontology/useRelationships";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useToasts } from "@/components/ui/Toast";
import { relationshipsCopy } from "@/routes/app/schema/relationships/-copy";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];

interface RelationshipDrawerProps {
  relationship: RelationshipResponse | null;
  onClose: () => void;
}

export function RelationshipDrawer({ relationship, onClose }: RelationshipDrawerProps) {
  const [sourceName, setSourceName] = useState("");
  const [targetName, setTargetName] = useState("");
  const [propertyName, setPropertyName] = useState("");

  const { toast } = useToasts();
  const deleteMutation = useDeleteRelationship();
  const { data: classesResponse } = useClasses();
  const { data: propertiesResponse } = useProperties();

  const classes = classesResponse?.items || [];
  const properties = propertiesResponse?.items || [];

  useEffect(() => {
    if (relationship) {
      const source = classes.find((c) => c.id === relationship.source_id);
      const target = classes.find((c) => c.id === relationship.target_id);
      const property = properties.find((p) => p.id === relationship.property_definition_id);

      setSourceName(source?.title || "—");
      setTargetName(target?.title || "—");
      setPropertyName(property?.title || "—");
    }
  }, [relationship, classes, properties]);

  const handleDelete = async () => {
    if (!relationship) return;
    try {
      await deleteMutation.mutateAsync(relationship.id);
      toast("success", relationshipsCopy.delete.successToast);
      onClose();
    } catch {
      toast("error", relationshipsCopy.delete.failureToast);
    }
  };

  if (!relationship) return null;

  return (
    <Drawer
      open={!!relationship}
      onClose={onClose}
      title={`${sourceName} → ${targetName}`}
      isDirty={false}
      onDelete={handleDelete}
      data-testid="relationship-drawer"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            ID
          </label>
          <Input
            type="text"
            value={relationship.id}
            disabled
            mono
            data-testid="relationship-drawer-id"
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Source Class
          </label>
          <Input
            type="text"
            value={sourceName}
            disabled
            data-testid="relationship-drawer-source-class"
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Target Class
          </label>
          <Input
            type="text"
            value={targetName}
            disabled
            data-testid="relationship-drawer-target-class"
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Relationship Type
          </label>
          <Input
            type="text"
            value={propertyName}
            disabled
            data-testid="relationship-drawer-property-type"
          />
        </div>

        <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
          <span style={{ color: "var(--canvas-fg-3)" }}>
            Created: {new Date(relationship.created_at ?? "").toLocaleDateString()}
          </span>
        </div>
      </div>
    </Drawer>
  );
}
