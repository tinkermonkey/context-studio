import * as React from 'react';

interface Relation {
  relation: string;
  terms: string[];
  scores?: number[];
}

interface ConcepcyData {
  related_terms?: Relation[] | string[];
  central_concept?: string;
}

interface Props {
  // backward compatible props
  centralTerm?: string;
  relations?: Relation[];

  // preferred: pass the raw concepcy data
  concepcyData?: ConcepcyData;

  maxRelationsPerType?: number;
  onConceptSelect?: (concept: string) => void;
}

const RELATION_COLORS: Record<string, string> = {
  IsA: '#10B981',
  RelatedTo: '#3B82F6',
  PartOf: '#F59E0B',
};

export const TokenConceptChart: React.FC<Props> = ({
  centralTerm = '',
  relations = [],
  concepcyData,
  maxRelationsPerType = 2,
  onConceptSelect,
}) => {
  try {
    // main render body
  } catch (err) {
    console.error('TokenConceptChart render error', err);
    return <div className="text-sm text-gray-500">Unable to render concept chart</div>;
  }
  // Normalize relations from concepcyData if provided, otherwise use relations prop
  const normalized: Relation[] = React.useMemo(() => {
    if (concepcyData?.related_terms) {
      const raw = concepcyData.related_terms;
      if (Array.isArray(raw) && raw.length > 0 && typeof raw[0] === 'string') {
        // simple array of strings -> group under 'related'
        return [
          {
            relation: 'RelatedTo',
            terms: raw as string[],
            scores: undefined,
          },
        ];
      }

      // assume objects
      return (raw as Relation[]).map((r: any) => ({
        relation: r.relation ?? r.type ?? 'RelatedTo',
        terms: r.terms ?? r.related ?? [],
        scores: r.scores,
      }));
    }

    return relations || [];
  }, [concepcyData, relations]);

  if (!normalized || normalized.length === 0) {
    return <div className="text-sm text-gray-500">No concept relationships available</div>;
  }

  // Build node list: for each relation type, include up to maxRelationsPerType term nodes
  type Node = { term: string; relation: string; score?: number };
  const nodes: Node[] = [];
  normalized.forEach((r) => {
    const topTerms = (r.terms || []).slice(0, maxRelationsPerType);
    topTerms.forEach((t, i) => nodes.push({ term: t, relation: r.relation, score: r.scores?.[i] }));
  });

  const centerX = 200;
  const centerY = 120;
  const radius = 80;

  return (
    <svg viewBox="0 0 400 240" className="w-full h-56" role="img" aria-label={`Concept map for ${centralTerm || concepcyData?.central_concept || 'term'}`}>
      {/* central node */}
      <g>
        <circle cx={centerX} cy={centerY} r={26} fill="#8B5CF6" />
        <text x={centerX} y={centerY + 5} textAnchor="middle" className="text-xs fill-white" pointerEvents="none">
          {centralTerm || concepcyData?.central_concept || 'term'}
        </text>
      </g>

      {nodes.map((n, idx) => {
        const angle = (idx / nodes.length) * 2 * Math.PI;
        const x = centerX + Math.cos(angle) * radius;
        const y = centerY + Math.sin(angle) * radius;
        const color = RELATION_COLORS[n.relation] ?? '#06B6D4';

        return (
          <g key={`${n.relation}-${n.term}-${idx}`} className="group" role="button" tabIndex={0}>
            <line x1={centerX} y1={centerY} x2={x} y2={y} stroke="#6B7280" strokeWidth={1} />

            <circle
              cx={x}
              cy={y}
              r={14}
              fill={color}
              className="transition-transform group-hover:scale-110"
              onClick={() => onConceptSelect && onConceptSelect(n.term)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onConceptSelect && onConceptSelect(n.term);
                }
              }}
            />

            <text x={x} y={y + 4} textAnchor="middle" className="text-xs fill-white pointer-events-none">
              {n.term.length > 12 ? `${n.term.slice(0, 11)}…` : n.term}
            </text>

            {/* small relation label */}
            <text x={(centerX + x) / 2} y={(centerY + y) / 2 - 6} textAnchor="middle" className="text-xs text-gray-600">
              {n.relation}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

export default React.memo(TokenConceptChart);
