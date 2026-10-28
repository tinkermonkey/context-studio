import { useState } from "react";
import { Button, Field, FormCallout, Icon, Panel, TextInput } from "@tinkermonkey/heimdall-ui";
import { useMcpConnection } from "@/api/hooks/admin";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import { COPY } from "@/routes/app/settings/copy";
import "./McpConnectionPanel.css";

const MASKED_TOKEN = "••••••••••••••••";

/**
 * How to connect Claude Code (or another MCP client) to this workspace: the
 * /mcp URL, its bearer token (masked until revealed) and a ready-to-paste
 * `claude mcp add` command.
 */
export function McpConnectionPanel() {
  const { toast } = useToasts();
  const { data: connection, isLoading, error, refetch } = useMcpConnection();
  const [tokenVisible, setTokenVisible] = useState(false);

  const handleCopyCommand = async () => {
    if (!connection) return;
    try {
      await navigator.clipboard.writeText(
        COPY.mcpAddCommand(connection.url, connection.auth_token),
      );
      toast("success", COPY.mcpCommandCopied);
    } catch {
      toast("error", COPY.mcpCommandCopyFailed);
    }
  };

  return (
    <Panel
      title={COPY.mcpPanelTitle}
      subtitle={COPY.mcpPanelSubtitle}
      data-testid="mcp-connection-panel"
    >
      {isLoading && <div className="skeleton mcp-connection-skeleton" />}

      {error && (
        <ErrorBanner error={error} onRetry={refetch} message={COPY.mcpConnectionLoadFailed} />
      )}

      {connection && (
        <div className="mcp-connection">
          <Field label={COPY.mcpUrlLabel} htmlFor="mcp-connection-url">
            <TextInput
              id="mcp-connection-url"
              data-testid="mcp-connection-url"
              mono
              readOnly
              value={connection.url}
            />
          </Field>

          <Field label={COPY.mcpTokenLabel} htmlFor="mcp-connection-token" hint={COPY.mcpTokenHint}>
            <div className="mcp-connection-row">
              <TextInput
                id="mcp-connection-token"
                data-testid="mcp-connection-token"
                mono
                readOnly
                type={tokenVisible ? "text" : "password"}
                value={connection.auth_token}
              />
              <Button
                variant="secondary"
                size="sm"
                icon
                data-testid="mcp-connection-token-toggle"
                aria-pressed={tokenVisible}
                aria-controls="mcp-connection-token mcp-connection-command"
                aria-label={tokenVisible ? COPY.mcpHideToken : COPY.mcpShowToken}
                title={tokenVisible ? COPY.mcpHideToken : COPY.mcpShowToken}
                onClick={() => setTokenVisible((visible) => !visible)}
              >
                <Icon name={tokenVisible ? "eyeOff" : "eye"} size={14} />
              </Button>
            </div>
          </Field>

          <Field label={COPY.mcpCommandLabel}>
            <div className="mcp-connection-row">
              <pre
                id="mcp-connection-command"
                className="mcp-connection-command"
                data-testid="mcp-connection-command"
                aria-label={COPY.mcpCommandLabel}
              >
                {COPY.mcpAddCommand(
                  connection.url,
                  tokenVisible ? connection.auth_token : MASKED_TOKEN,
                )}
              </pre>
              <Button
                variant="secondary"
                size="sm"
                data-testid="mcp-connection-copy-command"
                aria-label={COPY.mcpCopyCommand}
                onClick={handleCopyCommand}
              >
                <Icon name="copy" size={14} /> {COPY.mcpCopyButton}
              </Button>
            </div>
          </Field>

          <FormCallout variant="info" icon="info" data-testid="mcp-connection-note">
            {COPY.mcpConnectionNote}
          </FormCallout>
        </div>
      )}
    </Panel>
  );
}
