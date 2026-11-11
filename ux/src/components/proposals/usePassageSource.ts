import { useSource, useSourceText } from "@/api/hooks/sources/useSource";
import { pageAt, sectionAt, type PassageSource, type SourcePassage } from "./sourceModel";

/**
 * What the sources API knows about a passage's source: its title, the
 * section the passage is in, and the text of its page (or the whole text of a
 * source without pages) to place the quote in. A removed, failed or
 * unreachable source gives no text, so the passage shows its quote alone.
 */
export function usePassageSource(passage: SourcePassage | undefined): PassageSource | undefined {
  const { data: source } = useSource(passage?.sourceId);
  const readable = !!source && source.status === "ready" && !source.removed_at;
  const page =
    passage && source ? (passage.page ?? pageAt(passage.start, source.page_starts ?? [])) : null;
  const { data: text } = useSourceText(passage?.sourceId, page, { enabled: readable });
  if (!passage || !source) return undefined;
  return {
    title: source.title,
    taxonomyId: source.taxonomy_id,
    section: sectionAt(passage.start, source.headings ?? []),
    text: readable && text ? { text: text.text, start: text.start } : undefined,
    removed: !!source.removed_at,
  };
}
