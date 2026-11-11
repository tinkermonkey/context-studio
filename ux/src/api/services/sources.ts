import { BaseService } from "./base";

// TODO(#1561): switch to components["schemas"] once the sources API merges and types regenerate.

/** A heading in a source's text, at its character offset. */
export interface SourceHeading {
  start: number;
  title: string;
  level: number;
}

/** A source (file, web page or text) without its text: GET /api/sources/{id}. */
export interface Source {
  id: string;
  taxonomy_id: string;
  dataset_id: string | null;
  kind: "pdf" | "markdown" | "html" | "text" | "web";
  title: string;
  origin: string | null;
  content_type: string | null;
  bytes: number | null;
  pages: number | null;
  chars: number | null;
  /** The offset at which each page starts, in page order (pages from 1). */
  page_starts: number[];
  headings: SourceHeading[];
  status: "fetching" | "ready" | "failed";
  failure: string | null;
  failure_detail: string | null;
  created_at: string;
  updated_at: string;
  /** Set once the source was removed; it is still returned. */
  removed_at: string | null;
}

/** One page's text, or the whole text: GET /api/sources/{id}/text?page=. */
export interface SourceText {
  source_id: string;
  page: number | null;
  pages: number | null;
  /** The text's offsets in the source's whole text. */
  start: number;
  end: number;
  text: string;
}

class SourcesService extends BaseService {
  async getSource(id: string): Promise<Source> {
    return this.get<Source>(`/api/sources/${id}`);
  }

  /** One page's text, or the whole text when `page` is null. */
  async getSourceText(id: string, page: number | null): Promise<SourceText> {
    return this.get<SourceText>(`/api/sources/${id}/text`, page === null ? undefined : { page });
  }
}

export const sourcesService = new SourcesService();
