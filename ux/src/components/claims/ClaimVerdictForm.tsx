import { useState, type FormEvent } from "react";
import { Button, Chip, Field, Select, TextArea } from "@tinkermonkey/heimdall-ui";
import { useClearClaimVerdict, useSetClaimVerdict } from "@/api/hooks/claims";
import type { Claim, Validity } from "@/api/services/claims";
import { useToasts } from "@/components/ui/Toast";
import { formatDate } from "@/utils/dateFormatting";
import {
  FIX_SCOPE_LABELS,
  SEVERITY_LABELS,
  VALIDITIES,
  VALIDITY_LABELS,
  VALIDITY_VARIANT,
  categoryOptions,
  isValidity,
} from "./claimModel";
import "./claims.css";

/** Select value for "no category / score": Heimdall's Select can't be cleared otherwise. */
const NONE = "__none__";

const VALIDITY_ERROR = "Choose a validity.";

function scoreValue(score: number | null | undefined): string {
  return score === null || score === undefined ? NONE : String(score);
}

function scoreOf(value: string): number | null {
  return value === NONE ? null : Number(value);
}

interface ClaimVerdictFormProps {
  claim: Claim;
}

/**
 * A person's verdict on a claim: validity (required), category, severity, fix
 * scope and rationale. Saving replaces any earlier verdict; Clear removes it.
 * It starts from the recorded verdict, never from the triage, so the gold is
 * the person's own answer.
 */
export function ClaimVerdictForm({ claim }: ClaimVerdictFormProps) {
  const { toast } = useToasts();
  const setVerdict = useSetClaimVerdict();
  const clearVerdict = useClearClaimVerdict();
  const verdict = claim.verdict;
  const [validity, setValidity] = useState<Validity | "">(verdict?.validity ?? "");
  const [category, setCategory] = useState(verdict?.category ?? NONE);
  const [severity, setSeverity] = useState(scoreValue(verdict?.severity));
  const [fixScope, setFixScope] = useState(scoreValue(verdict?.fix_scope));
  const [rationale, setRationale] = useState(verdict?.rationale ?? "");
  const [validityError, setValidityError] = useState<string | undefined>();
  const busy = setVerdict.isPending || clearVerdict.isPending;
  const categories = categoryOptions(claim.triage?.category, verdict?.category);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!validity) {
      setValidityError(VALIDITY_ERROR);
      return;
    }
    setVerdict.mutate(
      {
        id: claim.id,
        data: {
          validity,
          category: category === NONE ? null : category,
          severity: scoreOf(severity),
          fix_scope: scoreOf(fixScope),
          rationale: rationale.trim(),
        },
      },
      { onSuccess: () => toast("success", "Verdict saved") },
    );
  };

  const handleClear = () => {
    clearVerdict.mutate(claim.id, {
      onSuccess: () => {
        setValidity("");
        setCategory(NONE);
        setSeverity(NONE);
        setFixScope(NONE);
        setRationale("");
        toast("success", "Verdict cleared");
      },
    });
  };

  const fieldId = (name: string) => `claim-verdict-${name}-${claim.id}`;

  return (
    <form
      className="claim-verdict"
      onSubmit={handleSubmit}
      aria-label="Verdict"
      noValidate
      data-testid="claim-verdict-form"
    >
      {verdict && (
        <div className="claim-verdict__recorded" data-testid="claim-verdict-recorded">
          <Chip variant={VALIDITY_VARIANT[verdict.validity]}>
            {VALIDITY_LABELS[verdict.validity]}
          </Chip>
          <span>
            by {verdict.adjudicated_by}, {formatDate(verdict.adjudicated_at)}
          </span>
        </div>
      )}

      <Field
        label="Validity"
        htmlFor={fieldId("validity")}
        required
        error={validityError}
        errorId={fieldId("validity-error")}
      >
        <Select
          id={fieldId("validity")}
          value={validity}
          onChange={(value) => {
            if (isValidity(value)) setValidity(value);
            setValidityError(undefined);
          }}
          placeholder="Choose…"
          error={!!validityError}
          ariaLabel="Validity"
          data-testid="claim-verdict-validity"
        >
          {VALIDITIES.map((v) => (
            <Select.Item key={v} value={v}>
              {VALIDITY_LABELS[v]}
            </Select.Item>
          ))}
        </Select>
      </Field>

      <Field label="Category" htmlFor={fieldId("category")}>
        <Select
          id={fieldId("category")}
          value={category}
          onChange={setCategory}
          ariaLabel="Category"
          data-testid="claim-verdict-category"
        >
          <Select.Item value={NONE}>None</Select.Item>
          {categories.map((c) => (
            <Select.Item key={c} value={c}>
              {c}
            </Select.Item>
          ))}
        </Select>
      </Field>

      <div className="claim-verdict__scores">
        <Field label="Severity" htmlFor={fieldId("severity")}>
          <Select
            id={fieldId("severity")}
            value={severity}
            onChange={setSeverity}
            ariaLabel="Severity"
            placement="top-start"
            data-testid="claim-verdict-severity"
          >
            <Select.Item value={NONE}>Not set</Select.Item>
            {SEVERITY_LABELS.map((label, score) => (
              <Select.Item key={label} value={String(score)}>
                {`${score} · ${label}`}
              </Select.Item>
            ))}
          </Select>
        </Field>
        <Field label="Fix scope" htmlFor={fieldId("fix-scope")}>
          <Select
            id={fieldId("fix-scope")}
            value={fixScope}
            onChange={setFixScope}
            ariaLabel="Fix scope"
            placement="top-end"
            data-testid="claim-verdict-fix-scope"
          >
            <Select.Item value={NONE}>Not set</Select.Item>
            {FIX_SCOPE_LABELS.map((label, score) => (
              <Select.Item key={label} value={String(score)}>
                {`${score} · ${label}`}
              </Select.Item>
            ))}
          </Select>
        </Field>
      </div>

      <Field label="Rationale" htmlFor={fieldId("rationale")}>
        <TextArea
          id={fieldId("rationale")}
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={3}
          placeholder="Why this verdict"
          data-testid="claim-verdict-rationale"
        />
      </Field>

      <div className="claim-verdict__actions">
        {verdict && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            disabled={busy}
            data-testid="claim-verdict-clear"
          >
            Clear verdict
          </Button>
        )}
        <Button
          type="submit"
          variant="primary"
          size="sm"
          disabled={busy}
          data-testid="claim-verdict-submit"
        >
          {setVerdict.isPending ? "Saving…" : "Save verdict"}
        </Button>
      </div>
    </form>
  );
}
