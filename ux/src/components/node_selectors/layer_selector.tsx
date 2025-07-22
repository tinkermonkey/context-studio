import { LayerOut } from "@/api/services/layers";
import { RecordSelector } from "@/components/node_selectors/record_selector";
import { useLayers } from "@/api/hooks/layers";

export interface LayerSelectorProps {
  onSelect?: (layer: LayerOut | undefined) => void;
  value?: string;
}

export const LayerSelector: React.FC<LayerSelectorProps> = ({ onSelect, value }) => {
  const { data: layers, isLoading, error } = useLayers();
  return (
    <RecordSelector
      records={layers ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={onSelect}
      value={value}
    />
  );
};
