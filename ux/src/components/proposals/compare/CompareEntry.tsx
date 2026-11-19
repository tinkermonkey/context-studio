import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useChangeProposals } from "@/api/hooks/proposals";
import type { ChangeProposal } from "@/api/services/proposals";
import { originLabel } from "../ProposalOrigin";
import { comparableProposals } from "./compareModel";
import "./compare.css";

/** One page of a taxonomy's open pipeline proposals covers the candidates. */
const CANDIDATES_LIMIT = 500;

/** The open proposals `proposal` can be compared with (other pipelines, same source and dataset). */
export function useComparableProposals(proposal: ChangeProposal | undefined): ChangeProposal[] {
  const open = proposal?.status === "open" && !!proposal.origin;
  const { data } = useChangeProposals(
    {
      taxonomy_id: proposal?.taxonomy_id,
      source: "pipeline",
      status: "open",
      limit: CANDIDATES_LIMIT,
    },
    { enabled: open },
  );
  return useMemo(
    () => (open ? comparableProposals(proposal, data?.items ?? []) : []),
    [open, proposal, data],
  );
}

interface CompareEntryProps {
  proposal: ChangeProposal | undefined;
  onCompare: (otherId: string) => void;
  "data-testid"?: string;
}

/**
 * "Compare with another pipeline": shown when another open proposal extracted
 * the same source into the same dataset with another pipeline implementation.
 * With several, a small menu picks one.
 */
export function CompareEntry({
  proposal,
  onCompare,
  "data-testid": testId = "compare-entry",
}: CompareEntryProps) {
  const candidates = useComparableProposals(proposal);
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (candidates.length === 0) return null;
  const labelOf = (c: ChangeProposal) => (c.origin ? originLabel(c.origin) : c.title);

  if (candidates.length === 1) {
    const [other] = candidates;
    return (
      <Button
        variant="secondary"
        size="sm"
        title={`Compare with ${labelOf(other)}`}
        onClick={() => onCompare(other.id)}
        data-testid={testId}
      >
        Compare with another pipeline
      </Button>
    );
  }

  return (
    <div
      ref={rootRef}
      className="compare-entry"
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.stopPropagation();
          setOpen(false);
        }
      }}
      data-testid={testId}
    >
      <Button
        variant="secondary"
        size="sm"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((o) => !o)}
        data-testid={`${testId}-toggle`}
      >
        Compare with another pipeline
      </Button>
      {open && (
        <ul id={menuId} className="compare-entry__menu" role="menu" aria-label="Compare with">
          {candidates.map((c) => (
            <li key={c.id} role="none">
              <button
                type="button"
                role="menuitem"
                className="compare-entry__item"
                onClick={() => {
                  setOpen(false);
                  onCompare(c.id);
                }}
                data-testid={`${testId}-option-${c.id}`}
              >
                {labelOf(c)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
