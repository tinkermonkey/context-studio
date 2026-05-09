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
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
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
            <div
              key={chip.value}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "4px 8px",
                borderRadius: "4px",
                background: "var(--canvas-bg-2)",
                border: "1px solid var(--canvas-bd)",
                fontSize: "var(--text-xs)",
                color: "var(--canvas-fg-2)",
              }}
            >
              <span>{chip.label}</span>
              <button
                onClick={chip.onRemove}
                style={{
                  background: "none",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  color: "var(--canvas-fg-3)",
                }}
                aria-label={`Remove ${chip.label}`}
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
