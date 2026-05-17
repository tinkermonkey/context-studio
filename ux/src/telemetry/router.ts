import { trace, Span } from "@opentelemetry/api";
import { setActiveSpan } from "./context";

interface RouterLike {
  subscribe(
    event: "onBeforeLoad",
    callback: (event: { toLocation?: { pathname: string }; fromLocation?: { pathname: string } }) => void
  ): void;
  subscribe(event: "onLoad", callback: () => void): void;
}

export function setupRouterTelemetry(router: RouterLike): void {
  const tracer = trace.getTracer("router-instrumentation", "1.0.0");

  let navigationSpan: Span | null = null;
  let navigationStartTime: number | null = null;

  // Track when navigation starts
  router.subscribe("onBeforeLoad", (event) => {
    const pathname = event.toLocation?.pathname || "unknown";
    const fromPathname = event.fromLocation?.pathname || "root";
    navigationStartTime = performance.now();
    navigationSpan = tracer.startSpan(`Navigation: ${pathname}`);
    navigationSpan.setAttributes({
      "navigation.from": fromPathname,
      "navigation.to": pathname,
    });
    setActiveSpan(navigationSpan);
  });

  // Track when navigation completes
  router.subscribe("onLoad", () => {
    if (navigationSpan && navigationStartTime) {
      const duration = performance.now() - navigationStartTime;
      navigationSpan.setAttributes({
        "navigation.duration_ms": duration,
      });
      navigationSpan.end();
      setActiveSpan(null);
      navigationSpan = null;
      navigationStartTime = null;
    }
  });
}
