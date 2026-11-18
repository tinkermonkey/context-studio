import { SegmentedControl } from "@tinkermonkey/heimdall-ui";
import { HintLabel } from "./ReviewPills";
import {
  ELEMENT_TIER_DETAIL,
  ELEMENT_TIER_HINT,
  RELATIONSHIP_TIER_DETAIL,
  RELATIONSHIP_TIER_HINT,
  type Tier,
} from "./goldModel";

/**
 * Gold mode's tier: core or supporting, with what that means in plain words
 * under the control, and the whole rule (how the scorer counts it) on the
 * label's hover.
 */
export function TierControl({
  tier,
  onChange,
  disabled,
  kind,
  idPrefix = "review-tier",
  label = "Tier",
  "data-testid": testId = "review-tier",
}: {
  tier: Tier;
  onChange: (tier: Tier) => void;
  disabled: boolean;
  /** An element's tier counts in scoring; a relationship's is only recorded. */
  kind: "element" | "relationship";
  /** Ids for the label and hint, unique on the page (the inspector and the add form). */
  idPrefix?: string;
  /** The label, a HintLabel (the inspector's footer reads "GOLD ONLY · TIER"). */
  label?: string;
  "data-testid"?: string;
}) {
  const detail = kind === "element" ? ELEMENT_TIER_DETAIL : RELATIONSHIP_TIER_DETAIL;
  const hint = kind === "element" ? ELEMENT_TIER_HINT : RELATIONSHIP_TIER_HINT;
  return (
    <div className="review-tier-block" data-testid={testId}>
      <div className="review-tier">
        <HintLabel
          id={`${idPrefix}-label`}
          label={label}
          className={label === "Tier" ? undefined : "review-hint-label--eyebrow"}
          data-testid={`${testId}-label`}
          hint={
            <>
              <span className="definition-overlay__term">Tier</span>
              {detail.map((line) => (
                <p key={line} className="definition-overlay__text">
                  {line}
                </p>
              ))}
            </>
          }
        />
        <SegmentedControl
          value={tier}
          onChange={(value) => onChange(value as Tier)}
          aria-labelledby={`${idPrefix}-label`}
          aria-describedby={`${idPrefix}-hint`}
          disabled={disabled}
          options={[
            { value: "core", label: "Core" },
            { value: "supporting", label: "Supporting" },
          ]}
        />
      </div>
      <span id={`${idPrefix}-hint`} className="review-tier__hint" data-testid={`${testId}-hint`}>
        {hint}
      </span>
    </div>
  );
}
