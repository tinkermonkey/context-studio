import { useEffect, useRef, useState } from "react";
import { Button, Chip, Field, Icon, TextArea } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";
import { stagePromptsBody, type StagePromptsBody } from "./stagePrompts";

type StagePromptView = components["schemas"]["StagePromptView"];

interface StagePromptsSectionProps {
  stages: StagePromptView[];
  editable: boolean;
  /** Save every stage's prompts; called on blur after a change and on reset. */
  onSave: (body: StagePromptsBody) => void;
}

/**
 * The LLM prompts a pipeline sends at each stage. Read-only for system
 * configurations; editable (saved on blur) for user configurations.
 */
export function StagePromptsSection({ stages, editable, onSave }: StagePromptsSectionProps) {
  const [drafts, setDrafts] = useState<StagePromptsBody>(() => stagePromptsBody(stages));
  // When saved prompts come back, refresh only the stages whose saved text
  // changed, so unsaved typing in another stage is kept.
  const savedRef = useRef(stagePromptsBody(stages));
  useEffect(() => {
    const saved = stagePromptsBody(stages);
    const before = savedRef.current;
    savedRef.current = saved;
    setDrafts((d) =>
      Object.fromEntries(
        Object.entries(saved).map(([key, prompt]) => {
          const unchanged =
            before[key]?.system === prompt?.system && before[key]?.user === prompt?.user;
          return [key, unchanged && d[key] ? d[key] : prompt];
        }),
      ),
    );
  }, [stages]);

  const setDraft = (key: string, field: "system" | "user", value: string) =>
    setDrafts((d) => ({ ...d, [key]: { ...d[key], [field]: value } }));

  const saveIfChanged = (stage: StagePromptView) => {
    const draft = drafts[stage.key];
    if (draft?.system === stage.system && draft?.user === stage.user) return;
    onSave(drafts);
  };

  return (
    <section data-testid="stage-prompts-section" aria-labelledby="stage-prompts-title">
      <div className="cfg-section-title" id="stage-prompts-title">
        Stage prompts
      </div>
      <div className="cfg-stage-list">
        {stages.map((stage) => {
          const draft = drafts[stage.key] ?? { system: stage.system, user: stage.user };
          return (
            <div
              key={stage.key}
              className="cfg-stage"
              data-testid={`stage-prompt-${stage.key}`}
              role="group"
              aria-label={`${stage.label} prompts`}
            >
              <div className="cfg-stage__header">
                <span className="cfg-stage__label">{stage.label}</span>
                {stage.is_default ? (
                  <Chip variant="neutral">default</Chip>
                ) : (
                  <Chip variant="amber">edited</Chip>
                )}
                {editable && !stage.is_default && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="cfg-stage__reset"
                    onClick={() => onSave({ ...drafts, [stage.key]: null })}
                    data-testid={`stage-prompt-reset-${stage.key}`}
                  >
                    <Icon name="reload" size={12} /> Reset to default
                  </Button>
                )}
              </div>
              <div className="cfg-stage__desc">{stage.description}</div>
              <Field label="System prompt" hint={editable ? "Blank uses the default" : undefined}>
                {editable ? (
                  <TextArea
                    className="cfg-prompt"
                    mono
                    rows={4}
                    value={draft.system ?? ""}
                    onChange={(e) => setDraft(stage.key, "system", e.target.value)}
                    onBlur={() => saveIfChanged(stage)}
                    aria-label={`${stage.label} system prompt`}
                    data-testid={`stage-prompt-system-${stage.key}`}
                  />
                ) : (
                  <pre className="cfg-prompt-preview">{stage.system}</pre>
                )}
              </Field>
              <Field
                label="User prompt template"
                hint={
                  editable
                    ? "{placeholder} names are filled per call · blank uses the default"
                    : "{placeholder} names are filled per call"
                }
              >
                {editable ? (
                  <TextArea
                    className="cfg-prompt"
                    mono
                    rows={6}
                    value={draft.user ?? ""}
                    onChange={(e) => setDraft(stage.key, "user", e.target.value)}
                    onBlur={() => saveIfChanged(stage)}
                    aria-label={`${stage.label} user prompt template`}
                    data-testid={`stage-prompt-user-${stage.key}`}
                  />
                ) : (
                  <pre className="cfg-prompt-preview">{stage.user}</pre>
                )}
              </Field>
              {Object.keys(stage.placeholders).length > 0 && (
                <ul className="cfg-stage__placeholders" aria-label="Placeholders">
                  {Object.entries(stage.placeholders).map(([name, meaning]) => (
                    <li key={name}>
                      <code className="cfg-stage__placeholder">{`{${name}}`}</code>
                      <span className="cfg-stage__placeholder-meaning">{meaning}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
