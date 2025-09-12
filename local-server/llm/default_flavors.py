"""
Default pipeline flavor definitions.

This module provides hard-coded default flavors for all pipeline types.
These defaults are available regardless of the current dataset and cannot be modified through the UI.
Users who want custom configurations should create new flavors.
"""

from typing import Dict
from datetime import datetime, timezone

from .models import PipelineFlavor, PipelineType, LLMConfig
from .prompts import DefinitionPromptTemplate


class DefaultFlavorProvider:
    """Provides default pipeline flavor configurations"""
    
    @staticmethod
    def get_default_flavor(pipeline: PipelineType) -> PipelineFlavor:
        """Get the default flavor for a specific pipeline type"""
        template = DefinitionPromptTemplate()
        now = datetime.now(timezone.utc)
        
        # Get prompts based on pipeline type
        if pipeline == PipelineType.SUGGEST_TERM_DEFINITION:
            system_prompt = template.get_term_definition_system_prompt()
            user_prompt = template.get_term_definition_user_prompt_template()
        elif pipeline == PipelineType.SUGGEST_LAYER_DEFINITION:
            system_prompt = template.get_layer_definition_system_prompt()
            user_prompt = template.get_layer_definition_user_prompt_template()
        elif pipeline == PipelineType.SUGGEST_DOMAIN_DEFINITION:
            system_prompt = template.get_domain_definition_system_prompt()
            user_prompt = template.get_domain_definition_user_prompt_template()
        else:
            raise ValueError(f"Unknown pipeline type: {pipeline}")
        
        # Create default flavor object
        return PipelineFlavor(
            id="default",  # Special ID for default flavors
            pipeline=pipeline,
            title="Default",
            llm_provider="openai",
            llm_model="gpt-3.5-turbo",
            llm_config=LLMConfig(temperature=0.0),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            version=1,
            enabled=True,
            last_updated=now,
            date_created=now
        )
    
    @staticmethod
    def get_all_default_flavors() -> Dict[PipelineType, PipelineFlavor]:
        """Get all default flavors as a dictionary"""
        return {
            pipeline_type: DefaultFlavorProvider.get_default_flavor(pipeline_type)
            for pipeline_type in PipelineType
        }
    
    @staticmethod
    def is_default_flavor(flavor_id: str) -> bool:
        """Check if a flavor ID represents a default flavor"""
        return flavor_id == "default"


# Template methods for user prompt templates (if not already in prompts.py)
def _get_default_user_prompt_templates():
    """Internal method to define default user prompt templates if needed"""
    return {
        PipelineType.SUGGEST_TERM_DEFINITION: """Based on the provided context, generate a 2-3 sentence definition for the term "{term}".

Context:
- Domain: {domain_title}
- Domain Definition: {domain_definition}
- Parent Term: {parent_term_title} 
- Parent Definition: {parent_term_definition}
- Relationship: {parent_relationship_predicate}

Component Terms:
{component_terms}

Current Definition: {current_definition}

Additional Context:
{additional_context}

Please provide:
1. A precise 2-3 sentence definition
2. Brief reasoning for your definitional choices
3. Any notable discrepancies between sources""",

        PipelineType.SUGGEST_LAYER_DEFINITION: """Based on the provided context, generate a 2-3 sentence definition for the layer "{layer_title}".

Context:
- Layer Title: {layer_title}
- Current Description: {layer_description}
- Parent Layer: {parent_layer_title}
- Parent Definition: {parent_layer_definition}
- Contained Domains: {contained_domains}
- Layer Purpose: {layer_purpose}

Current Definition: {current_definition}

Reference Context:
{reference_context}

Please provide:
1. A precise 2-3 sentence definition
2. Brief reasoning for your definitional choices
3. Any notable discrepancies between sources""",

        PipelineType.SUGGEST_DOMAIN_DEFINITION: """Based on the provided context, generate a 2-3 sentence definition for the domain "{domain_title}".

Context:
- Domain Title: {domain_title}
- Layer: {layer_title}
- Layer Definition: {layer_definition}
- Contained Terms: {contained_terms}
- Domain Purpose: {domain_purpose}

Current Definition: {current_definition}

Reference Context:
{reference_context}

Please provide:
1. A precise 2-3 sentence definition
2. Brief reasoning for your definitional choices
3. Any notable discrepancies between sources"""
    }
