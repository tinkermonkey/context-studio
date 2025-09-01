"""
Prompt templates and management for LLM interactions.
"""

from typing import List
from .models import DefinitionSuggestionRequest, ComponentTerm, SelectedRelation


class DefinitionPromptTemplate:
    """Manages prompt templates for definition suggestion"""
    
    @staticmethod
    def get_system_prompt() -> str:
        """Get the system prompt for definition suggestion"""
        return """You are an expert ontologist and taxonomist specializing in creating precise, context-aware definitions for terms within structured knowledge domains. Your task is to generate succinct 2-3 sentence definitions that accurately capture a term's meaning within its specific domain context while maintaining consistency with hierarchical relationships and broader taxonomic structures.

Your definitions should be:

Concise: Exactly 2-3 sentences, no more
Contextually precise: Tailored to the specific domain provided
Hierarchically consistent: Aligned with parent term definitions and relationships
Compositionally aware: For compound terms, synthesize meanings from component parts while capturing the emergent concept
Distinctive: Highlighting what makes this term unique within its taxonomic level
Authoritative: Drawing from provided reference sources while adapting to domain context

When crafting definitions, prioritize domain-specific usage over general dictionary definitions. For compound terms like "apple sauce," consider how the component meanings ("apple" + "sauce") combine to create a distinct concept that may be more than the sum of its parts. Ensure your definition would allow someone to correctly classify instances of this concept and distinguish it from sibling terms at the same taxonomic level. If contradictions exist between sources, favor domain context over general references, and note any significant discrepancies in your reasoning."""

    def create_prompt(self, request: DefinitionSuggestionRequest, format_instructions: str) -> str:
        """Create the user prompt with the provided context"""
        
        # Format component terms
        component_definitions = self._format_component_terms(request.component_terms)
        
        # Format ConceptNet relations
        conceptnet_relations = self._format_conceptnet_relations(request.component_terms)
        
        # Format other context fields
        wikidata_context = self._format_context_dict(request.wikidata_context)
        dbpedia_context = self._format_context_dict(request.dbpedia_context)
        
        prompt = f"""Please generate a 2-3 sentence definition for the term "{request.term}" based on the following structured context:

**Domain Context:**
Domain: {request.domain_title or "Not specified"}
Definition: {request.domain_definition or "Not specified"}

**Hierarchical Context:**
Term: {request.term}
Parent Term: {request.parent_term_title or "Not specified"}
Parent Definition: {request.parent_term_definition or "Not specified"}
Relationship to Parent: {request.parent_relationship_predicate or "Not specified"}

**Component Terms:**
{component_definitions}

**Current Definition:**
{request.current_definition or "Not specified"}

**Reference Sources:**
ConceptNet Relations: {conceptnet_relations}
WikiData Context: {wikidata_context}
DBpedia Context: {dbpedia_context}

Based on this context, provide:

A refined 2-3 sentence definition for "{request.term}"
Brief reasoning (1-2 sentences) explaining your definitional choices, particularly how component meanings informed the compound definition
Any notable discrepancies between sources that influenced your decision

Format your response as:
Definition: [Your 2-3 sentence definition]
Reasoning: [Your brief explanation]
Discrepancies: [any noted discrepancies or leave blank]"""
        
        return prompt
    
    def _format_component_terms(self, component_terms: List[ComponentTerm]) -> str:
        """Format component terms for the prompt"""
        if not component_terms:
            return "Not specified"
        
        formatted = []
        for term in component_terms:
            definitions = "; ".join(term.selected_definitions) if term.selected_definitions else "No definitions"
            relations = self._format_selected_relations(term.selected_relations) if term.selected_relations else "No relations"
            
            formatted.append(f"- {term.text}: {definitions}")
            if relations != "No relations":
                formatted.append(f"  Relations: {relations}")
        
        return "\n".join(formatted)
    
    def _format_selected_relations(self, relations: List[SelectedRelation]) -> str:
        """Format selected relations for a component term"""
        if not relations:
            return "No relations"
        
        formatted = []
        for rel in relations:
            formatted.append(f"{rel.predicate} → {rel.object} (weight: {rel.weight})")
        
        return "; ".join(formatted)
    
    def _format_conceptnet_relations(self, component_terms: List[ComponentTerm]) -> str:
        """Extract and format ConceptNet relations from component terms"""
        all_relations = []
        for term in component_terms:
            if term.selected_relations:
                for rel in term.selected_relations:
                    all_relations.append(f"{term.text} {rel.predicate} {rel.object}")
        
        return "; ".join(all_relations) if all_relations else "Not specified"
    
    def _format_context_dict(self, context_dict: dict) -> str:
        """Format a context dictionary for display"""
        if not context_dict:
            return "Not specified"
        
        # For now, just convert to string representation
        # This could be enhanced to format specific known structures
        return str(context_dict)
