interface BatchToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  testIdPrefix: string;
}

export function BatchToggle({ checked, onChange, disabled = false, testIdPrefix }: BatchToggleProps) {
  return (
    <div
      className="batch-toggle"
      role="group"
      aria-label="Batch execution"
      data-testid={`${testIdPrefix}-batch-toggle`}
    >
      <label className="batch-toggle-label">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
          data-testid={`${testIdPrefix}-batch-checkbox`}
        />
        <span>Run as batch</span>
      </label>
    </div>
  );
}
