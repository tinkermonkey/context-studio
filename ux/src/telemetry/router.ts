import { trace } from "@opentelemetry/api";
import { setActiveSpan } from "./context";

export function setupRouterTelemetry(router: any): void {
  const tracer = trace.getTracer("router-instrumentation", "1.0.0");

  let navigationSpan: any = null;
  let navigationStartTime: number | null = null;

  // Track when navigation starts
  router.subscribe("onBeforeLoad", (event: any) => {
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
