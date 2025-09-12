/**
 * Type definitions for NLP node context data structures
 */

export interface NodeContext {
  type: "input" | "sense" | "relation";
  text?: string;
  lemma?: string;
  pos?: string;
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
