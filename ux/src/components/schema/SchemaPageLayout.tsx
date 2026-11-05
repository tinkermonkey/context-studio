import { ReactNode } from "react";

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

  if (selectedEntity && renderInspectorContent) {
    return (
      <div data-testid="schema-page-layout" className="split-2">
        <div>{children}</div>
        <div data-testid="schema-inspector-container" className="split-2__inspector">
          {renderInspectorContent(selectedEntity)}
        </div>
      </div>
    );
  }

  return <div data-testid="schema-page-layout">{children}</div>;
}
