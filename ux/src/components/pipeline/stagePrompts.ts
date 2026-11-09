import type { components } from "@/api/types";

type StagePromptView = components["schemas"]["StagePromptView"];
type StagePromptPayload = components["schemas"]["StagePromptPayload"];

/** Stage key -> prompts to send; null resets that stage to its default. */
export type StagePromptsBody = Record<string, StagePromptPayload | null>;

/** The prompts a configuration uses now, in request form (the server drops defaults). */
export function stagePromptsBody(stages: StagePromptView[] | null | undefined): StagePromptsBody {
  return Object.fromEntries((stages ?? []).map((s) => [s.key, { system: s.system, user: s.user }]));
}
