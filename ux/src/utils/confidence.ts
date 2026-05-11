export function formatConfidence(confidence: number | null | undefined): string {
  if (confidence == null || isNaN(confidence)) {
    return "—";
  }
  return `${Math.round(confidence * 100)}%`;
}
