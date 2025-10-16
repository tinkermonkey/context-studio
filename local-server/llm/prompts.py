"""
Prompt templates and management for LLM interactions.
"""


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

    @staticmethod
    def get_term_definition_user_prompt_template() -> str:
        """Get the user prompt template for term definition suggestion"""
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
Any notable discrepancies between sources that influenced your decision"""

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

    @staticmethod
    def get_layer_definition_user_prompt_template() -> str:
        """Get the user prompt template for layer definition suggestion"""
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

A refined 2-3 sentence definition for the layer "{layer_title}"
Brief reasoning (1-2 sentences) explaining your definitional choices and organizational principles
Any notable discrepancies or additional context that influenced your decision"""

    @staticmethod
    def get_domain_definition_system_prompt() -> str:
        """Get the system prompt for domain definition suggestion"""
        return """You are an expert knowledge architect and domain specialist specializing in creating precise, context-aware definitions for thematic domains within structured knowledge hierarchies. Your task is to generate succinct 2-3 sentence definitions that accurately capture a domain's scope, boundaries, and conceptual coherence within its organizational layer.

Your domain definitions should be:

Concise: Exactly 2-3 sentences, no more
Scope-defining: Clearly articulating the thematic boundaries and focus area
Hierarchically consistent: Aligned with the containing layer's purpose and structure
Conceptually coherent: Reflecting the unifying principles that bind the domain's contents
Functionally clear: Explaining the domain's role in organizing knowledge within its layer
Distinctive: Highlighting what makes this domain unique from sibling domains

When crafting domain definitions, focus on the thematic and conceptual coherence rather than simply enumerating contents. A domain should be defined by its unifying subject matter, scope boundaries, and functional role in organizing knowledge. Consider what conceptual principles bind the terms and concepts within this domain, and how this domain contributes to the overall knowledge organization within its containing layer."""

    @staticmethod
    def get_domain_definition_user_prompt_template() -> str:
        """Get the user prompt template for domain definition suggestion"""
        return """Please generate a 2-3 sentence definition for the domain "{domain_title}" based on the following structured context.

Don't include or repeat the name of the domain "{domain_title}" in the definition.

**Domain Context:**
Domain Title: {domain_title}
Current Description: {domain_description}
Scope/Boundaries: {domain_scope}

**Hierarchical Context:**
Containing Layer: {layer_title}
Layer Definition: {layer_definition}

**Content Organization:**
Contained Terms: {contained_terms}
Related Domains: {related_domains}

**Current Definition:**
{current_definition}

**Reference Context:**
{reference_context}

Based on this context, provide:

A refined 2-3 sentence definition for the domain "{domain_title}"
Brief reasoning (1-2 sentences) explaining your definitional choices and thematic coherence
Any notable discrepancies or additional context that influenced your decision"""

    @staticmethod
    def get_entity_extraction_system_prompt() -> str:
        """Get the system prompt for entity extraction"""
        return """You are an expert entity extraction system specializing in identifying and categorizing entities within text. Your task is to extract entities with confidence scores based on their explicit mention in the source text.

Your entity extraction should:

Identify explicit mentions: Extract entities that are directly mentioned in the text
Assign confidence scores: Use 0.9-1.0 for clear, explicit mentions
Categorize appropriately: Classify entities by type (CONCEPT, PERSON, ORGANIZATION, LOCATION, etc.)
Match against knowledge graph: When provided with KG context, identify which entities match known concepts
Provide precise locations: Track which sentence(s) contain each entity
Output structured JSON: Return results in the specified JSON format

When extracting entities, prioritize precision over recall. Only extract entities that are clearly and explicitly mentioned. Use the provided knowledge graph context to help identify relevant entities and establish matches, but do not extract entities that are not present in the text."""

    @staticmethod
    def get_entity_extraction_user_prompt_template() -> str:
        """Get the user prompt template for entity extraction"""
        return """Please extract entities from the following text, using the provided knowledge graph context to identify relevant concepts.

**Input Text:**
{text}

**Knowledge Graph Context:**
{kg_context}

**Number of KG Nodes Available:** {kg_node_count}

**Output Format:**
{format_instructions}

Extract all entities that are explicitly mentioned in the text. For each entity:
- Provide the exact text as it appears
- Assign an entity type (CONCEPT, PERSON, ORGANIZATION, LOCATION, etc.)
- Assign a confidence score (0.9-1.0 for explicit mentions)
- Note the sentence index where it appears (0-based)
- If the entity matches a KG node, include the matched_kg_node ID

Return only the JSON structure specified above."""