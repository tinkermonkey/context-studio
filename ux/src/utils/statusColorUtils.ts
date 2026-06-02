// TODO: ExecutionResponse not yet in OpenAPI spec (Phase 2 work)
type ExecutionStatus = "success" | "error" | "timeout" | string;
type ChipColor = "emerald" | "rose" | "amber" | "neutral";

export function getStatusColor(status: ExecutionStatus): ChipColor {
  switch (status) {
    case "success":
      return "emerald";
    case "error":
      return "rose";
    case "timeout":
      return "amber";
    default:
      return "neutral";
  }
}
