interface SparklineProps {
  version: number;
  lastModified?: string | null;
  maxHeight?: number;
}

export function Sparkline({ version, lastModified, maxHeight = 20 }: SparklineProps) {
  const getRecencyColor = (lastModified?: string | null): string => {
    if (!lastModified) return "var(--slate-400)";

    const lastModTime = new Date(lastModified).getTime();
    const now = Date.now();
    const ageInHours = (now - lastModTime) / (1000 * 60 * 60);

    if (ageInHours < 1) return "var(--green-500)";
    if (ageInHours < 24) return "var(--green-400)";
    if (ageInHours < 7 * 24) return "var(--yellow-400)";
    return "var(--slate-400)";
  };

  const barCount = Math.min(version, 10);
  const barWidth = Math.max(2, Math.floor(100 / barCount));
  const gap = 1;
  const color = getRecencyColor(lastModified);

  return (
    <div
      style={{
        display: "inline-flex",
        gap: `${gap}px`,
        alignItems: "flex-end",
        height: `${maxHeight}px`,
      }}
      title={`v${version} · Last modified: ${lastModified ? new Date(lastModified).toLocaleDateString() : "—"}`}
    >
      {Array.from({ length: barCount }).map((_, index) => {
        const height = Math.max(30, ((index + 1) / barCount) * 100);
        return (
          <div
            key={index}
            style={{
              width: `${barWidth}%`,
              height: `${height}%`,
              backgroundColor: color,
              borderRadius: "2px",
              opacity: 0.6 + (index / barCount) * 0.4,
            }}
          />
        );
      })}
    </div>
  );
}
