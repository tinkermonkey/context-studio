/**
 * Type definitions for NLP node context data structures
 */

export interface NodeContext {
  type: "input" | "sense" | "relation";
  text?: string;
  lemma?: string;
  pos?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  token?: any;
  synset?: {
    name: string;
    definition: string;
    lemmas: string[];
    pos: string;
    offset: number;
    domain: string;
  };
  relationType?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  relation?: any;
  targetTerm?: {
    label: string;
    language: string;
    id: string;
    term: string;
  };
  index?: number;
}

export interface SelectedNodeContextEntry {
  nodeId: string;
  context: NodeContext;
}
