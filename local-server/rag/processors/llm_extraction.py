"""
Layer 1: LLM Extraction Processor

This processor performs LLM-based entity extraction enhanced by knowledge graph context.
It uses the pipeline_flavors system to extract entities with confidence scores.
"""
from typing import List, Dict, Any
import json

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

        try:
            # Format KG context for prompt
            kg_context_text = self._format_kg_context(kg_context)

            # Build extraction prompt
            prompt_context = {
                'text': input_data.text,
                'kg_context': kg_context_text,
                'kg_node_count': len(kg_context.kg_nodes),
                'format_instructions': '''Return a JSON object with this structure:
{
  "entities": [
    {
      "text": "entity text as it appears",
      "entity_type": "CONCEPT",
      "confidence": 0.95,
      "sentence_index": 0,
      "matched_kg_node": "node_id_if_matched"
    }
  ]
}'''
            }

            if input_data.enable_trace:
                trace_data['prompt_context'] = prompt_context

            # Execute LLM extraction
            # Create execution request
            execution_request = PipelineExecutionRequest(
                flavor_id=self.flavor_id,
                pipeline_type=PipelineType.EXTRACT_ENTITIES,
                context_data=prompt_context
            )

            # Execute pipeline synchronously - LLMService handles async internally
            response = self.llm_service.execute_pipeline_flavor_sync(execution_request)

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
            logger.error(f"LLM extraction failed: {e}", exc_info=True)
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
        Parse entities from LLM response content using structured JSON output.

        Args:
            response_content: LLM response text (expected to be JSON)
            original_text: Original input text
            kg_context: KG context for matching

        Returns:
            List of extracted entities
        """
        entities = []

        # Split text into sentences for sentence indexing
        sentences = [s.strip() for s in original_text.split('.') if s.strip()]

        try:
            # Try to parse as JSON first (structured output)
            response_json = json.loads(response_content)

            if 'entities' in response_json and isinstance(response_json['entities'], list):
                for entity_data in response_json['entities']:
                    try:
                        # Validate required fields
                        if 'text' not in entity_data:
                            logger.warning(f"Entity missing 'text' field: {entity_data}")
                            continue

                        entity_text = entity_data['text']

                        # Find entity in original text for character positions
                        start_char = original_text.lower().find(entity_text.lower())
                        if start_char == -1:
                            logger.debug(f"Entity '{entity_text}' not found in original text")
                            continue

                        end_char = start_char + len(entity_text)

                        # Determine sentence index
                        sentence_indices = []
                        if 'sentence_index' in entity_data:
                            sentence_indices = [entity_data['sentence_index']]
                        else:
                            # Find which sentence contains the entity
                            for sent_idx, sentence in enumerate(sentences):
                                if entity_text.lower() in sentence.lower():
                                    sentence_indices.append(sent_idx)

                        # Check for matched KG node
                        matched_kg_node = entity_data.get('matched_kg_node')
                        if not matched_kg_node:
                            # Try to match against KG context
                            for node in kg_context.kg_nodes:
                                if entity_text.lower() == node.title.lower() or \
                                   entity_text.lower() in node.title.lower() or \
                                   node.title.lower() in entity_text.lower():
                                    matched_kg_node = node.node_id
                                    break

                        # Get confidence (explicit mentions: 0.9-1.0)
                        confidence = float(entity_data.get('confidence', 0.95))
                        confidence = max(0.9, min(1.0, confidence))  # Clamp to [0.9, 1.0]

                        entity = ExtractedEntity(
                            text=entity_text,
                            entity_type=entity_data.get('entity_type', 'CONCEPT'),
                            confidence=confidence,
                            sentence_indices=sentence_indices,
                            matched_kg_node=matched_kg_node,
                            start_char=start_char,
                            end_char=end_char
                        )
                        entities.append(entity)

                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse entity data: {entity_data}, error: {e}")
                        continue

                logger.info(f"Parsed {len(entities)} entities from structured JSON response")
                return entities

        except json.JSONDecodeError:
            logger.debug("Response is not valid JSON, falling back to heuristic parsing")

        # Fallback: Use heuristic parsing if JSON parsing fails
        entities = self._fallback_parse_entities(response_content, original_text, sentences, kg_context)

        return entities

    def _fallback_parse_entities(
        self,
        response_content: str,
        original_text: str,
        sentences: List[str],
        kg_context: KGContextOutput
    ) -> List[ExtractedEntity]:
        """
        Fallback heuristic parser for non-JSON responses.

        Args:
            response_content: LLM response text
            original_text: Original input text
            sentences: Sentences from original text
            kg_context: KG context for matching

        Returns:
            List of extracted entities
        """
        entities = []

        # Fallback: Extract entities that appear in both KG context and original text
        logger.debug("Using fallback KG matching for entity extraction")
        for node in kg_context.kg_nodes[:10]:  # Check top 10 KG nodes
            node_title_lower = node.title.lower()
            if node_title_lower in original_text.lower():
                start_char = original_text.lower().find(node_title_lower)
                if start_char == -1:
                    continue

                end_char = start_char + len(node.title)

                # Find sentence index
                sent_indices = []
                for idx, sentence in enumerate(sentences):
                    if node_title_lower in sentence.lower():
                        sent_indices.append(idx)

                entity = ExtractedEntity(
                    text=node.title,
                    entity_type="CONCEPT",
                    confidence=0.90,  # Explicit mention from KG
                    sentence_indices=sent_indices if sent_indices else [0],
                    matched_kg_node=node.node_id,
                    start_char=start_char,
                    end_char=end_char
                )
                entities.append(entity)

        return entities
