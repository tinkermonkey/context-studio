import * as React from "react";
import { useState} from "react";
import NlpConceptChart from "../graphs/nlp_concept/NlpConceptChart";
import type { TokenData as BaseTokenData } from "@/api/services/nlp";

type TokenData = BaseTokenData & { is_stop?: boolean };

interface Props {
  token: TokenData;
  /** Selected node IDs from the parent */
  selectedNodeIds?: Set<string>;
  /** Handler for node click events */
  onNodeClick?: (nodeId: string) => void;
}

export const NlpTokenAnalysisPanel: React.FC<Props> = ({
  token,
  selectedNodeIds,
  onNodeClick,
}) => {
  const [measuredWidth, setMeasuredWidth] = useState<number | null>(null);
  const measurementContentRef = React.useRef<HTMLDivElement | null>(null);

  // Get the token context
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const wordnet = token.wordnet as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const concepcy = token.concepcy as any;
  const relations = Array.isArray(concepcy?.related_terms)
    ? concepcy.related_terms
    : [];

  // Create token prefix for this chart
  const tokenPrefix = `token-${token.text}-${token.start ?? 0}`;

  // Filter selectedNodeIds to only include nodes from this token chart
  // and convert them back to local node IDs
  const localSelectedNodeIds = React.useMemo(() => {
    if (!selectedNodeIds) return new Set<string>();

    const localIds = new Set<string>();
    for (const fullId of selectedNodeIds) {
      if (fullId.startsWith(`${tokenPrefix}-`)) {
        // Remove the token prefix to get the local node ID
        const localId = fullId.substring(`${tokenPrefix}-`.length);
        localIds.add(localId);
      }
    }
    return localIds;
  }, [selectedNodeIds, tokenPrefix]);

  // ResizeObserver to measure available width
  useEffect(() => {
    const el = measurementContentRef.current;
    if (!el) return;

    const measure = () => {
      const rect = el.getBoundingClientRect();
      setMeasuredWidth(rect.width || null);
    };

    measure();
    const ro = new ResizeObserver(() => measure());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="space-y-3">
      <div className="w-full" ref={measurementContentRef} />
      <div>
        {(wordnet?.synsets || concepcy?.related_terms) && measuredWidth ? (
          <NlpConceptChart
            data={{
              text: token.text,
              lemma: token.lemma || token.text,
              pos: token.pos || token.tag || "",
              concepcy: {
                related_terms: relations,
              },
              wordnet: {
   
                synsets: (wordnet?.synsets || []).map((s: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => ({
                  name: s.name || s.synset || s.id || s[0] || "unknown",
                  definition: s.definition || s.gloss || s.def || "",
                  lemmas: s.lemmas || [],
                  pos: s.pos || s.partOfSpeech || token.pos || token.tag || "",
                  offset: s.offset || 0,
                  domain: s.domain || "general",
                })),
                definitions: (wordnet?.synsets || []).map(
   
                  (s: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => s.definition || s.gloss || s.def || "",
                ),
              },
            }}
            width={measuredWidth}
            config={{
              RelatedTo: 3,
              IsA: 3,
              HasA: 2,
              PartOf: 2,
              UsedFor: 2,
            }}
            onNodeClick={onNodeClick}
            selectedNodeIds={localSelectedNodeIds}
          />
        ) : (
          <div className="text-sm text-gray-500">
            No concept relationships available
          </div>
        )}
      </div>
    </div>
  );
};

export default NlpTokenAnalysisPanel;
