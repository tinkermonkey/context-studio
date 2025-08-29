import * as React from 'react';
import { Card, Badge } from 'flowbite-react';

interface WordNetSynset {
  name?: string;
  definition?: string;
  examples?: string[];
  partOfSpeech?: string;
}

interface WordNetData {
  synsets?: any[];
}

interface Props {
  // Accept either a pre-normalized list of senses or the raw wordnet data
  senses?: WordNetSynset[];
  wordnetData?: WordNetData;
  // Controlled selected index (optional)
  selectedIndex?: number;
  // Default selection for uncontrolled mode
  defaultSelection?: number;
  onSenseSelect?: (sense: WordNetSynset, index: number) => void;
}

export const TokenSenseList: React.FC<Props> = ({
  senses = [],
  wordnetData,
  selectedIndex,
  defaultSelection = 0,
  onSenseSelect,
}) => {
  // Normalize source: prefer explicit senses prop, otherwise extract from wordnetData
  const normalized: WordNetSynset[] = React.useMemo(() => {
    if (senses && senses.length > 0) return senses;
    const raw = wordnetData?.synsets ?? [];
    return raw.map((s: any) => ({
      name: s.name ?? s.synset ?? s.id ?? (s[0] as string),
      definition: s.definition ?? s.gloss ?? s.def ?? '',
      examples: s.examples ?? [],
      partOfSpeech: s.pos ?? s.partOfSpeech ?? '',
    }));
  }, [senses, wordnetData]);

  const [internalIndex, setInternalIndex] = React.useState<number>(defaultSelection ?? 0);

  // If consumer provides controlled selectedIndex, use it; otherwise use internal state
  const effectiveIndex = typeof selectedIndex === 'number' ? selectedIndex : internalIndex;

  React.useEffect(() => {
    // ensure default selection applies when senses change
    setInternalIndex(defaultSelection ?? 0);
  }, [defaultSelection, normalized.length]);

  if (!normalized || normalized.length === 0) {
    return <div className="text-sm text-gray-500">No word senses available</div>;
  }

  const handleSelect = (sense: WordNetSynset, idx: number) => {
    if (typeof selectedIndex !== 'number') {
      setInternalIndex(idx);
    }
    onSenseSelect && onSenseSelect(sense, idx);
  };

  return (
    <div className="space-y-2" role="list">
      {normalized.map((sense, index) => (
        <Card
          key={sense.name ?? index}
          className={`cursor-pointer transition-colors ${effectiveIndex === index ? 'ring-2 ring-purple-500' : 'hover:bg-gray-50'}`}
          onClick={() => handleSelect(sense, index)}
          role="listitem"
          aria-selected={effectiveIndex === index}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleSelect(sense, index);
            }
          }}
        >
          <div className="p-3">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <h4 className="font-medium text-gray-900">{sense.name ?? 'sense'}</h4>
                <p className="text-sm text-gray-600 mt-1">{sense.definition}</p>
                {sense.examples && sense.examples.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs text-gray-500">Example:</p>
                    <p className="text-xs italic text-gray-600">"{sense.examples[0]}"</p>
                  </div>
                )}
              </div>
              <Badge color={effectiveIndex === index ? 'purple' : 'gray'} size="sm">
                {sense.partOfSpeech}
              </Badge>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
};

export default React.memo(TokenSenseList);
