type ProgressBarColor = StatusColor;

interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  percent: number;
  color?: ProgressBarColor;
  height?: number;
  label?: string;
}

const ProgressBar = React.forwardRef<HTMLDivElement, ProgressBarProps>(
  ({ percent, color = "emerald", height = 6, label, className = "", ...rest }, ref) => {
    const clampedPercent = Number.isNaN(percent) ? 0 : Math.min(Math.max(percent, 0), 100);
    const colorClass = `progress-bar--${color}`;

    return (
      <div
        ref={ref}
        className={`progress-bar ${colorClass} ${className}`.trim()}
        style={{ height: `${height}px` }}
        role="progressbar"
        aria-valuenow={clampedPercent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        {...rest}
      >
        <div className="progress-bar__fill" style={{ width: `${clampedPercent}%` }} />
      </div>
    );
  },
);

ProgressBar.displayName = "ProgressBar";

// --- Babel-standalone: expose runtime values to window ---
window.ProgressBar = ProgressBar;
