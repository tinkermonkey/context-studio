"""
Service for populating default flavors on application startup.
"""

from .flavor_service import PipelineFlavorService
from .models import PipelineType, CreatePipelineFlavorRequest, LLMConfig
from .prompts import DefinitionPromptTemplate
from utils.logger import get_logger


class DefaultFlavorPopulator:
    """Populates default flavors for all pipeline types"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.flavor_service = PipelineFlavorService()
    
    async def populate_defaults(self) -> None:
        """Populate default flavors for all pipelines if they don't exist"""
        self.logger.info("Checking for default flavors...")
        
        template = DefinitionPromptTemplate()
        
        # Extract current prompts from existing code to move to database
        pipelines = [
            {
                "type": PipelineType.SUGGEST_TERM_DEFINITION,
                "system_prompt": template.get_term_definition_system_prompt(),
                "user_prompt": self._extract_term_user_prompt_template()
            },
            {
                "type": PipelineType.SUGGEST_LAYER_DEFINITION,
                "system_prompt": template.get_layer_definition_system_prompt(),
                "user_prompt": self._extract_layer_user_prompt_template()
            },
            {
                "type": PipelineType.SUGGEST_DOMAIN_DEFINITION,
                "system_prompt": template.get_domain_definition_system_prompt(),
                "user_prompt": self._extract_domain_user_prompt_template()
            }
        ]
        
        for pipeline_config in pipelines:
            try:
                # Check if default exists
                await self.flavor_service.get_flavor_by_title(
                    pipeline_config["type"], 
                    "Default"
                )
                self.logger.info(f"Default flavor already exists for {pipeline_config['type'].value}")
                
            except:
                # Create default flavor with current prompts from code
                self.logger.info(f"Creating default flavor for {pipeline_config['type'].value}")
                
                request = CreatePipelineFlavorRequest(
                    pipeline=pipeline_config["type"],
                    title="Default",
                    llm_provider="openai",
                    llm_model="gpt-3.5-turbo",
                    llm_config=LLMConfig(temperature=0.0),
                    system_prompt=pipeline_config["system_prompt"],
                    user_prompt=pipeline_config["user_prompt"],
                    enabled=True
                )
                
                await self.flavor_service.create_flavor(request)
                self.logger.info(f"Created default flavor for {pipeline_config['type'].value}")
    
    def _extract_term_user_prompt_template(self) -> str:
        """Extract the user prompt template from existing term definition logic"""
        # This represents the structure of the current create_term_definition_prompt method
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
    
    def _extract_layer_user_prompt_template(self) -> str:
        """Extract the user prompt template from existing layer definition logic"""
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
    
    def _extract_domain_user_prompt_template(self) -> str:
        """Extract the user prompt template from existing domain definition logic"""
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
