"""
Layer 1: LLM Extraction Processor

This processor performs LLM-based entity extraction enhanced by knowledge graph context.
It uses the pipeline_flavors system to extract entities with confidence scores.
"""
from typing import List, Dict, Any
import re
import asyncio

from rag.processors.models import (
    ProcessorInput,
    LLMExtractionOutput,
    ExtractedEntity,
    KGContextOutput
)
from llm.service import LLMService
from llm.models import PipelineType, PipelineExecutionRequest
from utils.logger import get_logger

logger = get_logger(__name__)


class LLMExtractionProcessor:
    """
    Layer 1: LLM-Based Entity Extraction with Knowledge Graph Context

    Performs LLM-based entity extraction enhanced by knowledge graph context:
    - Accepts paragraph-level input text and aggregated relevant KG subset
    - Extracts entities using LLM with KG context awareness
    - Returns recognized entities with confidence scores (0.9-1.0 for explicit mentions)
    - Identifies entities that match against provided KG subset
    - Records which sentence(s) each entity was extracted from
    """

    def __init__(self, flavor_id: str = "default"):
        """
        Initialize LLM Extraction Processor.

        Args:
            flavor_id: Pipeline flavor to use for LLM extraction (default: "default")
        """
        self.flavor_id = flavor_id
        self.llm_service = LLMService()
        logger.info(f"LLMExtractionProcessor initialized with flavor_id={flavor_id}")

    def process(
        self,
        input_data: ProcessorInput,
        kg_context: KGContextOutput
    ) -> LLMExtractionOutput:
        """
        Process input text with KG context to extract entities.

        Args:
            input_data: Input containing text and trace settings
            kg_context: KG context from Layer 0

        Returns:
            LLMExtractionOutput with extracted entities
        """
        logger.info("Starting LLM extraction with KG context")
        trace_data = {} if input_data.enable_trace else {}

        # Format KG context for prompt
        kg_context_text = self._format_kg_context(kg_context)

        # Build extraction prompt
        prompt_context = {
            'text': input_data.text,
            'kg_context': kg_context_text,
            'kg_node_count': len(kg_context.kg_nodes)
        }

        if input_data.enable_trace:
            trace_data['prompt_context'] = prompt_context

        # Execute LLM extraction
        try:
            # Create execution request
            execution_request = PipelineExecutionRequest(
                flavor_id=self.flavor_id,
                pipeline_type=PipelineType.SUGGEST_TERM_DEFINITION,  # Reusing existing pipeline type
                context_data=prompt_context
            )

            # Execute pipeline synchronously (wrap async call)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    self.llm_service.execute_pipeline_flavor(execution_request)
                )
            finally:
                loop.close()

            # Parse entities from response
            entities = self._parse_entities_from_response(
                response.response_content,
                input_data.text,
                kg_context
            )

            if input_data.enable_trace:
                trace_data['llm_response'] = response.response_content
                trace_data['execution_id'] = response.execution_id
                trace_data['entities_extracted'] = len(entities)
                if response.token_usage:
                    trace_data['token_usage'] = response.token_usage

            logger.info(f"Extracted {len(entities)} entities via LLM")

            return LLMExtractionOutput(
                entities=entities,
                kg_context_size=len(kg_context.kg_nodes),
                token_usage=response.token_usage,
                trace_data=trace_data
            )

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            # Return empty result on error
            return LLMExtractionOutput(
                entities=[],
                kg_context_size=len(kg_context.kg_nodes),
                token_usage=None,
                trace_data=trace_data
            )

    def _format_kg_context(self, kg_context: KGContextOutput) -> str:
        """
        Format KG context for inclusion in LLM prompt.

        Args:
            kg_context: KG context output from Layer 0

        Returns:
            Formatted string representation of KG context
        """
        if not kg_context.kg_nodes:
            return "No knowledge graph context available."

        # Group by node type
        nodes_by_type: Dict[str, List[str]] = {}
        for node in kg_context.kg_nodes[:20]:  # Limit to top 20 for prompt
            node_type = node.node_type
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []

            node_desc = f"- {node.title}"
            if node.definition:
                node_desc += f": {node.definition[:100]}"  # Truncate long definitions
            nodes_by_type[node_type].append(node_desc)

        # Build formatted context
        context_parts = ["Relevant Knowledge Graph Context:"]
        for node_type, nodes in nodes_by_type.items():
            context_parts.append(f"\n{node_type.upper()}S:")
            context_parts.extend(nodes[:10])  # Limit per type

        return "\n".join(context_parts)

    def _parse_entities_from_response(
        self,
        response_content: str,
        original_text: str,
        kg_context: KGContextOutput
    ) -> List[ExtractedEntity]:
        """
        Parse entities from LLM response content.

        This is a heuristic parser that attempts to extract entity mentions
        from the LLM's response. In production, structured output would be preferred.

        Args:
            response_content: LLM response text
            original_text: Original input text
            kg_context: KG context for matching

        Returns:
            List of extracted entities
        """
        entities = []

        # Split text into sentences for sentence indexing
        doc = self.llm_service.flavor_service  # Access through service
        # Use simple sentence splitting for now
        sentences = [s.strip() for s in original_text.split('.') if s.strip()]

        # Heuristic: Look for entity mentions in response
        # This is a simplified parser - in production would use structured output
        lines = response_content.split('\n')
        current_entity = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for entity patterns like "Entity: <text>" or "- <text>"
            entity_match = re.match(r'^(?:Entity|Concept|Term|-):\s*(.+)$', line, re.IGNORECASE)
            if entity_match:
                entity_text = entity_match.group(1).strip()

                # Find entity in original text
                for sent_idx, sentence in enumerate(sentences):
                    if entity_text.lower() in sentence.lower():
                        # Find character positions
                        start_char = original_text.lower().find(entity_text.lower())
                        if start_char != -1:
                            end_char = start_char + len(entity_text)

                            # Check if entity matches any KG node
                            matched_kg_node = None
                            for node in kg_context.kg_nodes:
                                if entity_text.lower() == node.title.lower() or \
                                   entity_text.lower() in node.title.lower() or \
                                   node.title.lower() in entity_text.lower():
                                    matched_kg_node = node.node_id
                                    break

                            entity = ExtractedEntity(
                                text=entity_text,
                                entity_type="CONCEPT",  # Default type
                                confidence=0.95 if matched_kg_node else 0.92,  # Explicit mention confidence
                                sentence_indices=[sent_idx],
                                matched_kg_node=matched_kg_node,
                                start_char=start_char,
                                end_char=end_char
                            )
                            entities.append(entity)
                            break

        # Fallback: Extract entities that appear in both KG context and original text
        if not entities:
            logger.debug("No entities found in response, falling back to KG matching")
            for node in kg_context.kg_nodes[:10]:  # Check top 10 KG nodes
                node_title_lower = node.title.lower()
                if node_title_lower in original_text.lower():
                    start_char = original_text.lower().find(node_title_lower)
                    end_char = start_char + len(node.title)

                    # Find sentence index
                    sent_idx = 0
                    for idx, sentence in enumerate(sentences):
                        if node_title_lower in sentence.lower():
                            sent_idx = idx
                            break

                    entity = ExtractedEntity(
                        text=node.title,
                        entity_type="CONCEPT",
                        confidence=0.90,  # Explicit mention from KG
                        sentence_indices=[sent_idx],
                        matched_kg_node=node.node_id,
                        start_char=start_char,
                        end_char=end_char
                    )
                    entities.append(entity)

        return entities
