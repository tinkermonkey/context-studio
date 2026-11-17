import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Button, Field, SegmentedControl, TextInput } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";
import { titleFromQuote, type SelectedPassage } from "./addFromText";
import { ClassChip } from "./ReviewInspector";
import { ADDED_TIER, type Tier } from "./goldModel";
import { ReviewClassPicker } from "./ReviewClassPicker";

type ClassResponse = components["schemas"]["ClassResponse"];

interface AddElementPopoverProps {
  passage: SelectedPassage;
  /** The taxonomy's classes that are not derived. */
  pickable: ClassResponse[];
  /** The class it opens with: the one picked most recently in this review, if any. */
  initialClassId?: string;
  classLabel: (classId: string | undefined) => string;
  classOf: (classId: string | undefined) => ClassResponse | undefined;
  busy: boolean;
  /** Why the server refused the last try, shown in the form. */
  error?: string;
  /** The reviewer changed the form: a refusal shown no longer applies. */
  onEdit: () => void;
  /** Gold mode: ask the element's tier (supporting to start with). */
  askTier?: boolean;
  /** `tier` only when asked. */
  onAdd: (title: string, classId: string, tier?: Tier) => void;
  onCancel: () => void;
}

/**
 * "Selected text · not in the proposal": add the selection as an element the
 * extraction missed, with a title (the selection to start with) and a class.
 * Escape or Cancel closes it.
 */
export function AddElementPopover({
  passage,
  pickable,
  initialClassId,
  classLabel,
  classOf,
  busy,
  error,
  onEdit,
  onAdd,
  onCancel,
  askTier = false,
}: AddElementPopoverProps) {
  const [tier, setTier] = useState<Tier>(ADDED_TIER);
  const [title, setTitle] = useState(() => titleFromQuote(passage.quote));
  const [titleError, setTitleError] = useState<string>();
  const [classId, setClassId] = useState(initialClassId);
  const [classError, setClassError] = useState<string>();
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    titleRef.current?.focus();
    titleRef.current?.select();
  }, []);

  const submit = () => {
    const trimmed = title.trim();
    const noTitle = trimmed ? undefined : "Give the element a title.";
    const noClass = classId ? undefined : "Choose its class.";
    setTitleError(noTitle);
    setClassError(noClass);
    if (noTitle || noClass || !classId) return;
    onAdd(trimmed, classId, askTier ? tier : undefined);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Escape") return;
    // Escape in an open class list closes only the list.
    const target = event.target as HTMLElement;
    if (target.getAttribute("aria-expanded") === "true") return;
    event.preventDefault();
    onCancel();
  };

  return (
    <div
      className="review-add"
      role="dialog"
      aria-modal="false"
      aria-labelledby="review-add-heading"
      aria-describedby="review-add-quote"
      onKeyDown={onKeyDown}
      data-testid="review-add-popover"
    >
      <span id="review-add-heading" className="review-eyebrow">
        Selected text · not in the proposal
      </span>
      <span id="review-add-quote" className="review-add__quote" data-testid="review-add-quote">
        {passage.quote}
      </span>
      <form
        className="review-add__form"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <Field
          label="Title"
          htmlFor="review-add-title"
          required
          error={titleError}
          errorId="review-add-title-error"
        >
          <TextInput
            ref={titleRef}
            id="review-add-title"
            value={title}
            error={!!titleError}
            aria-invalid={titleError ? true : undefined}
            aria-describedby={titleError ? "review-add-title-error" : undefined}
            onChange={(event) => {
              setTitle(event.target.value);
              setTitleError(undefined);
              onEdit();
            }}
            data-testid="review-add-title"
          />
        </Field>
        <div className="review-section" data-testid="review-add-class">
          <span className="review-muted">Add as</span>
          {classId ? (
            <ClassChip label={classLabel(classId)} data-testid="review-add-class-chosen" />
          ) : (
            <span className="review-muted">No class chosen yet</span>
          )}
          <ReviewClassPicker
            classes={pickable}
            current={classOf(classId)}
            disabled={busy}
            inputId="review-add-class-search"
            label={classId ? "Another class" : "Search the classes"}
            onPick={(picked) => {
              setClassId(picked);
              setClassError(undefined);
              onEdit();
            }}
            data-testid="review-add-class-picker"
          />
          {classError && (
            <span className="review-add__error" role="alert" data-testid="review-add-class-error">
              {classError}
            </span>
          )}
        </div>
        {askTier && (
          <div className="review-tier" data-testid="review-add-tier">
            <span className="review-muted" id="review-add-tier-label">
              Tier
            </span>
            <SegmentedControl
              value={tier}
              onChange={(value) => setTier(value as Tier)}
              aria-labelledby="review-add-tier-label"
              disabled={busy}
              options={[
                { value: "core", label: "Core" },
                { value: "supporting", label: "Supporting" },
              ]}
            />
          </div>
        )}
        {error && (
          <div className="review-failed" role="alert" data-testid="review-add-error">
            {error}
          </div>
        )}
        <div className="review-chips">
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={busy}
            aria-busy={busy ? true : undefined}
            data-testid="review-add-submit"
          >
            Add element
          </Button>
          <Button variant="ghost" size="sm" onClick={onCancel} data-testid="review-add-cancel">
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
