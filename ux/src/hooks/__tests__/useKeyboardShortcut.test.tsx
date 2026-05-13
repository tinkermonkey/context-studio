import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useKeyboardShortcut } from "../useKeyboardShortcut";

describe("useKeyboardShortcut", () => {
  let addEventListenerSpy: any;
  let removeEventListenerSpy: any;

  beforeEach(() => {
    addEventListenerSpy = vi.spyOn(window, "addEventListener");
    removeEventListenerSpy = vi.spyOn(window, "removeEventListener");
  });

  it("registers keydown event listener on mount", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        onKeydown: mockHandler,
      }),
    );

    expect(addEventListenerSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
  });

  it("removes keydown event listener on unmount", () => {
    const mockHandler = vi.fn();

    const { unmount } = renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        onKeydown: mockHandler,
      }),
    );

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
  });

  it("calls handler when matching key is pressed", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        onKeydown: mockHandler,
      }),
    );

    const event = new KeyboardEvent("keydown", { key: "k" });
    window.dispatchEvent(event);

    expect(mockHandler).toHaveBeenCalledWith(expect.any(KeyboardEvent));
  });

  it("does not call handler for different keys", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        onKeydown: mockHandler,
      }),
    );

    const event = new KeyboardEvent("keydown", { key: "j" });
    window.dispatchEvent(event);

    expect(mockHandler).not.toHaveBeenCalled();
  });

  it("calls handler when meta modifier is pressed with correct key", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        modifiers: ["meta"],
        onKeydown: mockHandler,
      }),
    );

    const event = new KeyboardEvent("keydown", { key: "k", metaKey: true });
    vi.spyOn(event, "preventDefault");
    window.dispatchEvent(event);

    expect(mockHandler).toHaveBeenCalled();
  });

  it("does not call handler when meta modifier is required but not pressed", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        modifiers: ["meta"],
        onKeydown: mockHandler,
      }),
    );

    const event = new KeyboardEvent("keydown", { key: "k", metaKey: false });
    window.dispatchEvent(event);

    expect(mockHandler).not.toHaveBeenCalled();
  });

  it("calls handler when ctrl modifier is pressed with correct key", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        modifiers: ["ctrl"],
        onKeydown: mockHandler,
      }),
    );

    const event = new KeyboardEvent("keydown", { key: "k", ctrlKey: true });
    window.dispatchEvent(event);

    expect(mockHandler).toHaveBeenCalled();
  });

  it("calls handler when multiple modifiers are pressed", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        modifiers: ["ctrl", "shift"],
        onKeydown: mockHandler,
      }),
    );

    const event = new KeyboardEvent("keydown", { key: "k", ctrlKey: true, shiftKey: true });
    window.dispatchEvent(event);

    expect(mockHandler).toHaveBeenCalled();
  });

  it("does not call handler when shortcut is disabled", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        onKeydown: mockHandler,
        enabled: false,
      }),
    );

    const event = new KeyboardEvent("keydown", { key: "k" });
    window.dispatchEvent(event);

    expect(mockHandler).not.toHaveBeenCalled();
  });

  it("prevents default when shortcut is matched", () => {
    const mockHandler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut({
        key: "k",
        onKeydown: mockHandler,
      }),
    );

    const event = new KeyboardEvent("keydown", { key: "k" });
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");
    window.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
  });
});
