import { Icon } from "@tinkermonkey/heimdall-ui";
import { useChatPanelStore } from "@/stores/chatPanel";
import { useCanvasStore } from "@/stores/canvas";

/**
 * Right-side controls of the top bar: the chat assistant and the light/dark
 * canvas toggle. Only controls with working behaviour belong here.
 */
export function TopbarActions() {
  const chatOpen = useChatPanelStore((s) => s.open);
  const toggleChat = useChatPanelStore((s) => s.togglePanel);
  const darkCanvas = useCanvasStore((s) => s.darkCanvas);
  const toggleDarkCanvas = useCanvasStore((s) => s.toggleDarkCanvas);
  const themeLabel = darkCanvas ? "Switch to light canvas" : "Switch to dark canvas";

  return (
    <div className="topbar-actions" data-testid="topbar-actions">
      <button
        type="button"
        className="topbar-iconbtn"
        aria-label="Chat assistant (⌘J)"
        title="Chat assistant (⌘J)"
        aria-pressed={chatOpen}
        aria-controls="chat-panel"
        onClick={toggleChat}
        data-testid="topbar-chat-button"
      >
        <Icon name="bot" size={16} />
      </button>
      <button
        type="button"
        className="topbar-iconbtn"
        aria-label={themeLabel}
        title={themeLabel}
        aria-pressed={darkCanvas}
        onClick={toggleDarkCanvas}
        data-testid="topbar-theme-toggle"
      >
        <Icon name={darkCanvas ? "sun" : "moon"} size={16} />
      </button>
    </div>
  );
}
