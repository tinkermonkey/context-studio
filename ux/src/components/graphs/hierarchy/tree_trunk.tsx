import React from 'react';
import { ChartStyles } from './tree_styles';

const TreeTrunk: React.FC = () => {
  // Since layout function ensures coordinates are set, we can safely assert they exist
  const x = 20;
  const y = 30;
  
  return (
    <g>
      <circle
        cx={x - 10}
        cy={y}
        r={10}
        style={ChartStyles.mainNode}
      />
    </g>
  );
};

export default TreeTrunk;