import type { ProposedOperation, RejectionReason } from "@/api/services/proposals";
import { reasonsFor } from "./review/reviewModel";

interface RejectReasonPickerProps {
  /** The operations being rejected: the codes offered are those that apply to all of them. */
  operations: ProposedOperation[];
  value: RejectionReason;
  onChange: (code: RejectionReason) => void;
  /** Distinguishes this picker from another on the page (the dialog's is the default). */
  testIdPrefix?: string;
}

/** One reason code for every operation a bulk reject covers. */
export function RejectReasonPicker({
  operations,
  value,
  onChange,
  testIdPrefix = "reject-reason",
}: RejectReasonPickerProps) {
  return (
    <div
      className="reject-reasons"
      role="radiogroup"
      aria-label="Reason for every rejected operation"
      id={`${testIdPrefix}-picker`}
      data-testid={`${testIdPrefix}-picker`}
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
          data-testid={`${testIdPrefix}-${reason.code}`}
        >
          {reason.label}
        </button>
      ))}
    </div>
  );
}
