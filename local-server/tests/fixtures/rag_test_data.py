"""
Shared test fixtures and realistic data for RAG Pipeline tests.

This module provides reusable test data including:
- Realistic multi-domain paragraphs
- Expected entity extraction outputs
- Test knowledge graph data
- Mock processor outputs
"""

# Realistic test paragraphs across multiple domains
REALISTIC_TEST_PARAGRAPHS = {
    "ai_machine_learning": {
        "short": "Machine learning algorithms learn patterns from data without explicit programming.",  # noqa: E501

        "medium": (
            "Machine learning is a subset of artificial intelligence that focuses on developing "  # noqa: E501
            "algorithms that can learn from and make predictions based on data. Neural networks, "  # noqa: E501
            "inspired by biological neural systems, have become particularly effective at pattern "  # noqa: E501
            "recognition tasks. Deep learning uses multi-layered neural networks and has "  # noqa: E501
            "revolutionized fields such as computer vision and natural language processing."  # noqa: E501
        ),

        "long": (
            "Machine learning is a subset of artificial intelligence that focuses on developing "  # noqa: E501
            "algorithms that can learn from and make predictions based on data. Neural networks, "  # noqa: E501
            "inspired by biological neural systems, have become particularly effective at pattern "  # noqa: E501
            "recognition tasks. Deep learning, which uses multi-layered neural networks, has "  # noqa: E501
            "revolutionized fields such as computer vision and natural language processing. "  # noqa: E501
            "Supervised learning algorithms require labeled training data to learn the relationship "  # noqa: E501
            "between inputs and outputs. Common techniques include linear regression for continuous "  # noqa: E501
            "predictions, logistic regression for binary classification, and decision trees for both "  # noqa: E501
            "regression and classification tasks. These models form the foundation of many practical "  # noqa: E501
            "applications in industry. Unsupervised learning algorithms discover hidden patterns in "  # noqa: E501
            "unlabeled data without explicit guidance, using techniques like clustering and "  # noqa: E501
            "dimensionality reduction."
        ),

        "expected_concepts": [
            "machine learning",
            "artificial intelligence",
            "neural networks",
            "deep learning",
            "supervised learning",
            "unsupervised learning",
            "pattern recognition",
            "computer vision",
            "natural language processing"
        ]
    },

    "biology": {
        "short": "DNA contains the genetic instructions for all living organisms.",  # noqa: E501

        "medium": (
            "DNA replication is a semi-conservative process that ensures genetic information "  # noqa: E501
            "is accurately copied before cell division. The enzyme helicase unwinds the double "  # noqa: E501
            "helix, DNA polymerase synthesizes new complementary strands, and ligase seals any "  # noqa: E501
            "gaps in the sugar-phosphate backbone. This precise mechanism maintains genomic "  # noqa: E501
            "integrity across generations."
        ),

        "long": (
            "DNA replication is a semi-conservative process that ensures genetic information "  # noqa: E501
            "is accurately copied before cell division. The enzyme helicase unwinds the double "  # noqa: E501
            "helix, DNA polymerase synthesizes new complementary strands, and ligase seals any "  # noqa: E501
            "gaps in the sugar-phosphate backbone. Cellular respiration converts glucose and "  # noqa: E501
            "oxygen into energy in the form of ATP through three main stages: glycolysis, the "  # noqa: E501
            "Krebs cycle, and the electron transport chain. Photosynthesis converts light energy "  # noqa: E501
            "into chemical energy stored in glucose molecules through light-dependent and "  # noqa: E501
            "light-independent reactions. The immune system provides defense against pathogens "  # noqa: E501
            "through innate and adaptive responses involving T cells and B cells."  # noqa: E501
        ),

        "expected_concepts": [
            "DNA replication",
            "cell division",
            "helicase",
            "DNA polymerase",
            "ligase",
            "cellular respiration",
            "ATP",
            "photosynthesis",
            "immune system"
        ]
    },

    "technology": {
        "short": "Cloud computing delivers on-demand computing resources over the internet.",  # noqa: E501

        "medium": (
            "Cloud computing delivers computing services over the internet, enabling organizations "  # noqa: E501
            "to access scalable resources without maintaining physical infrastructure. The three "  # noqa: E501
            "main service models are Infrastructure as a Service (IaaS), Platform as a Service "  # noqa: E501
            "(PaaS), and Software as a Service (SaaS). Major cloud providers like AWS, Azure, "  # noqa: E501
            "and Google Cloud offer comprehensive ecosystems of tools and services."  # noqa: E501
        ),

        "long": (
            "Cloud computing delivers computing services over the internet, enabling organizations "  # noqa: E501
            "to access scalable resources without maintaining physical infrastructure. Blockchain "  # noqa: E501
            "technology creates immutable, distributed ledgers that record transactions across a "  # noqa: E501
            "network of computers. The Internet of Things connects physical devices with sensors "  # noqa: E501
            "and software to collect and exchange data. Quantum computing leverages quantum "  # noqa: E501
            "mechanical phenomena like superposition and entanglement to perform calculations "  # noqa: E501
            "exponentially faster than classical computers. Edge computing processes data closer "  # noqa: E501
            "to where it is generated rather than sending it to centralized cloud servers, "  # noqa: E501
            "reducing latency and enabling real-time processing."
        ),

        "expected_concepts": [
            "cloud computing",
            "IaaS",
            "PaaS",
            "SaaS",
            "blockchain",
            "Internet of Things",
            "IoT",
            "quantum computing",
            "edge computing"
        ]
    },

    "finance": {
        "short": "Compound interest earns returns on both principal and accumulated interest.",  # noqa: E501

        "medium": (
            "Portfolio diversification reduces risk by spreading investments across different "  # noqa: E501
            "asset classes, industries, and geographic regions. Modern portfolio theory suggests "  # noqa: E501
            "that investors can optimize returns for a given level of risk through strategic "  # noqa: E501
            "asset allocation. Index funds offer low-cost exposure to broad market segments and "  # noqa: E501
            "have historically outperformed actively managed funds over long time periods."  # noqa: E501
        ),

        "expected_concepts": [
            "portfolio diversification",
            "asset allocation",
            "modern portfolio theory",
            "index funds",
            "risk management",
            "compound interest"
        ]
    },

    "healthcare": {
        "short": "Preventive medicine focuses on disease prevention rather than treatment.",  # noqa: E501

        "medium": (
            "Electronic health records have transformed healthcare delivery by enabling seamless "  # noqa: E501
            "information sharing among providers, reducing medical errors, and improving patient "  # noqa: E501
            "outcomes. Telemedicine expands access to healthcare services, particularly in rural "  # noqa: E501
            "areas, by enabling remote consultations through video conferencing and digital "  # noqa: E501
            "communication platforms. Precision medicine uses genetic information and biomarkers "  # noqa: E501
            "to tailor treatments to individual patients."
        ),

        "expected_concepts": [
            "electronic health records",
            "telemedicine",
            "precision medicine",
            "preventive medicine",
            "biomarkers",
            "patient outcomes"
        ]
    }
}


# Test knowledge graph terms for seeding test databases
TEST_KG_TERMS = [
    # AI/ML Domain
    ("Machine Learning", "Algorithms that learn from data without explicit programming", "ai_ml"),  # noqa: E501
    ("Artificial Intelligence", "Simulation of human intelligence by machines", "ai_ml"),  # noqa: E501
    ("Neural Networks", "Computing systems inspired by biological neural networks", "ai_ml"),  # noqa: E501
    ("Deep Learning", "Multi-layered neural networks for complex pattern recognition", "ai_ml"),  # noqa: E501
    ("Natural Language Processing", "AI for understanding and generating human language", "ai_ml"),  # noqa: E501
    ("Computer Vision", "AI for analyzing and understanding visual information", "ai_ml"),  # noqa: E501
    ("Supervised Learning", "Learning from labeled training data", "ai_ml"),
    ("Unsupervised Learning", "Finding patterns in unlabeled data", "ai_ml"),
    ("Reinforcement Learning", "Learning through trial and error with rewards", "ai_ml"),  # noqa: E501

    # Biology Domain
    ("DNA Replication", "Process of copying genetic information", "biology"),
    ("Cell Division", "Process by which cells reproduce", "biology"),
    ("Cellular Respiration", "Converting glucose to ATP energy", "biology"),
    ("Photosynthesis", "Converting light energy to chemical energy", "biology"),  # noqa: E501
    ("Protein Synthesis", "Creating proteins from genetic code", "biology"),
    ("Immune System", "Defense mechanism against pathogens", "biology"),
    ("Enzyme", "Biological catalyst that speeds up reactions", "biology"),
    ("ATP", "Adenosine triphosphate, primary energy currency of cells", "biology"),  # noqa: E501

    # Technology Domain
    ("Cloud Computing", "Computing services delivered over the internet", "technology"),  # noqa: E501
    ("Blockchain", "Distributed ledger technology", "technology"),
    ("Internet of Things", "Network of connected physical devices", "technology"),  # noqa: E501
    ("Quantum Computing", "Computing using quantum mechanical phenomena", "technology"),  # noqa: E501
    ("Edge Computing", "Processing data closer to its source", "technology"),
    ("IaaS", "Infrastructure as a Service cloud model", "technology"),
    ("PaaS", "Platform as a Service cloud model", "technology"),
    ("SaaS", "Software as a Service cloud model", "technology"),

    # Finance Domain
    ("Portfolio Diversification", "Spreading investments to reduce risk", "finance"),  # noqa: E501
    ("Asset Allocation", "Distributing investments among different asset classes", "finance"),  # noqa: E501
    ("Compound Interest", "Interest calculated on principal and accumulated interest", "finance"),  # noqa: E501
    ("Index Fund", "Investment fund tracking a market index", "finance"),
    ("Modern Portfolio Theory", "Framework for optimizing investment returns", "finance"),  # noqa: E501

    # Healthcare Domain
    ("Electronic Health Records", "Digital patient health information", "healthcare"),  # noqa: E501
    ("Telemedicine", "Remote healthcare delivery via technology", "healthcare"),  # noqa: E501
    ("Precision Medicine", "Tailoring treatment to individual patients", "healthcare"),  # noqa: E501
    ("Preventive Medicine", "Focus on disease prevention", "healthcare"),
    ("Biomarker", "Measurable indicator of biological state or condition", "healthcare"),  # noqa: E501
]


# Expected entity counts by input size (for validation)
EXPECTED_ENTITY_RANGES = {
    "short": {"min": 1, "max": 5},
    "medium": {"min": 3, "max": 15},
    "long": {"min": 5, "max": 30},
}


# Test cases for edge cases and special inputs
EDGE_CASE_INPUTS = {
    "empty": "",
    "whitespace_only": "   \n\t  ",
    "single_word": "Technology",
    "special_characters": "Test with special chars: @#$%^&*()",
    "unicode": "Test with unicode: \u2022 \u2026 \u00A9 中文",
    "emoji": "Test with emoji 🔥 💡 🚀",
    "very_long_word": "pneumonoultramicroscopicsilicovolcanoconiosis",
    "numbers_only": "12345 67890",
    "mixed_languages": "English and עברית and 中文",
    "rtl_text": "This is RTL text: العربية",
    "newlines": "First line.\n\nSecond line.\n\n\nThird line.",
    "tabs": "Column1\tColumn2\tColumn3",
}


# Mock processor outputs for unit testing
def get_mock_kg_context_output(num_phrases=2, num_nodes=3):
    """Generate mock KG context output for testing."""
    from rag.processors.models import KGContextOutput, ExtractedPhrase, KGNode

    return KGContextOutput(
        extracted_phrases=[
            ExtractedPhrase(
                text=f"phrase_{i}",
                sentence_index=0,
                start_char=i * 10,
                end_char=(i * 10) + 8
            ) for i in range(num_phrases)
        ],
        kg_nodes=[
            KGNode(
                node_id=f"node_{i}",
                title=f"Concept {i}",
                node_type="term",
                similarity_score=0.9 - (i * 0.1),
                definition=f"Definition for concept {i}"
            ) for i in range(num_nodes)
        ],
        total_sentences=1,
        trace_data={}
    )


def get_mock_llm_extraction_output(num_entities=2):
    """Generate mock LLM extraction output for testing."""
    from rag.processors.models import LLMExtractionOutput, ExtractedEntity

    return LLMExtractionOutput(
        entities=[
            ExtractedEntity(
                text=f"entity_{i}",
                entity_type="CONCEPT",
                confidence=0.95 - (i * 0.05),
                sentence_indices=[0],
                matched_kg_node=f"node_{i}" if i < 2 else None,
                start_char=i * 15,
                end_char=(i * 15) + 8
            ) for i in range(num_entities)
        ],
        kg_context_size=3,
        token_usage={"prompt_tokens": 100, "completion_tokens": 50},
        trace_data={}
    )


def get_mock_spacy_gap_output(num_gaps=1):
    """Generate mock spaCy gap output for testing."""
    from rag.processors.models import SpaCyGapOutput, GapConcept, GapPriority

    return SpaCyGapOutput(
        gaps=[
            GapConcept(
                text=f"gap_{i}",
                sentence_index=0,
                priority=GapPriority.IMPORTANT if i % 2 == 0 else GapPriority.CONTEXTUAL,  # noqa: E501
                dep_role="nsubj" if i % 2 == 0 else "amod",
                head_word="verb",
                connected_verb="verb",
                start_char=i * 20,
                end_char=(i * 20) + 5,
                tf_idf_score=0.3 + (i * 0.1)
            ) for i in range(num_gaps)
        ],
        total_noun_phrases=num_gaps + 5,
        filtered_count=2,
        trace_data={}
    )


def get_mock_concept_resolution_output(num_resolved=1):
    """Generate mock concept resolution output for testing."""
    from rag.processors.models import (
        ConceptResolutionOutput,
        ResolvedConcept,
        GapConcept,
        GapPriority,
        ResolutionMethod,
        KGNode
    )

    gaps = [
        GapConcept(
            text=f"gap_{i}",
            sentence_index=0,
            priority=GapPriority.IMPORTANT,
            dep_role="nsubj",
            head_word="verb",
            connected_verb="verb",
            start_char=i * 20,
            end_char=(i * 20) + 5,
            tf_idf_score=0.3
        ) for i in range(num_resolved)
    ]

    return ConceptResolutionOutput(
        resolved_concepts=[
            ResolvedConcept(
                original_gap=gap,
                resolution_method=ResolutionMethod.FULL_KG if i % 2 == 0 else ResolutionMethod.WEB_SEARCH,  # noqa: E501
                matched_kg_node=KGNode(
                    node_id=f"resolved_{i}",
                    title=f"Resolved {i}",
                    node_type="term",
                    similarity_score=0.85,
                    definition=f"Definition {i}"
                ) if i % 2 == 0 else None,
                web_definition=f"Web definition {i}" if i % 2 == 1 else None,
                confidence=0.75
            ) for i, gap in enumerate(gaps)
        ],
        unresolved_gaps=[],
        web_searches_performed=num_resolved // 2,
        cached_kg_hits=0,
        full_kg_hits=num_resolved // 2,
        trace_data={}
    )


# Performance benchmarks for validation
PERFORMANCE_BENCHMARKS = {
    "layer_0_target_ms": 500,
    "layer_0_relaxed_ms": 2000,  # For test environments
    "layer_1_target_ms": 30000,
    "layer_2_target_ms": 500,
    "layer_2_relaxed_ms": 2000,  # For test environments
    "layer_3_target_ms": 30000,
    "total_target_min_ms": 5000,   # 5s minimum for typical inputs
    "total_target_max_ms": 15000,  # 15s maximum for typical inputs
    "total_budget_max_ms": 120000,  # 120s absolute maximum
}
