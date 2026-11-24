import { useEffect, useState } from "react";
import { formatDuration } from "./reviewModel";

/** The active time on this review, ticking each second. */
export function ReviewElapsed({ pageMs }: { pageMs: () => number }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => tick((n) => n + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <span className="review-progress__time" data-testid="review-time">
      {formatDuration(pageMs())} on this review
    </span>
  );
}
