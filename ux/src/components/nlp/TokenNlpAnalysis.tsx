import * as React from 'react';
import { Card, Badge } from 'flowbite-react';
import TokenSenseList from './TokenSenseList';
import NlpConceptChart from './NlpConceptChart';
import type { TokenData as BaseTokenData } from '@/api/services/nlp';

type TokenData = BaseTokenData & { is_stop?: boolean };

interface Props {
  token: TokenData;
}

export const TokenNlpAnalysis: React.FC<Props> = ({ token }) => {
  const [activeTab, setActiveTab] = React.useState<'senses' | 'concepts' | 'similar'>('senses');

  const wordnet = token.wordnet as any;
  const concepcy = token.concepcy as any;
  const sense2vec = token.sense2vec as any;

  const senses = (wordnet?.synsets || []).map((s: any) => ({
    root: s.lemmas ? s.lemmas[0] : undefined,
    name: s.name || s.synset || s.id || s[0],
    definition: s.definition || s.gloss || s.def || '',
    partOfSpeech: s.pos || s.partOfSpeech || '',
  }));

  const relations = Array.isArray(concepcy?.related_terms) ? concepcy.related_terms : [];

  return (
    <div className="space-y-3">
      <div>
        <h5 className="text-sm font-medium">Token</h5>
        <div className="p-2 bg-gray-50 rounded flex items-center justify-between">
          <div className="font-semibold">{token.text}</div>
          <div className="text-xs text-gray-500">{token.pos ?? token.tag}</div>
        </div>
      </div>

      <div>
        <div className="flex gap-2 border-b pb-2">
          <button
            className={`text-sm px-3 py-1 ${activeTab === 'senses' ? 'border-b-2 border-purple-500 text-purple-600' : 'text-gray-600'}`}
            onClick={() => setActiveTab('senses')}
          >
            Senses
          </button>
          <button
            className={`text-sm px-3 py-1 ${activeTab === 'concepts' ? 'border-b-2 border-purple-500 text-purple-600' : 'text-gray-600'}`}
            onClick={() => setActiveTab('concepts')}
          >
            Concepts
          </button>
          <button
            className={`text-sm px-3 py-1 ${activeTab === 'similar' ? 'border-b-2 border-purple-500 text-purple-600' : 'text-gray-600'}`}
            onClick={() => setActiveTab('similar')}
          >
            Similar
          </button>
        </div>

        <div className="pt-3">
          {activeTab === 'senses' && (
            <TokenSenseList
              senses={senses}
            />
          )}

          {activeTab === 'concepts' && (
            <div>
              {(wordnet?.synsets || concepcy?.related_terms) ? (
                <NlpConceptChart
                  data={{
                    text: token.text,
                    lemma: token.lemma || token.text,
                    pos: token.pos || token.tag || '',
                    concepcy: {
                      related_terms: relations
                    },
                    wordnet: {
                      synsets: (wordnet?.synsets || []).map((s: any) => ({
                        name: s.name || s.synset || s.id || s[0] || 'unknown',
                        definition: s.definition || s.gloss || s.def || '',
                        lemmas: s.lemmas || [],
                        pos: s.pos || s.partOfSpeech || token.pos || token.tag || '',
                        offset: s.offset || 0,
                        domain: s.domain || 'general'
                      })),
                      definitions: (wordnet?.synsets || []).map((s: any) => s.definition || s.gloss || s.def || '')
                    }
                  }}
                  config={{
                    "RelatedTo": 3,
                    "IsA": 3,
                    "HasA": 2,
                    "PartOf": 2,
                    "UsedFor": 2
                  }}
                />
              ) : (
                <div className="text-sm text-gray-500">No concept relationships available</div>
              )}
            </div>
          )}

          {activeTab === 'similar' && (
            <div>
              {sense2vec && Array.isArray(sense2vec.similar) && sense2vec.similar.length > 0 ? (
                <div className="space-y-2">
                  {sense2vec.similar.map((s: any, i: number) => (
                    <Card key={i} className="p-2">
                      <div className="flex justify-between">
                        <div className="text-sm">{s.term ?? s[0]}</div>
                        <div className="text-xs text-gray-500">{typeof (s.score ?? s[1]) === 'number' ? ((s.score ?? s[1]) * 100).toFixed(1) + '%' : ''}</div>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-gray-500">No similar terms available</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TokenNlpAnalysis;
