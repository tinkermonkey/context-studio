import { useMemo } from "react";
import { Button, Chip, Icon, InspectorPanel, KVGrid, ProgressBar } from "@tinkermonkey/heimdall-ui";
import type { Claim, ClaimTriage } from "@/api/services/claims";
import { EntityLink } from "@/components/entity/EntityLink";
import { formatDate } from "@/utils/dateFormatting";
import {
  FIX_SCOPE_LABELS,
  SEVERITY_LABELS,
  VALIDITY_LABELS,
  VALIDITY_VARIANT,
  formatProbability,
  formatScore,
  isValidity,
  rankedProbabilities,
} from "./claimModel";
import { ClaimVerdictForm } from "./ClaimVerdictForm";
import { useClaimEntities, type ClaimEntity } from "./useClaimEntities";
import "./claims.css";

/** How many categories the triage section lists, most likely first. */
const TOP_CATEGORIES = 4;

function EntityRef({ id, entity, testId }: { id: string; entity?: ClaimEntity; testId: string }) {
  if (!entity) {
    return (
      <span className="claim-ref" data-testid={testId}>
        {id}
      </span>
    );
  }
  const content = (
    <>
      <span className="claim-ref">{entity.label}</span>
      <span className="claim-ref__kind">{entity.kind}</span>
    </>
  );
  return entity.page ? (
    <EntityLink
      kind={entity.page.kind}
      id={entity.page.id}
      className="entity-link claim-entity"
      data-testid={testId}
    >
      {content}
    </EntityLink>
  ) : (
    <span className="claim-entity" data-testid={testId}>
      {content}
    </span>
  );
}

function ProbabilityRows({
  label,
  probabilities,
  chosen,
  testIdPrefix,
}: {
  label: string;
  probabilities: Array<[string, number]>;
  chosen?: string | null;
  testIdPrefix: string;
}) {
  return (
    <ul className="claim-probabilities" aria-label={label}>
      {probabilities.map(([option, p]) => (
        <li
          key={option}
          className={
            option === chosen ? "claim-probability claim-probability--chosen" : "claim-probability"
          }
          data-testid={`${testIdPrefix}${option}`}
        >
          <span className="claim-probability__name">
            {isValidity(option) ? VALIDITY_LABELS[option] : option}
          </span>
          <ProgressBar
            percent={p * 100}
            color={option === chosen ? "amber" : "neutral"}
            height={4}
            label={`${option} probability`}
          />
          <span className="claim-probability__p">{p.toFixed(2)}</span>
        </li>
      ))}
    </ul>
  );
}

function TriageSection({ triage }: { triage: ClaimTriage }) {
  const categories = rankedProbabilities(triage.category_probabilities).slice(0, TOP_CATEGORIES);
  return (
    <div className="claim-stack" data-testid="claim-triage">
      <div className="claim-chips">
        <Chip variant={VALIDITY_VARIANT[triage.validity]}>{VALIDITY_LABELS[triage.validity]}</Chip>
        {triage.category && <Chip form="id-tag">{triage.category}</Chip>}
        {!triage.calibrated && <Chip form="inferred">uncalibrated</Chip>}
      </div>
      <ProbabilityRows
        label="Validity probabilities"
        probabilities={rankedProbabilities(triage.validity_probabilities)}
        chosen={triage.validity}
        testIdPrefix="claim-triage-validity-"
      />
      {categories.length > 0 && (
        <ProbabilityRows
          label="Category probabilities"
          probabilities={categories}
          chosen={triage.category}
          testIdPrefix="claim-triage-category-"
        />
      )}
      <KVGrid
        keyWidth={120}
        rows={[
          { key: "severity", value: formatScore(triage.severity, SEVERITY_LABELS) },
          { key: "fix_scope", value: formatScore(triage.fix_scope, FIX_SCOPE_LABELS) },
          {
            key: "addressed",
            value:
              triage.addressed_by_proposal === null || triage.addressed_by_proposal === undefined
                ? "—"
                : `p ${formatProbability(triage.addressed_by_proposal)} by the pending proposal`,
          },
          { key: "model", value: <span className="claim-ref">{triage.model}</span> },
          {
            key: "cost",
            value:
              triage.cost_usd === null || triage.cost_usd === undefined
                ? "—"
                : `$${triage.cost_usd.toFixed(4)}`,
          },
          {
            key: "latency",
            value:
              triage.latency_ms === null || triage.latency_ms === undefined
                ? "—"
                : `${Math.round(triage.latency_ms)} ms`,
          },
          { key: "triaged_at", value: formatDate(triage.triaged_at) },
        ]}
      />
    </div>
  );
}

interface ClaimInspectorProps {
  claim: Claim;
  /** The claim's taxonomy, so a claim naming it links to its page. */
  taxonomy?: { id: string; label: string };
  onClose: () => void;
}

/**
 * The selected claim: its text, the note it came from, the entities it names,
 * the decision model's triage, and the verdict form.
 */
export function ClaimInspector({ claim, taxonomy, onClose }: ClaimInspectorProps) {
  const affected = useMemo(() => claim.affected_ids ?? [], [claim.affected_ids]);
  const ids = useMemo(
    () => [...new Set([claim.subject_id, ...affected].filter((id): id is string => !!id))],
    [claim.subject_id, affected],
  );
  const entities = useClaimEntities(ids, taxonomy);
  const unresolved = claim.unresolved_refs ?? [];
  const subject = claim.subject_id ? entities.get(claim.subject_id) : undefined;

  return (
    <div className="claim-inspector" data-testid="claim-inspector">
      <InspectorPanel
        eyebrow={`CLAIM · ${claim.note_source} note`}
        title={subject?.label ?? "Claim"}
        id={claim.key}
        actions={
          <Button
            variant="ghost"
            size="sm"
            icon
            onClick={onClose}
            aria-label="Close claim"
            data-testid="claim-inspector-close"
          >
            <Icon name="x" size={14} />
          </Button>
        }
      >
        <InspectorPanel.Section title="Claim">
          <div className="claim-stack">
            <p className="claim-text" data-testid="claim-text">
              {claim.text}
            </p>
            {claim.proposed_change && (
              <p className="claim-note" data-testid="claim-proposed-change">
                <span className="claim-label">Proposed change</span> {claim.proposed_change}
              </p>
            )}
            <div className="claim-chips">
              <Chip variant={claim.note_source === "maintainer" ? "violet" : "cyan"}>
                {claim.note_source}
              </Chip>
              {claim.category_hint && <Chip form="inferred">{claim.category_hint}</Chip>}
            </div>
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Source note">
          <div className="claim-stack">
            <span className="claim-ref">{claim.note_ref}</span>
            <p className="claim-note" data-testid="claim-note">
              {claim.note_text || "No note text recorded."}
            </p>
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Entities" count={affected.length + unresolved.length}>
          <div className="claim-stack" data-testid="claim-entities">
            {claim.subject_id && (
              <div className="claim-entities__subject">
                <span className="claim-label">Subject</span>
                <EntityRef
                  id={claim.subject_id}
                  entity={subject}
                  testId={`claim-subject-link-${claim.subject_id}`}
                />
              </div>
            )}
            {affected.length > 0 && (
              <ul className="claim-entities" aria-label="Affected entities">
                {affected.map((id) => (
                  <li key={id}>
                    <EntityRef id={id} entity={entities.get(id)} testId={`claim-entity-${id}`} />
                  </li>
                ))}
              </ul>
            )}
            {unresolved.length > 0 && (
              <div className="claim-stack">
                <span className="claim-label">Unresolved</span>
                <ul
                  className="claim-entities"
                  aria-label="Unresolved references"
                  data-testid="claim-unresolved-refs"
                >
                  {unresolved.map((ref) => (
                    <li key={ref} className="claim-ref">
                      {ref}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {affected.length === 0 && unresolved.length === 0 && (
              <p className="entity-note">The claim names no entities.</p>
            )}
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Triage">
          {claim.triage ? (
            <TriageSection triage={claim.triage} />
          ) : (
            <p className="entity-note" data-testid="claim-untriaged">
              Not triaged yet.
            </p>
          )}
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Verdict">
          <ClaimVerdictForm key={claim.id} claim={claim} />
        </InspectorPanel.Section>
      </InspectorPanel>
    </div>
  );
}
