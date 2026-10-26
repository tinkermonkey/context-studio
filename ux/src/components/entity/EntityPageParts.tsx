import { Fragment, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Button,
  Chip,
  Icon,
  KVGrid,
  PageHeader,
  Panel,
  VersionPill,
  type KVGridRow,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { EntityKind } from "@/lib/entityPaths";
import type { GraphSearchParams } from "@/components/graph/graphLayers";
import { ApiError } from "@/api/client/interceptors";

/** Window event an "Ask about this" button dispatches; the chat panel listens for it. */
export const ASK_ABOUT_EVENT = "context-studio:ask-about";

export interface AskAboutDetail {
  kind: EntityKind;
  id: string;
  title: string;
}

/** YYYY-MM-DD for an ISO timestamp, or an em dash when missing/invalid. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toISOString().slice(0, 10);
}

/** A property definition's predicate for display: its canonical verb, else its title. */
export function predicateLabel(prop: { canonical_predicate?: string | null; title: string }) {
  return prop.canonical_predicate || prop.title;
}

/** A table's empty state: the message once loaded, "Loading…" before. */
export function TableEmpty({ loaded, children }: { loaded: boolean; children: ReactNode }) {
  return <span className="entity-note">{loaded ? children : "Loading…"}</span>;
}

export function formatCount(value: number | undefined): string {
  return value === undefined ? "—" : value.toLocaleString();
}

interface EntityPageLayoutProps {
  navigator: ReactNode;
  children: ReactNode;
  "data-testid": string;
}

/**
 * Navigator column beside the entity page. The frame is a size container, so
 * the columns adapt to the canvas width (which the chat column narrows), not
 * the viewport's.
 */
export function EntityPageLayout({
  navigator,
  children,
  "data-testid": testId,
}: EntityPageLayoutProps) {
  return (
    <div className="entity-page-frame">
      <div className="entity-page" data-testid={testId}>
        <aside className="entity-page__navigator">{navigator}</aside>
        <div className="entity-page__main">{children}</div>
      </div>
    </div>
  );
}

interface EntityBodyProps {
  identity: ReactNode;
  children: ReactNode;
}

/** Main sections beside the Identity card. */
export function EntityBody({ identity, children }: EntityBodyProps) {
  return (
    <div className="entity-page__body">
      <div className="entity-page__sections">{children}</div>
      {identity}
    </div>
  );
}

interface EntityEyebrowProps {
  /** e.g. ["Schema", "Class"] */
  parts: string[];
  /** Parent link(s) or class chips shown after the parts. */
  parent?: ReactNode;
  status: string;
  version: number;
}

export function EntityEyebrow({ parts, parent, status, version }: EntityEyebrowProps) {
  return (
    <span className="entity-eyebrow" data-testid="entity-eyebrow">
      {parts.map((part, i) => (
        <Fragment key={part}>
          {i > 0 && (
            <span className="entity-eyebrow__sep" aria-hidden="true">
              ·
            </span>
          )}
          <span>{part}</span>
        </Fragment>
      ))}
      {parent && (
        <>
          <span className="entity-eyebrow__sep" aria-hidden="true">
            ·
          </span>
          {parent}
        </>
      )}
      <span className="entity-eyebrow__chips">
        <Chip variant={status === "published" ? "emerald" : "amber"} data-testid="entity-status">
          {status}
        </Chip>
        <VersionPill data-testid="entity-version">v{version}</VersionPill>
      </span>
    </span>
  );
}

interface EntityActionsProps {
  entity: AskAboutDetail;
  graph: GraphSearchParams;
  create?: { label: string; onClick: () => void };
}

/** Open in graph · Ask about this · the kind's primary create action. */
export function EntityActions({ entity, graph, create }: EntityActionsProps) {
  const navigate = useNavigate();
  const askAbout = () => {
    window.dispatchEvent(new CustomEvent<AskAboutDetail>(ASK_ABOUT_EVENT, { detail: entity }));
  };
  return (
    <>
      <Button
        variant="ghost"
        onClick={() => navigate({ to: "/app/graph", search: graph })}
        data-testid="entity-open-graph"
      >
        <Icon name="graph" size={13} /> Open in graph
      </Button>
      <Button variant="ghost" onClick={askAbout} data-testid="entity-ask-about">
        <Icon name="bot" size={13} /> Ask about this
      </Button>
      {create && (
        <Button variant="primary" onClick={create.onClick} data-testid="entity-create">
          <Icon name="plus" size={13} /> {create.label}
        </Button>
      )}
    </>
  );
}

interface EntityHeaderProps {
  eyebrow: ReactNode;
  title: string;
  identifier?: string;
  description?: string | null;
  actions: ReactNode;
}

export function EntityHeader({
  eyebrow,
  title,
  identifier,
  description,
  actions,
}: EntityHeaderProps) {
  return (
    <PageHeader
      eyebrow={eyebrow}
      title={title}
      idChip={identifier}
      subtitle={description ?? undefined}
      actions={actions}
      data-testid="entity-header"
    />
  );
}

interface IdentityCardProps {
  rows: KVGridRow[];
  children?: ReactNode;
}

/** Ids, parents, status, version and dates, plus optional extra sections. */
export function IdentityCard({ rows, children }: IdentityCardProps) {
  return (
    <aside aria-label="Identity" data-testid="entity-identity">
      <Panel title="Identity">
        <div className="entity-identity">
          <KVGrid rows={rows} keyWidth={96} />
          {children}
        </div>
      </Panel>
    </aside>
  );
}

interface IdentitySectionProps {
  title: string;
  children: ReactNode;
}

export function IdentitySection({ title, children }: IdentitySectionProps) {
  return (
    <section className="entity-identity__section">
      <h3 className="entity-identity__heading">{title}</h3>
      {children}
    </section>
  );
}

interface ExternalReferencesProps {
  references?: Array<{ source: string; identifier: string; uri?: string | null }>;
}

export function ExternalReferences({ references }: ExternalReferencesProps) {
  if (!references?.length) return null;
  return (
    <IdentitySection title="External references">
      {references.map((ref) => (
        <p key={`${ref.source}:${ref.identifier}`} className="entity-note">
          {ref.source} · <span className="mono">{ref.identifier}</span>
        </p>
      ))}
    </IdentitySection>
  );
}

interface EntityPageStateProps {
  kind: string;
  error: unknown;
  onRetry: () => void;
}

/** Load failure for the page's own entity: 404 reads as "not found", anything else can retry. */
export function EntityPageError({ kind, error, onRetry }: EntityPageStateProps) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <EmptyState
        title={`${kind} not found`}
        description={`This ${kind.toLowerCase()} doesn't exist. It may have been deleted.`}
      />
    );
  }
  return (
    <ErrorBanner
      error={error as Error}
      onRetry={onRetry}
      message={`Failed to load ${kind.toLowerCase()}`}
    />
  );
}
