import { useState } from "react";
import {
  Button,
  Chip,
  Field,
  Modal,
  Table,
  TextInput,
  type Column,
} from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import { useDrSpecDrift } from "@/api/hooks/interchange";
import type { DriftEntry, DriftResponse } from "@/api/services/interchange";
import { ProposalLink } from "@/components/proposals/ProposalLink";
import type { ChipVariant } from "@/components/proposals/proposalModel";
import "./DrSpecDriftDialog.css";

/** Where the last spec directory checked is remembered, per browser. */
export const SPEC_DIR_KEY = "cs.drSpecDir";

const CHANGE_VARIANT: Record<string, ChipVariant> = {
  create: "emerald",
  update: "cyan",
  move: "violet",
  delete: "rose",
};

const columns: Column<DriftEntry & { key: string }>[] = [
  {
    key: "change",
    label: "Change",
    width: "90px",
    render: (value) => (
      <Chip variant={CHANGE_VARIANT[value as string] ?? "neutral"}>{value as string}</Chip>
    ),
  },
  { key: "kind", label: "Kind", width: "100px" },
  {
    key: "source_id",
    label: "DR id",
    render: (value) => <span className="mono drift-dialog__id">{value as string}</span>,
  },
  {
    key: "fields",
    label: "Differs in",
    width: "200px",
    render: (value) => (
      <span className="drift-dialog__fields">{Object.keys(value ?? {}).join(", ") || "—"}</span>
    ),
  },
];

function rememberedDir(): string {
  try {
    return window.localStorage.getItem(SPEC_DIR_KEY) ?? "";
  } catch {
    return "";
  }
}

function remember(dir: string) {
  try {
    window.localStorage.setItem(SPEC_DIR_KEY, dir);
  } catch {
    // Remembering is a convenience; nothing to do without storage.
  }
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail as unknown;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
  }
  return error instanceof Error ? error.message : "The drift check failed";
}

function revisionLabel(result: DriftResponse): string {
  const revision = result.source_revision;
  if (!revision) return "the spec";
  const commit = revision.commit ? ` (${revision.commit.slice(0, 8)})` : "";
  return `spec ${revision.spec_version ?? ""}${commit}`.trim();
}

interface DrSpecDriftDialogProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Re-import the DR spec as a drift check: a dry run lists what differs between
 * the spec on disk and the taxonomy; Propose turns it into one proposal for
 * the review queue. Nothing changes the taxonomy until that proposal is applied.
 */
export function DrSpecDriftDialog({ open, onClose }: DrSpecDriftDialogProps) {
  const [specDir, setSpecDir] = useState(rememberedDir);
  const [checked, setChecked] = useState<DriftResponse | null>(null);
  const [proposed, setProposed] = useState<DriftResponse | null>(null);
  const drift = useDrSpecDrift();

  const run = (dryRun: boolean) => {
    const dir = specDir.trim();
    remember(dir);
    drift.mutate(
      { spec_dir: dir, dry_run: dryRun },
      { onSuccess: (result) => (dryRun ? setChecked(result) : setProposed(result)) },
    );
  };

  const shown = proposed ?? checked;
  const entries = (shown?.entries ?? []).map((entry) => ({
    ...entry,
    key: `${entry.kind}:${entry.source_id}`,
  }));
  const canPropose = !!checked && checked.entries.length > 0 && !proposed && !drift.isPending;

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Check drift against the DR spec"
      subtitle="Compares the spec on disk with this taxonomy, matched by DR id"
      size="xl"
      data-testid="dr-drift-dialog"
      footer={
        <>
          <span className="drift-dialog__spacer" />
          <Button variant="ghost" size="sm" onClick={onClose} data-testid="dr-drift-close">
            Close
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => run(true)}
            disabled={!specDir.trim() || drift.isPending || !!proposed}
            aria-busy={drift.isPending}
            data-testid="dr-drift-check"
          >
            Check
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => run(false)}
            disabled={!canPropose}
            data-testid="dr-drift-propose"
          >
            Propose
          </Button>
        </>
      }
    >
      <div className="drift-dialog" role="region" aria-label="DR spec drift">
        <Field
          label="Spec directory"
          htmlFor="dr-drift-spec-dir"
          hint="the DR checkout's spec/ folder"
          error={drift.isError ? errorText(drift.error) : undefined}
        >
          <TextInput
            id="dr-drift-spec-dir"
            mono
            value={specDir}
            placeholder="/path/to/documentation_robotics/spec"
            error={drift.isError}
            aria-invalid={drift.isError}
            onChange={(event) => {
              setSpecDir(event.target.value);
              setChecked(null);
              drift.reset();
            }}
            data-testid="dr-drift-spec-dir"
          />
        </Field>

        {shown && (
          <p className="drift-dialog__summary" data-testid="dr-drift-summary">
            {shown.entries.length === 0
              ? `No drift: the taxonomy matches ${revisionLabel(shown)}.`
              : `${shown.entries.length} ${shown.entries.length === 1 ? "entity differs" : "entities differ"} from ${revisionLabel(shown)}.`}{" "}
            {proposed?.proposal ? (
              <ProposalLink proposalId={proposed.proposal.id} data-testid="dr-drift-proposal-link">
                Review the proposal
              </ProposalLink>
            ) : shown.entries.length > 0 ? (
              "Propose them to review in the queue; nothing changes until you apply them."
            ) : null}
          </p>
        )}

        {entries.length > 0 && (
          <div className="drift-dialog__table" data-testid="dr-drift-entries">
            <Table rowKey="key" columns={columns} data={entries} />
          </div>
        )}
      </div>
    </Modal>
  );
}
