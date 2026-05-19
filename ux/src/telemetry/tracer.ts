import {
  BasicTracerProvider,
  ConsoleSpanExporter,
  SimpleSpanProcessor,
  BatchSpanProcessor,
} from "@opentelemetry/sdk-trace-web";
import { Resource } from "@opentelemetry/resources";
import { SemanticResourceAttributes } from "@opentelemetry/semantic-conventions";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";

let tracerProvider: BasicTracerProvider | null = null;

function createResource(): Resource {
  return new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: "context-studio-frontend",
    [SemanticResourceAttributes.SERVICE_VERSION]: import.meta.env.VITE_APP_VERSION || "0.0.0",
    [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]:
      import.meta.env.VITE_DEPLOYMENT_ENV || "development",
  });
}

export function initializeTracing(): BasicTracerProvider | null {
  const telemetryEnabled = import.meta.env.VITE_TELEMETRY_ENABLED === "true";

  if (!telemetryEnabled) {
    return null;
  }

  try {
    const resource = createResource();

    tracerProvider = new BasicTracerProvider({
      resource,
    });

    const otlpEndpoint = import.meta.env.VITE_OTLP_ENDPOINT || "http://localhost:4318/v1/traces";

    const otlpExporter = new OTLPTraceExporter({
      url: otlpEndpoint,
    });

    // Type assertion needed due to version skew between @opentelemetry/exporter-trace-otlp-http
    // and @opentelemetry/sdk-trace-web. The exporter is compatible at runtime but types don't align.
    tracerProvider.addSpanProcessor(new BatchSpanProcessor(otlpExporter as any));

    // Fallback for development: log spans to console
    if (import.meta.env.DEV) {
      tracerProvider.addSpanProcessor(new SimpleSpanProcessor(new ConsoleSpanExporter()));
    }

    tracerProvider.register();

    return tracerProvider;
  } catch (error) {
    console.error("Failed to initialize tracing:", error);
    return null;
  }
}

export function getTracerProvider(): BasicTracerProvider | null {
  return tracerProvider;
}

export function setTracerProvider(provider: BasicTracerProvider): void {
  tracerProvider = provider;
}
