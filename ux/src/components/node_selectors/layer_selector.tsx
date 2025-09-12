import { StructureNode } from "@/api/types/structureNodes";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useLayerNodes } from "@/api/hooks/structure_nodes/useStructureNodes";

export interface LayerSelectorProps {
  onSelect?: (layer: StructureNode | undefined) => void;
  value?: string;
}

export const LayerSelector: React.FC<LayerSelectorProps> = ({
  onSelect,
  value,
}) => {
  const { data: layers, isLoading, error } = useLayerNodes();
  return (
    <PortalRecordSelector
      records={layers ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as StructureNode | undefined)}
      value={value}
    />
  );
};
