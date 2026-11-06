import { useState } from "react";
import { Button, Field, FormCallout, SegmentedControl, Select } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  edgeEndLabel,
  plural,
  replacementLabel,
  resolutionLabel,
  type DeleteBlockers,
  type Resolution,
} from "./decisionModel";
import "./proposals.css";

type Strategy = Resolution["strategy"];

interface InUseResolverProps {
  operation: ProposedOperation;
  blockers: DeleteBlockers;
  busy?: boolean;
  /** The resolution this delete's last apply sent, if it failed with one. */
  lastResolution?: Resolution;
  /** Why the last apply failed, when it did. */
  failureReason?: string | null;
  /**
   * The reviewer's edit retargets the type (gives it another pair of classes):
   * the relationships are resolved before the retarget instead of a delete.
   */
  retargetEdit?: string;
  onApply: (resolution: Resolution) => void;
}

/**
 * A relationship-type delete that relationships still use: lists them, and
 * offers to move them to a type every one of them fits, or delete them too,
 * before the type is deleted. Keeping the type is the Decision's reject.
 */
export function InUseResolver({
  operation,
  blockers,
  busy,
  lastResolution,
  failureReason,
  retargetEdit,
  onApply,
}: InUseResolverProps) {
  const replacements = blockers.replacements ?? [];
  const canMove = replacements.length > 0;
  // The type the delete names as its replacement: the server lists it first when it fits.
  const proposed = operation.replacement_check ?? undefined;
  const proposedId = proposed?.property_id ?? undefined;
  const proposedFits = replacements.some((r) => r.property_id === proposedId);
  // The reviewer's choices; what applies is derived from the current blockers,
  // falling back when a choice no longer holds (its type isn't offered, or no
  // type fits any more).
  const [chosenStrategy, setStrategy] = useState<Strategy | undefined>(lastResolution?.strategy);
  const [chosenReplacement, setReplacementId] = useState<string | undefined>(
    lastResolution?.replacement_property_id ?? undefined,
  );
  const replacement =
    replacements.find((r) => r.property_id === chosenReplacement) ?? replacements[0];
  const strategy: Strategy = canMove ? (chosenStrategy ?? "move") : "delete";
  const moving = strategy === "move";
  const count = blockers.edges.length;
  const pickerId = `operation-resolution-replacement-${operation.id}`;

  // The relationships the reviewer sees: the server refuses if they changed meanwhile.
  const relationshipIds = blockers.edges.map((edge) => edge.relationship_id);
  const apply = () =>
    onApply(
      moving && replacement
        ? {
            strategy: "move",
            replacement_property_id: replacement.property_id,
            relationship_ids: relationshipIds,
          }
        : { strategy: "delete", relationship_ids: relationshipIds },
    );

  return (
    <div className="op-resolver" data-testid="operation-in-use">
      <FormCallout variant="warn" icon="alert" data-testid="operation-in-use-callout">
        {retargetEdit
          ? `Your picks retarget this type to ${retargetEdit}, and ${plural(count, "relationship")} still ${count === 1 ? "uses" : "use"} it. Move them to another type or delete them, and the type is retargeted after them; or keep the type by rejecting.`
          : `Blocked: ${plural(count, "relationship")} still ${count === 1 ? "uses" : "use"} this type, so deleting it as proposed fails. Move them to another type or delete them too, and the type is deleted after them; or keep the type by rejecting.`}
      </FormCallout>
      {failureReason && (
        <FormCallout variant="error" icon="alert" data-testid="operation-resolution-failed">
          {`The last apply failed: ${failureReason}`}
        </FormCallout>
      )}

      <ul
        className="op-resolver__edges"
        aria-label="Relationships using this type"
        data-testid="operation-blocker-edges"
      >
        {blockers.edges.map((edge) => (
          <li
            key={edge.relationship_id}
            className="op-resolver__edge"
            data-testid={`operation-blocker-edge-${edge.relationship_id}`}
          >
            <span>{edgeEndLabel(edge.source)}</span>
            <span className="op-resolver__arrow" aria-label="to">
              →
            </span>
            <span>{edgeEndLabel(edge.target)}</span>
            {moving && replacement && (
              <span className="op-resolver__fit">
                {replacement.reversed
                  ? `fits ${replacement.identifier}, ends swapped`
                  : `fits ${replacement.identifier}`}
              </span>
            )}
          </li>
        ))}
      </ul>

      <SegmentedControl
        value={strategy}
        onChange={(value) => setStrategy(value as Strategy)}
        options={[
          { value: "move", label: "Move them", disabled: !canMove },
          { value: "delete", label: "Delete them too" },
        ]}
        aria-label="What happens to these relationships"
        data-testid="operation-resolution-strategy"
      />

      {!canMove && (
        <p className="op-resolver__note" data-testid="operation-move-unavailable">
          {`Move isn't available: ${blockers.move_unavailable_reason ?? "no other relationship type fits every relationship"}.`}
        </p>
      )}

      {moving && (
        <Field
          label="Move to"
          hint={`types whose source and target fit all ${plural(count, "relationship")}`}
          htmlFor={pickerId}
        >
          <Select
            id={pickerId}
            value={replacement?.property_id ?? ""}
            onChange={setReplacementId}
            ariaLabel="Move to"
            data-testid="operation-resolution-replacement"
          >
            {replacements.map((r) => (
              <Select.Item key={r.property_id} value={r.property_id}>
                {replacementLabel(r, r.property_id === proposedId)}
              </Select.Item>
            ))}
          </Select>
        </Field>
      )}

      {proposed && proposedId && !proposedFits && (
        <p className="op-resolver__note" data-testid="operation-proposed-replacement-unfit">
          {`The proposed replacement ${proposed.identifier ?? proposed.replacement_id} doesn't fit every relationship, so it isn't offered.`}
        </p>
      )}

      <div className="op-decision__actions" role="group" aria-label="Resolve">
        <Button
          variant="primary"
          size="sm"
          disabled={busy || (moving && !replacement)}
          onClick={apply}
          data-testid="operation-resolution-apply"
        >
          {resolutionLabel(
            blockers,
            moving ? "move" : "delete",
            replacement?.identifier,
            retargetEdit ? "retarget" : "delete",
          )}
        </Button>
      </div>
    </div>
  );
}
