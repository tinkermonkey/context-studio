import { Chip } from "@tinkermonkey/heimdall-ui";

interface VariableChipsProps {
  template: string | null | undefined;
  onInsert?: (variable: string) => void;
}

export function VariableChips({ template, onInsert }: VariableChipsProps) {
  const vars = [...new Set((template ?? "").match(/\{\{(\w+)\}\}/g)?.map((m) => m.slice(2, -2)) ?? [])];
  if (vars.length === 0) return null;

  return (
    <div className="variable-chips" data-testid="variable-chips">
      {vars.map((v) => (
        <button
          key={v}
          type="button"
          className="variable-chip-btn"
          onClick={onInsert ? () => onInsert(v) : undefined}
          disabled={!onInsert}
          title={onInsert ? `Insert {{${v}}}` : `Variable: ${v}`}
        >
          <Chip variant="neutral">{`{{${v}}}`}</Chip>
        </button>
      ))}
    </div>
  );
}
