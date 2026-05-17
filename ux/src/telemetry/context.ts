import { Span } from "@opentelemetry/api";

let activeSpan: Span | null = null;

export function setActiveSpan(span: Span | null): void {
  activeSpan = span;
}

export function getActiveSpan(): Span | null {
  return activeSpan;
}
