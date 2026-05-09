import { Input } from "@/components/ui/Input";
import { Chip } from "@/components/ui/Chip";
import { X } from "lucide-react";

interface FilterChip {
  label: string;
  value: string;
  onRemove: () => void;
}

interface FilterBarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  filterChips?: FilterChip[];
  placeholder?: string;
}

export function FilterBar({
  searchValue,
  onSearchChange,
  filterChips = [],
  placeholder = "Search by title or description…",
}: FilterBarProps) {
  return (
    <div data-testid="schema-filter-bar" style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Input
        type="text"
        placeholder={placeholder}
        value={searchValue}
        onChange={(e) => onSearchChange(e.target.value)}
        data-testid="schema-search-input"
      />
      {filterChips.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
          {filterChips.map((chip) => (
            <div key={chip.value} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <Chip className="flex items-center gap-1">
                {chip.label}
                <button
                  onClick={chip.onRemove}
                  style={{
                    background: "none",
                    border: "none",
                    padding: 0,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    marginLeft: 2,
                  }}
                  aria-label={`Remove ${chip.label}`}
                >
                  <X size={12} />
                </button>
              </Chip>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
