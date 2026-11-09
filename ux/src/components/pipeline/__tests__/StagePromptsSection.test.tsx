import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StagePromptsSection } from "../StagePromptsSection";
import { stagePromptsBody } from "../stagePrompts";
import type { components } from "@/api/types";

type StagePromptView = components["schemas"]["StagePromptView"];

const STAGES: StagePromptView[] = [
  {
    key: "candidate_identification",
    label: "Candidate identification",
    description: "Lists candidate class labels.",
    placeholders: { chunk: "One chunk of the source text" },
    system: "Default system.",
    user: "Extract from {chunk}",
    is_default: true,
  },
  {
    key: "disambiguation",
    label: "Disambiguation",
    description: "Splits terms into senses.",
    placeholders: { terms: "The labels", context: "The text" },
    system: "Only split homonyms.",
    user: "Terms: {terms}",
    is_default: false,
  },
];

describe("StagePromptsSection", () => {
  it("shows every stage read-only with its placeholders and default state", () => {
    render(<StagePromptsSection stages={STAGES} editable={false} onSave={vi.fn()} />);

    expect(screen.getByTestId("stage-prompts-section")).toBeInTheDocument();
    const first = screen.getByTestId("stage-prompt-candidate_identification");
    expect(first).toHaveAttribute("role", "group");
    expect(first).toHaveTextContent("Default system.");
    expect(first).toHaveTextContent("{chunk}");
    expect(first).toHaveTextContent("default");
    expect(screen.getByTestId("stage-prompt-disambiguation")).toHaveTextContent("edited");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stage-prompt-reset-disambiguation")).not.toBeInTheDocument();
  });

  it("saves all stages on blur after an edit", async () => {
    const onSave = vi.fn();
    render(<StagePromptsSection stages={STAGES} editable onSave={onSave} />);

    const system = screen.getByTestId("stage-prompt-system-candidate_identification");
    expect(system).toHaveAccessibleName("Candidate identification system prompt");
    await userEvent.type(system, " More.");
    await userEvent.tab();

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0]).toEqual({
      candidate_identification: { system: "Default system. More.", user: "Extract from {chunk}" },
      disambiguation: { system: "Only split homonyms.", user: "Terms: {terms}" },
    });
  });

  it("does not save when a field is left unchanged", async () => {
    const onSave = vi.fn();
    render(<StagePromptsSection stages={STAGES} editable onSave={onSave} />);

    await userEvent.click(screen.getByTestId("stage-prompt-user-disambiguation"));
    await userEvent.tab();

    expect(onSave).not.toHaveBeenCalled();
  });

  it("keeps unsaved typing in one stage when another stage's saved prompts change", async () => {
    const { rerender } = render(<StagePromptsSection stages={STAGES} editable onSave={vi.fn()} />);
    const user = screen.getByTestId("stage-prompt-user-candidate_identification");
    await userEvent.type(user, " draft");

    const saved = [STAGES[0], { ...STAGES[1], system: "Saved elsewhere." }];
    rerender(<StagePromptsSection stages={saved} editable onSave={vi.fn()} />);

    expect(user).toHaveValue("Extract from {chunk} draft");
    expect(screen.getByTestId("stage-prompt-system-disambiguation")).toHaveValue(
      "Saved elsewhere.",
    );
  });

  it("resets an edited stage by sending null for it", async () => {
    const onSave = vi.fn();
    render(<StagePromptsSection stages={STAGES} editable onSave={onSave} />);

    expect(
      screen.queryByTestId("stage-prompt-reset-candidate_identification"),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("stage-prompt-reset-disambiguation"));

    expect(onSave.mock.calls[0][0]).toEqual({
      candidate_identification: { system: "Default system.", user: "Extract from {chunk}" },
      disambiguation: null,
    });
  });
});

describe("stagePromptsBody", () => {
  it("maps views to the request shape", () => {
    expect(stagePromptsBody(STAGES)).toEqual({
      candidate_identification: { system: "Default system.", user: "Extract from {chunk}" },
      disambiguation: { system: "Only split homonyms.", user: "Terms: {terms}" },
    });
    expect(stagePromptsBody(null)).toEqual({});
  });
});
