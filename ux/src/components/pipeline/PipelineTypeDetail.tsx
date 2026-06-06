import { useMemo } from "react";
import { useParams, useNavigate, useSearch } from "@tanstack/react-router";
import { PageHeader, Icon, FormCallout } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";
import { ImplementationList } from "./ImplementationList";
import { ConfigurationList } from "./ConfigurationList";
import { ConfigurationDrawer } from "./ConfigurationDrawer";
import type { PipelineTypeSearchParams } from "@/routes/app/pipelines/types/$type";
import "./PipelineTypeDetail.css";

export function PipelineTypeDetail() {
  const { type } = useParams({ from: "/app/pipelines/types/:type" as any });
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/pipelines/types/:type" as any }) as PipelineTypeSearchParams;

  const {
    data: implementations,
    isLoading: implLoading,
    error: implError,
    refetch: refetchImpl,
  } = usePipelineImplementations(type);

  const {
    data: configurations,
    isLoading: configLoading,
    error: configError,
    refetch: refetchConfig,
  } = usePipelineConfigurations(type, searchParams.impl || "");

  const selectedConfig = useMemo(() => {
    if (!searchParams.config || !configurations) return undefined;
    // selectedId format: "config_ref" or "config_ref_version"
    const parts = searchParams.config.split("_v");
    const configRef = parts[0];
    const version = parts[1] ? parseInt(parts[1]) : undefined;

    if (version !== undefined) {
      return configurations.find((c) => c.config_ref === configRef && c.version === version);
    }
    return configurations.find((c) => c.config_ref === configRef);
  }, [configurations, searchParams.config]);

  const handleSelectImplementation = (implId: string) => {
    navigate({
      to: "/app/pipelines/types/:type" as any,
      params: { type } as any,
      search: { impl: implId, config: undefined } as any,
      replace: true,
    } as any);
  };

  const handleSelectConfiguration = (configRef: string, version?: number) => {
    const configId = version !== undefined ? `${configRef}_v${version}` : configRef;
    navigate({
      to: "/app/pipelines/types/:type" as any,
      params: { type } as any,
      search: { impl: searchParams.impl, config: configId } as any,
      replace: true,
    } as any);
  };

  if (implError) {
    return (
      <div data-testid="pipeline-type-detail-page">
        <PageHeader eyebrow="Pipelines" title={`Type: ${type}`} />
        <ErrorBanner error={implError} onRetry={() => refetchImpl()} message="Failed to load implementations" />
      </div>
    );
  }

  if (!implLoading && (!implementations || implementations.length === 0)) {
    return (
      <div data-testid="pipeline-type-detail-page">
        <PageHeader eyebrow="Pipelines" title={`Type: ${type}`} />
        <EmptyState
          title="No implementations found"
          description="This pipeline type has no registered implementations."
          icon={<Icon name="pipeline" size={48} />}
        />
      </div>
    );
  }

  return (
    <div data-testid="pipeline-type-detail-page" className="pipeline-type-detail">
      <PageHeader eyebrow="Pipelines" title={`Type: ${type}`} subtitle="Browse implementations and configurations" />

      <div className="pipeline-detail-content">
        <FormCallout variant="info" icon="info">
          Configuration editing is not yet available — persistence backend is not yet delivered
        </FormCallout>

        <div className={`pipeline-detail-layout ${selectedConfig ? "has-drawer" : ""}`}>
          <ImplementationList
            implementations={implementations || []}
            selectedId={searchParams.impl}
            onSelect={handleSelectImplementation}
            isLoading={implLoading}
            error={implError}
            onRetry={() => refetchImpl()}
          />

          {searchParams.impl && (
            <ConfigurationList
              configurations={configurations || []}
              selectedId={searchParams.config}
              onSelect={handleSelectConfiguration}
              isLoading={configLoading}
              error={configError}
              onRetry={() => refetchConfig()}
            />
          )}

          {selectedConfig && <ConfigurationDrawer configuration={selectedConfig} />}
        </div>
      </div>
    </div>
  );
}
