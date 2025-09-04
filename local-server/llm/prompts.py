"""
Prompt templates and management for LLM interactions.
"""

from typing import List

from .models import (
    DefinitionSuggestionRequest, 
    LayerDefinitionRequest,
    DomainDefinitionRequest,
    ComponentTerm, 
    SelectedRelation
)


class DefinitionPromptTemplate:
    """Manages prompt templates for term definition suggestion"""
    
    @staticmethod
    def get_term_definition_system_prompt() -> str:
        """Get the system prompt for term definition suggestion"""
        return """You are an expert ontologist and taxonomist specializing in creating precise, context-aware definitions for terms within structured knowledge domains. Your task is to generate succinct 2-3 sentence definitions that accurately capture a term's meaning within its specific domain context while maintaining consistency with hierarchical relationships and broader taxonomic structures.

Your term definitions should be:

Concise: Exactly 2-3 sentences, no more
Contextually precise: Tailored to the specific domain provided
Hierarchically consistent: Aligned with parent term definitions and relationships
Compositionally aware: For compound terms, synthesize meanings from component parts while capturing the emergent concept
Distinctive: Highlighting what makes this term unique within its taxonomic level
Authoritative: Drawing from provided reference sources while adapting to domain context

When crafting term definitions, prioritize domain-specific usage over general dictionary definitions. For compound terms like "apple sauce," consider how the component meanings ("apple" + "sauce") combine to create a distinct concept that may be more than the sum of its parts. Ensure your definition would allow someone to correctly classify instances of this concept and distinguish it from sibling terms at the same taxonomic level. If contradictions exist between sources, favor domain context over general references, and note any significant discrepancies in your reasoning."""

    def create_term_definition_prompt(self, request: DefinitionSuggestionRequest, format_instructions: str) -> str:
        """Create the user prompt with the provided context for term definition"""
        
        # Format component terms
        component_definitions = self._format_component_terms(request.component_terms)
        
        # Format ConceptNet relations
        conceptnet_relations = self._format_conceptnet_relations(request.component_terms)
        
        # Format other context fields
        wikidata_context = self._format_context_dict(request.wikidata_context)
        dbpedia_context = self._format_context_dict(request.dbpedia_context)

        prompt = f"""Please generate a 2-3 sentence definition for the term "{request.term}" based on the following structured context.

Don't include or repeat the name of the term "{request.term}" in the definition.

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

A refined 2-3 sentence definition for the term "{request.term}"
Brief reasoning (1-2 sentences) explaining your definitional choices, particularly how component meanings informed the compound definition
Any notable discrepancies between sources that influenced your decision

Format your response as:
Definition: [Your 2-3 sentence definition]
Reasoning: [Your brief explanation]
Discrepancies: [any noted discrepancies or leave blank]"""
        
        return prompt
    
    @staticmethod
    def get_layer_definition_system_prompt() -> str:
        """Get the system prompt for layer definition suggestion"""
        return """You are an expert knowledge architect and information scientist specializing in creating precise, context-aware definitions for conceptual layers within structured knowledge domains. Your task is to generate succinct 2-3 sentence definitions that accurately capture a layer's purpose, scope, and organizational role within the broader knowledge hierarchy.

Your layer definitions should be:

Concise: Exactly 2-3 sentences, no more
Scope-defining: Clearly articulating the boundaries and purpose of the layer
Hierarchically aware: Understanding the layer's position relative to parent layers and contained domains
Organizationally coherent: Reflecting how the layer groups and organizes related domains
Functionally precise: Explaining the layer's role in the overall knowledge structure
Contextually appropriate: Tailored to the specific knowledge domain or organizational context

When crafting layer definitions, focus on the organizational and conceptual purpose rather than simply listing contents. A layer should be defined by its unifying principles, scope boundaries, and functional role in organizing knowledge. Consider how this layer helps users navigate and understand the knowledge space, and what makes it a meaningful organizational unit distinct from other layers at the same hierarchical level."""

    def create_layer_definition_prompt(self, request: LayerDefinitionRequest, format_instructions: str) -> str:
        """Create the user prompt with the provided context for layer definition"""
        
        # Format contained domains
        contained_domains_text = ", ".join(request.contained_domains) if request.contained_domains else "Not specified"
        
        # Format reference context
        reference_context = self._format_context_dict(request.reference_context)

        prompt = f"""Please generate a 2-3 sentence definition for the layer "{request.layer_title}" based on the following structured context.

Don't include or repeat the name of the layer "{request.layer_title}" in the definition.

**Layer Context:**
Layer Title: {request.layer_title}
Current Description: {request.layer_description or "Not specified"}
Purpose/Role: {request.layer_purpose or "Not specified"}

**Hierarchical Context:**
Parent Layer: {request.parent_layer_title or "Not specified"}
Parent Layer Definition: {request.parent_layer_definition or "Not specified"}

**Organizational Context:**
Contained Domains: {contained_domains_text}

**Current Definition:**
{request.current_definition or "Not specified"}

**Reference Context:**
{reference_context}

Based on this context, provide:

A refined 2-3 sentence definition for the layer "{request.layer_title}" that captures its organizational purpose and scope
Brief reasoning (1-2 sentences) explaining your definitional choices, particularly how the layer's role and contained domains informed the definition
Any notable discrepancies or organizational insights that influenced your decision

Format your response as:
Definition: [Your 2-3 sentence definition]
Reasoning: [Your brief explanation]
Discrepancies: [any noted discrepancies or leave blank]"""
        
        return prompt

    @staticmethod
    def get_domain_definition_system_prompt() -> str:
        """Get the system prompt for domain definition suggestion"""
        return """You are an expert domain analyst and knowledge architect specializing in creating precise, context-aware definitions for knowledge domains within structured information systems. Your task is to generate succinct 2-3 sentence definitions that accurately capture a domain's scope, boundaries, and thematic coherence within its organizational context.

Your domain definitions should be:

Concise: Exactly 2-3 sentences, no more
Scope-defining: Clearly establishing the thematic boundaries and coverage area
Thematically coherent: Reflecting the unifying concepts or subject matter
Contextually positioned: Understanding the domain's role within its containing layer
Content-aware: Informed by but not limited to the terms and concepts contained within
Distinctive: Highlighting what makes this domain unique within its layer
Functionally clear: Explaining the domain's purpose in organizing related knowledge

When crafting domain definitions, focus on the thematic and conceptual coherence rather than simply enumerating contents. A domain should be defined by its subject matter boundaries, conceptual unity, and functional role in organizing related terms and concepts. Consider what unifying principles bring the contained terms together and what distinguishes this domain from related domains in the same layer."""

    def create_domain_definition_prompt(self, request: DomainDefinitionRequest, format_instructions: str) -> str:
        """Create the user prompt with the provided context for domain definition"""
        
        # Format contained terms
        contained_terms_text = ", ".join(request.contained_terms) if request.contained_terms else "Not specified"
        
        # Format related domains
        related_domains_text = ", ".join(request.related_domains) if request.related_domains else "Not specified"
        
        # Format reference context
        reference_context = self._format_context_dict(request.reference_context)

        prompt = f"""Please generate a 2-3 sentence definition for the domain "{request.domain_title}" based on the following structured context.

Don't include or repeat the name of the domain "{request.domain_title}" in the definition.

**Domain Context:**
Domain Title: {request.domain_title}
Current Description: {request.domain_description or "Not specified"}
Scope: {request.domain_scope or "Not specified"}

**Hierarchical Context:**
Containing Layer: {request.layer_title or "Not specified"}
Layer Definition: {request.layer_definition or "Not specified"}

**Content Context:**
Contained Terms: {contained_terms_text}
Related Domains: {related_domains_text}

**Current Definition:**
{request.current_definition or "Not specified"}

**Reference Context:**
{reference_context}

Based on this context, provide:

A refined 2-3 sentence definition for the domain "{request.domain_title}" that captures its thematic scope and conceptual boundaries
Brief reasoning (1-2 sentences) explaining your definitional choices, particularly how the contained terms and domain scope informed the definition
Any notable discrepancies or thematic insights that influenced your decision

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
    
    # 11.2.7.2 Prompt Template Updates - Template extraction methods for database storage
    
    @staticmethod
    def get_term_definition_user_prompt_template() -> str:
        """Get the user prompt template for term definition"""
        return """Please generate a 2-3 sentence definition for the term "{term}" based on the following structured context.

Don't include or repeat the name of the term "{term}" in the definition.

**Domain Context:**
Domain: {domain_title}
Definition: {domain_definition}

**Hierarchical Context:**
Term: {term}
Parent Term: {parent_term_title}
Parent Definition: {parent_term_definition}
Relationship to Parent: {parent_relationship_predicate}

**Component Terms:**
{component_terms}

**Current Definition:**
{current_definition}

**Reference Sources:**
ConceptNet Relations: {conceptnet_relations}
WikiData Context: {wikidata_context}
DBpedia Context: {dbpedia_context}

Based on this context, provide:

A refined 2-3 sentence definition for the term "{term}"
Brief reasoning (1-2 sentences) explaining your definitional choices, particularly how component meanings informed the compound definition
Any notable discrepancies between sources that influenced your decision

Format your response as:
Definition: [Your 2-3 sentence definition]
Reasoning: [Your brief explanation]
Discrepancies: [any noted discrepancies or leave blank]"""
    
    @staticmethod
    def get_layer_definition_user_prompt_template() -> str:
        """Get the user prompt template for layer definition"""
        return """Please generate a 2-3 sentence definition for the layer "{layer_title}" based on the following structured context.

Don't include or repeat the name of the layer "{layer_title}" in the definition.

**Layer Context:**
Layer Title: {layer_title}
Current Description: {layer_description}
Purpose/Role: {layer_purpose}

**Hierarchical Context:**
Parent Layer: {parent_layer_title}
Parent Layer Definition: {parent_layer_definition}

**Organizational Context:**
Contained Domains: {contained_domains}

**Current Definition:**
{current_definition}

**Reference Context:**
{reference_context}

Based on this context, provide:

A refined 2-3 sentence definition for the layer "{layer_title}" that captures its organizational purpose and scope
Brief reasoning (1-2 sentences) explaining your definitional choices, particularly how the layer's role and contained domains informed the definition
Any notable discrepancies or organizational insights that influenced your decision

Format your response as:
Definition: [Your 2-3 sentence definition]
Reasoning: [Your brief explanation]
Discrepancies: [any noted discrepancies or leave blank]"""
    
    @staticmethod
    def get_domain_definition_user_prompt_template() -> str:
        """Get the user prompt template for domain definition"""
        return """Please generate a 2-3 sentence definition for the domain "{domain_title}" based on the following structured context.

Don't include or repeat the name of the domain "{domain_title}" in the definition.

**Domain Context:**
Domain Title: {domain_title}
Current Description: {domain_description}
Scope: {domain_scope}

**Hierarchical Context:**
Containing Layer: {layer_title}
Layer Definition: {layer_definition}

**Content Context:**
Contained Terms: {contained_terms}
Related Domains: {related_domains}

**Current Definition:**
{current_definition}

**Reference Context:**
{reference_context}

Based on this context, provide:

A refined 2-3 sentence definition for the domain "{domain_title}" that captures its thematic scope and conceptual boundaries
Brief reasoning (1-2 sentences) explaining your definitional choices, particularly how the contained terms and domain scope informed the definition
Any notable discrepancies or thematic insights that influenced your decision

Format your response as:
Definition: [Your 2-3 sentence definition]
Reasoning: [Your brief explanation]
Discrepancies: [any noted discrepancies or leave blank]"""
