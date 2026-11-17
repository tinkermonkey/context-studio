import { Chip } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";

export type ProposalOrigin = components["schemas"]["ProposalOriginResponse"];

/** How many characters of the digest the chip shows. */
const DIGEST_SHOWN = 6;

/**
 * The implementation and version that produced a proposal, compactly:
 * "find_then_type v1 · 3f2a9c". The digest tells apart two runs of the same
 * configuration version that ran differently (a built-in configuration or a
 * default prompt changed in code, or a run that named its own model).
 */
export function originLabel(origin: ProposalOrigin): string {
  return `${origin.implementation_id} v${origin.configuration_version} · ${origin.digest.slice(0, DIGEST_SHOWN)}`;
}

/** The whole origin, for the chip's tooltip. */
export function originTitle(origin: ProposalOrigin): string {
  return (
    `Produced by the ${origin.implementation_id} implementation of ${origin.pipeline_type},` +
    ` configuration ${origin.configuration_ref} version ${origin.configuration_version}` +
    ` (digest ${origin.digest})`
  );
}

interface ProposalOriginChipProps {
  /** The proposal's origin; nothing renders without one (no pipeline run made it). */
  origin?: ProposalOrigin | null;
  "data-testid"?: string;
}

/** Which pipeline implementation and version produced a proposal. */
export function ProposalOriginChip({
  origin,
  "data-testid": testId = "proposal-origin",
}: ProposalOriginChipProps) {
  if (!origin) return null;
  return (
    <Chip form="version" title={originTitle(origin)} data-testid={testId}>
      {originLabel(origin)}
    </Chip>
  );
}
