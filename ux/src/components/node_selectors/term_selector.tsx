import { TermOut } from "@/api/services/terms";
import { RecordSelector } from "@/components/node_selectors/record_selector";
import { useTerms } from "@/api/hooks/terms";

export interface TermSelectorProps {
  onSelect?: (term: TermOut | undefined) => void;
  value?: string;
}

export const TermSelector: React.FC<TermSelectorProps> = ({ onSelect, value }) => {
  const { data: terms, isLoading, error } = useTerms();
  return (
    <RecordSelector
      records={terms ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={onSelect}
      value={value}
    />
  );
};
