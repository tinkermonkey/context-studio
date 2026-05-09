import { BaseService } from "./base";
import type { components } from "@/api/types";

type ExtractionResultSchema = components["schemas"]["ExtractionResultSchema"];
type ExtractRequest = components["schemas"]["ExtractRequest"];
type AnalyzeTextRequest = components["schemas"]["AnalyzeTextRequest"];
type EnrichFromReferencesRequest =
  components["schemas"]["EnrichFromReferencesRequest"];

class ExtractionService extends BaseService {
  async extract(text: string): Promise<ExtractionResultSchema> {
    const body: ExtractRequest = { text };
    return this.post<ExtractionResultSchema>("/api/extract", body);
  }

  async analyzeText(text: string): Promise<ExtractionResultSchema> {
    const body: AnalyzeTextRequest = { text };
    return this.post<ExtractionResultSchema>("/api/analyze_text", body);
  }

  async enrichFromReferences(
    data: EnrichFromReferencesRequest
  ): Promise<ExtractionResultSchema> {
    return this.post<ExtractionResultSchema>(
      "/api/enrich_from_references",
      data
    );
  }
}

export const extractionService = new ExtractionService();
