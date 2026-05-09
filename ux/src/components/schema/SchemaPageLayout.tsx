import { ReactNode } from "react";

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
  const selectedEntity = data.find((item) => item.id === selectedId);

  return (
    <div className="split-2" data-testid="schema-page-layout">
      <div>
        {children}
      </div>
      {selectedEntity && renderDrawerContent && (
        <div data-testid="schema-drawer-container">
          {renderDrawerContent(selectedEntity)}
        </div>
      )}
    </div>
  );
}
