import { Chip, InspectorPanel } from "@tinkermonkey/heimdall-ui";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  CREATE_NEW,
  alsoOnLabel,
  charsLabel,
  nearMatchesOf,
  pageLabel,
  placePassage,
  relationshipEndsNote,
  similarityLabel,
  type NearMatchChoice as Choice,
  type RelationshipEnd,
  type SourcePassage,
} from "./sourceModel";
import { SourcesPageLink } from "@/components/sources/SourcesPageLink";
import { usePassageSource } from "./usePassageSource";
import "./proposals.css";

/**
 * The passage an operation came from: its quote highlighted in the text
 * around it when the source's text is at hand and the quote sits at its
 * offsets, else the quote alone; its page and section, a link to the source,
 * and the pages of any further passages.
 */
export function SourcePassageSection({ passages }: { passages: SourcePassage[] }) {
  const first = passages[0];
  const source = usePassageSource(first);
  if (!first) return null;
  const placed = placePassage(first, source);
  const location =
    [pageLabel(first.page), source?.section].filter(Boolean).join(" · ") || charsLabel(first);
  const also = alsoOnLabel(passages);
  const title = source?.title ?? `Source ${first.sourceId.slice(0, 8)}`;
  // A listed source links to its taxonomy's Sources page; a removed one isn't listed there.
  const linkTaxonomy = source && !source.removed ? source.taxonomyId : undefined;
  return (
    <InspectorPanel.Section title="Source passage">
      <div className="op-inspector__stack op-passage" data-testid="operation-source-passage">
        <div className="op-passage__where">
          <span className="op-passage__location" data-testid="operation-source-passage-location">
            {location}
          </span>
          {linkTaxonomy ? (
            // A new tab, so leaving never loses an unsent decision or reason.
            <SourcesPageLink
              taxonomyId={linkTaxonomy}
              newTab
              className="entity-link op-passage__source"
              data-testid="operation-source-title"
            >
              {title}
            </SourcesPageLink>
          ) : (
            <span className="op-passage__source" data-testid="operation-source-title">
              {title}
            </span>
          )}
        </div>
        <blockquote
          className="op-passage__text"
          data-placed={placed.placed ? "true" : "false"}
          data-testid="operation-source-passage-text"
        >
          {placed.placed ? (
            <>
              {placed.before}
              <mark className="op-passage__mark" data-testid="operation-source-passage-mark">
                {placed.quote}
              </mark>
              {placed.after}
            </>
          ) : (
            placed.quote || <span className="entity-note">No quote recorded.</span>
          )}
        </blockquote>
        {(also || source?.removed) && (
          <p className="op-passage__more" data-testid="operation-source-passage-more">
            {[also, source?.removed && "The source was removed."].filter(Boolean).join(". ")}
          </p>
        )}
      </div>
    </InspectorPanel.Section>
  );
}

interface NearMatchChoiceProps {
  operation: ProposedOperation;
  /** The proposal's taxonomy and dataset, to name the dataset in the question. */
  taxonomyId: string;
  datasetId?: string | null;
  choice: Choice;
  onChoose: (choice: Choice) => void;
  disabled?: boolean;
}

/**
 * "Already in dataset …?": each existing individual the create may be, with
 * its similarity, or creating a new one. Choosing an existing individual
 * applies the create as that individual.
 */
export function NearMatchChoice({
  operation,
  taxonomyId,
  datasetId,
  choice,
  onChoose,
  disabled = false,
}: NearMatchChoiceProps) {
  const { data: datasets } = useDatasets(taxonomyId);
  const dataset = datasets?.find((d) => d.id === datasetId);
  const name = `near-match-${operation.id}`;
  const title = typeof operation.fields?.title === "string" ? operation.fields.title : "this one";
  const options = [
    ...nearMatchesOf(operation).map((a) => ({
      value: a.entity_id,
      label: a.title ?? "No longer exists",
      detail: [similarityLabel(a), a.title ? undefined : a.entity_id].filter(Boolean).join(" · "),
      gone: !a.title,
    })),
    { value: CREATE_NEW, label: `Create new: ${title}`, detail: "a new individual", gone: false },
  ];
  return (
    <fieldset className="op-near-match" data-testid="operation-near-match">
      <legend className="op-near-match__legend">
        Already in {dataset ? `dataset ${dataset.identifier}` : "the dataset"}?
      </legend>
      {options.map((option) => {
        const id = `${name}-${option.value}`;
        const checked = choice === option.value;
        return (
          <label
            key={option.value}
            htmlFor={id}
            className={["op-near-match__option", checked && "op-near-match__option--chosen"]
              .filter(Boolean)
              .join(" ")}
            data-testid={`operation-near-match-option-${option.value}`}
          >
            <input
              id={id}
              type="radio"
              name={name}
              value={option.value}
              checked={checked}
              disabled={disabled || option.gone}
              onChange={() => onChoose(option.value)}
              className="op-near-match__radio"
              aria-labelledby={`${id}-label`}
              aria-describedby={option.detail ? `${id}-detail` : undefined}
            />
            <span id={`${id}-label`} className="op-near-match__label">
              {option.label}
            </span>
            {option.detail && (
              <span id={`${id}-detail`} className="op-near-match__detail">
                {option.detail}
              </span>
            )}
          </label>
        );
      })}
      <p className="op-near-match__note">
        Choosing an existing individual drops this create: relationships that name it point to the
        existing one instead, and the passage is added to its sources.
      </p>
    </fieldset>
  );
}

/** A relationship create's ends: which are new in the proposal and which follow a near match. */
export function RelationshipEndsSection({ ends }: { ends: RelationshipEnd[] }) {
  const note = relationshipEndsNote(ends);
  if (!note || ends.every((e) => e.kind === "existing")) return null;
  return (
    <InspectorPanel.Section title="Ends">
      <div className="op-inspector__stack" data-testid="operation-relationship-ends">
        <div className="op-inspector__chips">
          {ends.map((end) => (
            <Chip
              key={end.role}
              variant={end.kind === "near" ? "violet" : end.kind === "new" ? "amber" : "neutral"}
              data-testid={`operation-relationship-end-${end.role}`}
              data-kind={end.kind}
            >
              {end.role}: {end.kind === "existing" ? "existing" : `#${end.seq}`}
              {end.kind === "near" ? " · near match" : end.kind === "new" ? " · new" : ""}
            </Chip>
          ))}
        </div>
        <p className="op-decided__note" data-testid="operation-relationship-ends-note">
          {note}
        </p>
      </div>
    </InspectorPanel.Section>
  );
}
