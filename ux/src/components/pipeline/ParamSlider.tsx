interface ParamSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  fmt: (v: number) => string | number;
  onChange: (v: number) => void;
  active?: boolean;
}

export function ParamSlider({ label, value, min, max, step, fmt, onChange, active }: ParamSliderProps) {
  return (
    <div className="param-slider" data-testid={`param-slider-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="param-slider__header">
        <span className="param-slider__label">{label}</span>
        <span className="param-slider__value">{fmt(value)}</span>
      </div>
      {active ? (
        <input
          type="range"
          className="param-slider__input"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          aria-label={label}
        />
      ) : (
        <div className="param-slider__bar">
          <div
            className="param-slider__fill"
            style={{ width: `${((value - min) / (max - min)) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
