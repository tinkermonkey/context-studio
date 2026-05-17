import { Router } from "@tanstack/react-router";
import { trace } from "@opentelemetry/api";

export function setupRouterTelemetry(router: any): void {
  const tracer = trace.getTracer("router-instrumentation", "1.0.0");

  let navigationSpan: any = null;
  let navigationStartTime: number | null = null;

  // Track when navigation starts
  router.subscribe("onBeforeLoad", (event: any) => {
    const pathname = event.pathname || "unknown";
    const fromPathname = event.fromPathname || "root";
    navigationStartTime = performance.now();
    navigationSpan = tracer.startSpan(`Navigation: ${pathname}`);
    navigationSpan.setAttributes({
      "navigation.from": fromPathname,
      "navigation.to": pathname,
    });
  });

  // Track when navigation completes
  router.subscribe("onLoad", () => {
    if (navigationSpan && navigationStartTime) {
      const duration = performance.now() - navigationStartTime;
      navigationSpan.setAttributes({
        "navigation.duration_ms": duration,
      });
      navigationSpan.end();
      navigationSpan = null;
      navigationStartTime = null;
    }
  });
}
