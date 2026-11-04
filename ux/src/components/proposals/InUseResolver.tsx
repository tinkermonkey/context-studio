import { useState } from "react";
import { Button, Field, FormCallout, SegmentedControl, Select } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  edgeEndLabel,
  plural,
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
  onApply,
}: InUseResolverProps) {
  const replacements = blockers.replacements ?? [];
  const canMove = replacements.length > 0;
  const [strategy, setStrategy] = useState<Strategy>(
    lastResolution?.strategy ?? (canMove ? "move" : "delete"),
  );
  const [replacementId, setReplacementId] = useState(
    lastResolution?.replacement_property_id ?? replacements[0]?.property_id ?? "",
  );
  const replacement = replacements.find((r) => r.property_id === replacementId);
  const moving = strategy === "move" && canMove;
  const count = blockers.edges.length;
  const pickerId = `operation-resolution-replacement-${operation.id}`;

  const apply = () =>
    onApply(
      moving
        ? { strategy: "move", replacement_property_id: replacementId }
        : { strategy: "delete" },
    );

  return (
    <div className="op-resolver" data-testid="operation-in-use">
      <FormCallout variant="warn" icon="alert" data-testid="operation-in-use-callout">
        {`Blocked: ${plural(count, "relationship")} still ${count === 1 ? "uses" : "use"} this type, so deleting it as proposed fails. Move them to another type or delete them too, and the type is deleted after them; or keep the type by rejecting.`}
      </FormCallout>

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
              <span className="op-resolver__fit">fits {replacement.identifier}</span>
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
            value={replacementId}
            onChange={setReplacementId}
            ariaLabel="Move to"
            data-testid="operation-resolution-replacement"
          >
            {replacements.map((r) => (
              <Select.Item key={r.property_id} value={r.property_id}>
                {r.identifier}
              </Select.Item>
            ))}
          </Select>
        </Field>
      )}

      <div className="op-decision__actions" role="group" aria-label="Resolve">
        <Button
          variant="primary"
          size="sm"
          disabled={busy || (moving && !replacement)}
          onClick={apply}
          data-testid="operation-resolution-apply"
        >
          {resolutionLabel(blockers, moving ? "move" : "delete", replacement?.identifier)}
        </Button>
      </div>
    </div>
  );
}
