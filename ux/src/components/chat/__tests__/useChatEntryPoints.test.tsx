import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, fireEvent, render } from "@testing-library/react";
import { ASK_ABOUT_EVENT } from "@/components/entity/EntityPageParts";
import { useChatPanelStore } from "@/stores/chatPanel";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useChatEntryPoints } from "../useChatEntryPoints";
import { entityFromPath } from "../useChatPageContext";

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return {
    ...actual,
    useRouterState: () => ({ location: { pathname: "/app/data/individuals/ind-1" } }),
  };
});

function Harness() {
  useChatEntryPoints();
  return null;
}

beforeEach(() => {
  useChatPanelStore.setState({
    open: false,
    askAbout: null,
    dismissedContextKey: "old",
    newChatRequest: 0,
    focusRequest: 0,
  });
  useCommandPaletteStore.setState({ actions: [] });
});

describe("useChatEntryPoints", () => {
  it("opens the panel with the entity when an entity page asks about it", () => {
    render(<Harness />);

    act(() => {
      window.dispatchEvent(
        new CustomEvent(ASK_ABOUT_EVENT, {
          detail: { kind: "individual", id: "ind-1", title: "Admin Health" },
        }),
      );
    });

    expect(useChatPanelStore.getState()).toMatchObject({
      open: true,
      dismissedContextKey: null,
      askAbout: {
        kind: "individual",
        id: "ind-1",
        title: "Admin Health",
        pathname: "/app/data/individuals/ind-1",
      },
    });
  });

  it("toggles the panel with ⌘J", () => {
    render(<Harness />);

    fireEvent.keyDown(window, { key: "j", metaKey: true });
    expect(useChatPanelStore.getState().open).toBe(true);
    fireEvent.keyDown(window, { key: "j", metaKey: true });
    expect(useChatPanelStore.getState().open).toBe(false);
  });

  it("registers the Ask about this page and New chat palette actions", () => {
    render(<Harness />);

    const actions = useCommandPaletteStore.getState().actions;
    const ask = actions.find((a) => a.id === "chat-ask-about-page");
    const fresh = actions.find((a) => a.id === "chat-new");
    expect(ask?.label).toBe("Ask about this page");
    expect(fresh?.label).toBe("New chat");

    act(() => fresh!.onSelect());
    expect(useChatPanelStore.getState()).toMatchObject({ open: true, newChatRequest: 1 });
  });
});

describe("entityFromPath", () => {
  it.each([
    ["/app/schema/taxonomies/t1", { kind: "taxonomy", id: "t1" }],
    ["/app/schema/schemes/s1", { kind: "scheme", id: "s1" }],
    ["/app/schema/classes/c%201", { kind: "class", id: "c 1" }],
    ["/app/data/individuals/i1", { kind: "individual", id: "i1" }],
    ["/app/schema/classes", null],
    ["/app/graph", null],
  ])("%s", (path, expected) => {
    expect(entityFromPath(path)).toEqual(expected);
  });
});
