import * as React from 'react';
import { Card, Badge, Button } from 'flowbite-react';
import type { EntityData as BaseEntityData } from '@/api/services/nlp';

// Local augmentation for optional external links and similarity
type EntityData = BaseEntityData & {
  dbpedia?: { uri?: string; label?: string; similarity?: number } | null;
  label?: string; // fallback label
};

interface Props {
  entities: EntityData[];
  onEntitySelect?: (entity: EntityData) => void;
  className?: string;
}

const NlpEntityAnalysis: React.FC<Props> = ({ entities = [], onEntitySelect, className }) => {
  if (!entities || entities.length === 0) {
    return <div className={`text-sm text-gray-500 py-2 ${className ?? ''}`}>No entities detected</div>;
  }

  return (
    <div className={`space-y-3 ${className ?? ''}`}>
      {entities.map((entity: EntityData, idx: number) => {
        const key = `${entity.text ?? entity.label ?? idx}-${idx}`;
        const label = entity.label ?? (entity as any).type ?? 'Entity';
        const db = entity.dbpedia;

        return (
          <Card key={key} className="p-3">
            <div className="flex justify-between items-start gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h4 className="font-medium text-gray-900">{(entity as any).text ?? (entity as any).name ?? 'unknown'}</h4>
                  <Badge color="blue" size="sm">{label}</Badge>
                </div>

                {db?.uri && (
                  <div className="mt-2">
                    {db.label && <p className="text-sm text-gray-600">{db.label}</p>}
                    <a
                      href={db.uri}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 text-sm flex items-center gap-1"
                    >
                      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                        <path d="M14 3h7v7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M10 14L21 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M21 21H3V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      View on DBpedia
                    </a>
                  </div>
                )}
              </div>

              <div className="text-right flex flex-col items-end gap-2">
                {db?.similarity != null && (
                  <div>
                    <p className="text-xs text-gray-500">Confidence</p>
                    <p className="text-sm font-medium">{(db.similarity * 100).toFixed(1)}%</p>
                  </div>
                )}

                <div>
                  <Button size="sm" color="light" onClick={() => onEntitySelect && onEntitySelect(entity)}>
                    Select
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
};

export default NlpEntityAnalysis;
 
