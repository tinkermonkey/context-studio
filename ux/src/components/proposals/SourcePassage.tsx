import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  CREATE_NEW,
  nearMatchesOf,
  similarityLabel,
  type NearMatchChoice as Choice,
} from "./sourceModel";
import "./proposals.css";

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
