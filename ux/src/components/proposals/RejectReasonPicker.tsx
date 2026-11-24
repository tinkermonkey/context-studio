import type { ProposedOperation, RejectionReason } from "@/api/services/proposals";
import { reasonsFor } from "./review/reviewModel";

interface RejectReasonPickerProps {
  /** The operations being rejected: the codes offered are those that apply to all of them. */
  operations: ProposedOperation[];
  value: RejectionReason;
  onChange: (code: RejectionReason) => void;
}

/** One reason code for every operation a bulk reject covers. */
export function RejectReasonPicker({ operations, value, onChange }: RejectReasonPickerProps) {
  return (
    <div
      className="reject-reasons"
      role="radiogroup"
      aria-label="Reason for every rejected operation"
      id="reject-reason-picker"
      data-testid="reject-reason-picker"
    >
      {reasonsFor(operations).map((reason) => (
        <button
          key={reason.code}
          type="button"
          role="radio"
          aria-checked={reason.code === value}
          className={
            reason.code === value ? "reject-reason reject-reason--selected" : "reject-reason"
          }
          onClick={() => onChange(reason.code)}
          data-testid={`reject-reason-${reason.code}`}
        >
          {reason.label}
        </button>
      ))}
    </div>
  );
}
