import { BaseService } from "./base";
import type { components } from "@/api/types";

// TODO(#1552): the extract endpoint and `last_extraction` are typed by hand until
// the wave-2 backend lands and the types regenerate.
export type ExtractionPipeline = "individual_extraction" | "schema_extraction";

/** One run of a source's last extraction, as the source summarizes it. */
export interface LastExtractionRun {
  run_id: string;
  pipeline: ExtractionPipeline;
  status: string;
  items_done: number | null;
  items_total: number | null;
  proposal_id: string | null;
  /** The proposal's operation count, once it has one. */
  operations: number | null;
}

/** A source's most recent extraction: one run, two with schema suggestions. */
export interface LastExtraction {
  started_at: string;
  /** The dataset the extraction was for, which need not be the source's. */
  dataset_id: string;
  runs: LastExtractionRun[];
}

/** A source (file, web page or pasted text) without its text. */
export type Source = components["schemas"]["SourceResponse"] & {
  last_extraction?: LastExtraction | null;
};
export type SourceKind = components["schemas"]["SourceKind"];
export type SourceStatus = components["schemas"]["SourceStatus"];
export type SourceFailure = components["schemas"]["SourceFailure"];
/** A heading in a source's text, at its character offset. */
export type SourceHeading = components["schemas"]["SourceHeadingSchema"];
/** One page's text, or the whole text, with its offsets in the whole text. */
export type SourceText = components["schemas"]["SourceTextResponse"];
type ListSources = Omit<components["schemas"]["ListResponse_SourceResponse_"], "items"> & {
  items: Source[];
};

export interface SourceListParams {
  taxonomy_id: string;
  /** Only this dataset's sources (identifier or id). */
  dataset?: string;
  limit?: number;
  offset?: number;
}

/** Where a new source belongs; `dataset` defaults to the taxonomy's only one. */
export interface SourceScope {
  taxonomy_id: string;
  dataset?: string;
}

/** One of the three ways to add a source. */
export type NewSource =
  | { kind: "file"; file: File; title?: string }
  | { kind: "url"; url: string }
  | { kind: "text"; title: string; text: string };

/** POST /api/sources/{id}/extract */
export interface ExtractSourceRequest {
  /** The dataset the proposal and its individuals belong to (identifier or id). */
  dataset: string;
  /** An individual_extraction configuration; the server's default without. */
  configuration_ref?: string;
  /** Pages to read: digits, "-" and commas only, e.g. "1-12,15"; every page without. */
  pages?: string;
  /** Also run schema extraction, into a separate proposal. */
  schema?: boolean;
}

export interface ExtractionRunRef {
  run_id: string;
  pipeline: ExtractionPipeline;
}

/** 202 from POST /api/sources/{id}/extract: the background runs it started. */
export interface ExtractSourceResponse {
  runs: ExtractionRunRef[];
}

class SourcesService extends BaseService {
  /** A taxonomy's sources, newest first, without removed ones. */
  async listSources(params: SourceListParams): Promise<ListSources> {
    return this.get<ListSources>("/api/sources", { ...params });
  }

  /** One source without its text; a removed one too (with removed_at set). */
  async getSource(id: string): Promise<Source> {
    return this.get<Source>(`/api/sources/${id}`);
  }

  /** One page's text, or the whole text when `page` is null. */
  async getSourceText(id: string, page: number | null): Promise<SourceText> {
    return this.get<SourceText>(`/api/sources/${id}/text`, page === null ? undefined : { page });
  }

  /**
   * Add a source. A file goes up as multipart; a web page or pasted text as
   * JSON. A web page comes back `fetching` and is fetched in the background.
   */
  async addSource(scope: SourceScope, source: NewSource): Promise<Source> {
    if (source.kind === "file") {
      const form = new FormData();
      form.append("file", source.file);
      form.append("taxonomy_id", scope.taxonomy_id);
      if (scope.dataset) form.append("dataset", scope.dataset);
      if (source.title) form.append("title", source.title);
      // The instance defaults to JSON, which would make axios serialize the form as JSON.
      return this.post<Source>("/api/sources", form, undefined, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120_000,
      });
    }
    const body =
      source.kind === "url" ? { url: source.url } : { title: source.title, text: source.text };
    return this.post<Source>("/api/sources", { ...scope, ...body });
  }

  /** Remove a source; entities already applied from it keep their provenance. */
  async removeSource(id: string): Promise<Source> {
    return this.delete<Source>(`/api/sources/${id}`);
  }

  /** Start extraction on a source: one background run, two with `schema`. */
  async extractSource(id: string, body: ExtractSourceRequest): Promise<ExtractSourceResponse> {
    return this.post<ExtractSourceResponse>(`/api/sources/${id}/extract`, body);
  }
}

export const sourcesService = new SourcesService();
