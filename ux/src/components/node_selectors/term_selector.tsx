import { TermOut } from "@/api/services/terms";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useTerms } from "@/api/hooks/terms";

export interface TermSelectorProps {
  onSelect?: (term: TermOut | undefined) => void;
  value?: string;
}

export const TermSelector: React.FC<TermSelectorProps> = ({ onSelect, value }) => {
  const { data: terms, isLoading, error } = useTerms();
  return (
    <PortalRecordSelector
      records={terms ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as TermOut | undefined)}
      value={value}
    />
  );
};
