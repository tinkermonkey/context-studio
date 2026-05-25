import { ReactNode } from "react";
import { SplitPane } from "@tinkermonkey/heimdall-ui";

interface SchemaPageLayoutProps<T extends { id: string }> {
  data: T[];
  selectedId?: string;
  renderInspectorContent?: (entity: T) => ReactNode;
  children?: ReactNode;
}

export function SchemaPageLayout<T extends { id: string }>({
  data,
  selectedId,
  renderInspectorContent,
  children,
}: SchemaPageLayoutProps<T>) {
  const selectedEntity = selectedId ? data.find((item) => item.id === selectedId) : undefined;

  return (
    <div data-testid="schema-page-layout">
      {selectedEntity && renderInspectorContent ? (
        <SplitPane
          direction="horizontal"
          first={<div>{children}</div>}
          second={
            <div data-testid="schema-inspector-container">
              {renderInspectorContent(selectedEntity)}
            </div>
          }
        />
      ) : (
        children
      )}
    </div>
  );
}
