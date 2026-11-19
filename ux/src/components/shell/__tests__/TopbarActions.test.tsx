import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TopbarActions } from "../TopbarActions";
import { useCanvasStore } from "@/stores/canvas";
import { useChatPanelStore } from "@/stores/chatPanel";

describe("TopbarActions", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.classList.add("dark-canvas");
    useCanvasStore.setState({ darkCanvas: true });
    useChatPanelStore.setState({ open: false });
  });

  it("renders the action cluster with its testid", () => {
    render(<TopbarActions />);
    expect(screen.getByTestId("topbar-actions")).toHaveClass("topbar-actions");
  });

  it("shows only working controls: chat and the theme toggle", () => {
    render(<TopbarActions />);
    const cluster = screen.getByTestId("topbar-actions");
    expect(cluster.querySelectorAll("button")).toHaveLength(2);
    expect(screen.getByTestId("topbar-chat-button")).toBeInTheDocument();
    expect(screen.getByTestId("topbar-theme-toggle")).toBeInTheDocument();
    expect(screen.queryByTestId("topbar-notifications")).not.toBeInTheDocument();
    expect(screen.queryByTestId("topbar-docs")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /notifications/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /documentation/i })).not.toBeInTheDocument();
    expect(cluster).not.toHaveTextContent("main");
    expect(cluster.querySelector(".topbar-iconbtn__badge")).toBeNull();
  });

  it("on the dark canvas, offers light with a sun icon and aria-pressed true", () => {
    render(<TopbarActions />);
    const toggle = screen.getByRole("button", { name: "Switch to light canvas" });
    expect(toggle).toHaveAttribute("data-testid", "topbar-theme-toggle");
    expect(toggle).toHaveClass("topbar-iconbtn");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle.querySelector('[data-icon="sun"]')).not.toBeNull();
  });

  it("on the light canvas, offers dark with a moon icon and aria-pressed false", () => {
    document.body.classList.remove("dark-canvas");
    useCanvasStore.setState({ darkCanvas: false });
    render(<TopbarActions />);
    const toggle = screen.getByRole("button", { name: "Switch to dark canvas" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(toggle.querySelector('[data-icon="moon"]')).not.toBeNull();
  });

  it("clicking the toggle flips darkCanvas, the body class and the ARIA state", async () => {
    const user = userEvent.setup();
    render(<TopbarActions />);
    const toggle = screen.getByTestId("topbar-theme-toggle");

    await user.click(toggle);
    expect(useCanvasStore.getState().darkCanvas).toBe(false);
    expect(document.body).not.toHaveClass("dark-canvas");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(toggle).toHaveAccessibleName("Switch to dark canvas");

    await user.click(toggle);
    expect(useCanvasStore.getState().darkCanvas).toBe(true);
    expect(document.body).toHaveClass("dark-canvas");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle).toHaveAccessibleName("Switch to light canvas");
  });

  it("persists the choice to storage so it survives a reload", async () => {
    const user = userEvent.setup();
    render(<TopbarActions />);
    await user.click(screen.getByTestId("topbar-theme-toggle"));
    const stored = JSON.parse(localStorage.getItem("canvas-theme") ?? "{}");
    expect(stored.state.darkCanvas).toBe(false);
  });

  it("keeps the chat button's ARIA wiring", async () => {
    const user = userEvent.setup();
    render(<TopbarActions />);
    const chat = screen.getByTestId("topbar-chat-button");
    expect(chat).toHaveAttribute("aria-controls", "chat-panel");
    expect(chat).toHaveAttribute("aria-pressed", "false");
    await user.click(chat);
    expect(chat).toHaveAttribute("aria-pressed", "true");
  });
});
