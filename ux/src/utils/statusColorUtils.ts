import type { components } from "@/api/types";

type ExecutionStatus = components["schemas"]["ExecutionResponse"]["status"];
type ChipColor = "emerald" | "rose" | "amber" | "gray";

export function getStatusColor(status: ExecutionStatus): ChipColor {
  switch (status) {
    case "success":
      return "emerald";
    case "error":
      return "rose";
    case "timeout":
      return "amber";
    default:
      return "gray";
  }
}
