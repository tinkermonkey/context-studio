import * as React from 'react';
import { Badge } from 'flowbite-react';
import type { TokenData as BaseTokenData } from '@/api/services/nlp';

// Local augmentation: spaCy responses include is_stop; keep it optional
type TokenData = BaseTokenData & { is_stop?: boolean };

interface Props {
  tokens: TokenData[];
  selectedToken?: TokenData | null;
  onTokenSelect: (token: TokenData) => void;
  className?: string;
}

const TokenSelectionList: React.FC<Props> = ({
  tokens = [],
  selectedToken = null,
  onTokenSelect,
  className,
}) => {
  const filtered = React.useMemo(() => (tokens || []).filter((t) => t.is_stop !== true), [tokens]);

  if (!filtered || filtered.length === 0) {
    return <div className={`text-sm text-gray-500 py-2 ${className ?? ''}`}>No non-stop tokens available</div>;
  }

  return (
    <div className={`flex flex-wrap gap-2 ${className ?? ''}`}>
      {filtered.map((token) => (
        <Badge
          key={`${token.text}-${token.start ?? 0}`}
          color={selectedToken?.text === token.text && selectedToken?.start === token.start ? 'purple' : 'gray'}
          className="cursor-pointer hover:bg-purple-50"
          onClick={() => onTokenSelect(token)}
        >
          <span className="mr-1 font-medium">{token.text}</span>
          {token.wordnet && <span className="ml-1" aria-hidden>📚</span>}
          {token.concepcy && <span className="ml-1" aria-hidden>🧠</span>}
          {token.sense2vec && <span className="ml-1" aria-hidden>🔁</span>}
        </Badge>
      ))}
    </div>
  );
};

export default React.memo(TokenSelectionList);
