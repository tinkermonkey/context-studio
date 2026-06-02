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
      <div
        data-testid="schema-page-layout"
        style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 14, alignItems: "start" }}
      >
        <div>{children}</div>
        <div data-testid="schema-inspector-container">{renderInspectorContent(selectedEntity)}</div>
      </div>
    );
  }

  return <div data-testid="schema-page-layout">{children}</div>;
}
