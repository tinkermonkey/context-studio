import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Topbar } from "@tinkermonkey/heimdall-ui";
import { CommandPalette } from "../CommandPalette";
import { handTopbarSearchToPalette } from "../topbarSearch";
import { useCommandPaletteStore } from "@/stores/commandPalette";

// The real Topbar and CommandPalette, not the setup file's stubs: the handoff
// depends on Heimdall's own input handling and focus.
vi.mock("@tinkermonkey/heimdall-ui", async () => vi.importActual("@tinkermonkey/heimdall-ui"));

const PLACEHOLDER ="Search workspace, run command, jump to…";

function Shell() {
  return (
    <>
      <Topbar searchPlaceholder={PLACEHOLDER} onSearch={handTopbarSearchToPalette} />
      <CommandPalette />
    </>
  );
}

function paletteInput() {
  return document.querySelector<HTMLInputElement>(".command-palette__input");
}

describe("topbar search → command palette handoff", () => {
  beforeEach(() => {
    useCommandPaletteStore.setState({
      open: false,
      query: "",
      actions: [
        { id: "a-1", label: "ApplicationService", description: "Class", onSelect: () => {} },
        { id: "a-2", label: "Go to Dashboard", onSelect: () => {} },
      ],
    });
  });

  it("typing in the topbar opens the palette with the typed text and its results", async () => {
    const user = userEvent.setup();
    render(<Shell />);
    const topbarInput = screen.getByRole("searchbox", { name: PLACEHOLDER });

    await user.type(topbarInput, "ApplicationService");

    await waitFor(() => expect(paletteInput()).toHaveValue("ApplicationService"));
    expect(useCommandPaletteStore.getState().query).toBe("ApplicationService");
    expect(paletteInput()).toHaveFocus();
    expect(screen.getByRole("option", { name: /ApplicationService/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Go to Dashboard/ })).not.toBeInTheDocument();
    // The text moved to the palette: nothing is left behind in the topbar.
    expect(topbarInput).toHaveValue("");
  });

  it("keeps keystrokes that reach the topbar before the palette has focus", () => {
    render(<Shell />);
    const topbarInput = screen.getByRole<HTMLInputElement>("searchbox", { name: PLACEHOLDER });

    // Two change events before the palette input takes focus.
    handTopbarSearchToPalette("Appl");
    handTopbarSearchToPalette("ication");

    expect(useCommandPaletteStore.getState()).toMatchObject({
      open: true,
      query: "Application",
    });
    expect(topbarInput.value).toBe("");
  });

  it("ignores an empty change (the topbar input being cleared)", () => {
    handTopbarSearchToPalette("");

    expect(useCommandPaletteStore.getState().open).toBe(false);
  });

  it("closing the palette clears the query and the palette starts empty next time", async () => {
    const user = userEvent.setup();
    render(<Shell />);

    await user.type(screen.getByRole("searchbox", { name: PLACEHOLDER }), "Appl");
    await waitFor(() => expect(paletteInput()).toHaveValue("Appl"));
    await user.keyboard("{Escape}");
    await waitFor(() => expect(paletteInput()).toBeNull());

    useCommandPaletteStore.getState().openPalette();
    await waitFor(() => expect(paletteInput()).toHaveValue(""));
  });
});
