import { ReactNode } from "react";
import { SplitPane } from "@tinkermonkey/heimdall-ui";

interface SchemaPageLayoutProps<T extends { id: string }> {
  data: T[];
  selectedId?: string;
  renderDrawerContent?: (entity: T) => ReactNode;
  children?: ReactNode;
}

export function SchemaPageLayout<T extends { id: string }>({
  data,
  selectedId,
  renderDrawerContent,
  children,
}: SchemaPageLayoutProps<T>) {
  const selectedEntity = selectedId ? data.find((item) => item.id === selectedId) : undefined;

  return (
    <div data-testid="schema-page-layout">
      {selectedEntity && renderDrawerContent ? (
        <SplitPane
          direction="horizontal"
          first={<div>{children}</div>}
          second={
            <div data-testid="schema-drawer-container">
              {renderDrawerContent(selectedEntity)}
            </div>
          }
        />
      ) : (
        children
      )}
    </div>
  );
}
