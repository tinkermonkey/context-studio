import { LayerOut } from "@/api/services/layers";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useLayers } from "@/api/hooks/layers";

export interface LayerSelectorProps {
  onSelect?: (layer: LayerOut | undefined) => void;
  value?: string;
}

export const LayerSelector: React.FC<LayerSelectorProps> = ({ onSelect, value }) => {
  const { data: layers, isLoading, error } = useLayers();
  return (
    <PortalRecordSelector
      records={layers ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as LayerOut | undefined)}
      value={value}
    />
  );
};
