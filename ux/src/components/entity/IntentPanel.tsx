import { useState } from "react";
import Markdown, { type Components } from "react-markdown";
import { Button, Panel, TextArea } from "@tinkermonkey/heimdall-ui";

interface IntentPanelProps {
  /** Root test id; the controls derive theirs from it (`-edit`, `-input`, `-save`, `-text`). */
  "data-testid": string;
  title: string;
  /** A line under the text saying what it is for. */
  note: string;
  value: string | null | undefined;
  /** Shown when there is no value yet. */
  emptyText: string;
  /** Render the value as markdown (a vision) rather than plain text (a summary or scope note). */
  markdown?: boolean;
  rows?: number;
  /** Saves the edited text; '' clears it. A rejection keeps the editor open (the app-wide toast reports it). */
  onSave: (value: string) => Promise<unknown>;
}

/**
 * Links in a vision were written for the project's own repo: absolute links open
 * in a new tab, and relative ones (`docs/ONTOLOGY.md`) mean nothing here, so they
 * render as plain text.
 */
const markdownComponents: Components = {
  a: ({ href, children }) =>
    href && /^(https?:|mailto:)/i.test(href) ? (
      <a href={href} target="_blank" rel="noreferrer noopener">
        {children}
      </a>
    ) : (
      <span>{children}</span>
    ),
  // Images would point into the project's repo or load from elsewhere: show their alt text.
  img: ({ alt }) => (alt ? <span>[{alt}]</span> : null),
  // The page title is the h1, so the vision's own headings start a level below it.
  h1: ({ children }) => <h3>{children}</h3>,
  h2: ({ children }) => <h4>{children}</h4>,
  h3: ({ children }) => <h5>{children}</h5>,
};

/**
 * One piece of an entity's stated intent — a taxonomy's summary or vision, a
 * scheme's scope note — read and edited in place, like a class's definition.
 */
export function IntentPanel({
  "data-testid": testId,
  title,
  note,
  value,
  emptyText,
  markdown = false,
  rows = 4,
  onSave,
}: IntentPanelProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const editing = draft !== null;
  const label = title.toLowerCase();

  const save = async () => {
    if (draft === null) return;
    const next = draft.trim();
    // Nothing changed: close without saving, so no empty change lands in the history.
    if (next === (value ?? "").trim()) {
      setDraft(null);
      return;
    }
    setSaving(true);
    try {
      await onSave(next);
      setDraft(null);
    } catch {
      // The app-wide mutation error toast reports the failure; keep the draft to retry.
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel
      title={title}
      data-testid={testId}
      headerAction={
        editing ? undefined : (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDraft(value ?? "")}
            data-testid={`${testId}-edit`}
          >
            Edit {label}
          </Button>
        )
      }
    >
      {editing ? (
        <div className="stack">
          <TextArea
            aria-label={title}
            value={draft}
            rows={rows}
            mono={markdown}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            data-testid={`${testId}-input`}
          />
          <div className="row">
            <Button
              variant="primary"
              size="sm"
              onClick={() => void save()}
              disabled={saving}
              data-testid={`${testId}-save`}
            >
              Save
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDraft(null)}
              disabled={saving}
              data-testid={`${testId}-cancel`}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="stack">
          {!value ? (
            <p className="entity-note" data-testid={`${testId}-empty`}>
              {emptyText}
            </p>
          ) : markdown ? (
            <div
              className="intent-markdown"
              role="region"
              aria-label={title}
              tabIndex={0}
              data-testid={`${testId}-text`}
            >
              <Markdown components={markdownComponents}>{value}</Markdown>
            </div>
          ) : (
            <p className="entity-definition" data-testid={`${testId}-text`}>
              {value}
            </p>
          )}
          <p className="entity-note">{note}</p>
        </div>
      )}
    </Panel>
  );
}
