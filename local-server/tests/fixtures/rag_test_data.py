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
        "short": "Machine learning algorithms learn patterns from data without explicit programming.",

        "medium": (
            "Machine learning is a subset of artificial intelligence that focuses on developing "
            "algorithms that can learn from and make predictions based on data. Neural networks, "
            "inspired by biological neural systems, have become particularly effective at pattern "
            "recognition tasks. Deep learning uses multi-layered neural networks and has "
            "revolutionized fields such as computer vision and natural language processing."
        ),

        "long": (
            "Machine learning is a subset of artificial intelligence that focuses on developing "
            "algorithms that can learn from and make predictions based on data. Neural networks, "
            "inspired by biological neural systems, have become particularly effective at pattern "
            "recognition tasks. Deep learning, which uses multi-layered neural networks, has "
            "revolutionized fields such as computer vision and natural language processing. "
            "Supervised learning algorithms require labeled training data to learn the relationship "
            "between inputs and outputs. Common techniques include linear regression for continuous "
            "predictions, logistic regression for binary classification, and decision trees for both "
            "regression and classification tasks. These models form the foundation of many practical "
            "applications in industry. Unsupervised learning algorithms discover hidden patterns in "
            "unlabeled data without explicit guidance, using techniques like clustering and "
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
        "short": "DNA contains the genetic instructions for all living organisms.",

        "medium": (
            "DNA replication is a semi-conservative process that ensures genetic information "
            "is accurately copied before cell division. The enzyme helicase unwinds the double "
            "helix, DNA polymerase synthesizes new complementary strands, and ligase seals any "
            "gaps in the sugar-phosphate backbone. This precise mechanism maintains genomic "
            "integrity across generations."
        ),

        "long": (
            "DNA replication is a semi-conservative process that ensures genetic information "
            "is accurately copied before cell division. The enzyme helicase unwinds the double "
            "helix, DNA polymerase synthesizes new complementary strands, and ligase seals any "
            "gaps in the sugar-phosphate backbone. Cellular respiration converts glucose and "
            "oxygen into energy in the form of ATP through three main stages: glycolysis, the "
            "Krebs cycle, and the electron transport chain. Photosynthesis converts light energy "
            "into chemical energy stored in glucose molecules through light-dependent and "
            "light-independent reactions. The immune system provides defense against pathogens "
            "through innate and adaptive responses involving T cells and B cells."
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
        "short": "Cloud computing delivers on-demand computing resources over the internet.",

        "medium": (
            "Cloud computing delivers computing services over the internet, enabling organizations "
            "to access scalable resources without maintaining physical infrastructure. The three "
            "main service models are Infrastructure as a Service (IaaS), Platform as a Service "
            "(PaaS), and Software as a Service (SaaS). Major cloud providers like AWS, Azure, "
            "and Google Cloud offer comprehensive ecosystems of tools and services."
        ),

        "long": (
            "Cloud computing delivers computing services over the internet, enabling organizations "
            "to access scalable resources without maintaining physical infrastructure. Blockchain "
            "technology creates immutable, distributed ledgers that record transactions across a "
            "network of computers. The Internet of Things connects physical devices with sensors "
            "and software to collect and exchange data. Quantum computing leverages quantum "
            "mechanical phenomena like superposition and entanglement to perform calculations "
            "exponentially faster than classical computers. Edge computing processes data closer "
            "to where it is generated rather than sending it to centralized cloud servers, "
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
        "short": "Compound interest earns returns on both principal and accumulated interest.",

        "medium": (
            "Portfolio diversification reduces risk by spreading investments across different "
            "asset classes, industries, and geographic regions. Modern portfolio theory suggests "
            "that investors can optimize returns for a given level of risk through strategic "
            "asset allocation. Index funds offer low-cost exposure to broad market segments and "
            "have historically outperformed actively managed funds over long time periods."
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
        "short": "Preventive medicine focuses on disease prevention rather than treatment.",

        "medium": (
            "Electronic health records have transformed healthcare delivery by enabling seamless "
            "information sharing among providers, reducing medical errors, and improving patient "
            "outcomes. Telemedicine expands access to healthcare services, particularly in rural "
            "areas, by enabling remote consultations through video conferencing and digital "
            "communication platforms. Precision medicine uses genetic information and biomarkers "
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
    ("Machine Learning", "Algorithms that learn from data without explicit programming", "ai_ml"),
    ("Artificial Intelligence", "Simulation of human intelligence by machines", "ai_ml"),
    ("Neural Networks", "Computing systems inspired by biological neural networks", "ai_ml"),
    ("Deep Learning", "Multi-layered neural networks for complex pattern recognition", "ai_ml"),
    ("Natural Language Processing", "AI for understanding and generating human language", "ai_ml"),
    ("Computer Vision", "AI for analyzing and understanding visual information", "ai_ml"),
    ("Supervised Learning", "Learning from labeled training data", "ai_ml"),
    ("Unsupervised Learning", "Finding patterns in unlabeled data", "ai_ml"),
    ("Reinforcement Learning", "Learning through trial and error with rewards", "ai_ml"),

    # Biology Domain
    ("DNA Replication", "Process of copying genetic information", "biology"),
    ("Cell Division", "Process by which cells reproduce", "biology"),
    ("Cellular Respiration", "Converting glucose to ATP energy", "biology"),
    ("Photosynthesis", "Converting light energy to chemical energy", "biology"),
    ("Protein Synthesis", "Creating proteins from genetic code", "biology"),
    ("Immune System", "Defense mechanism against pathogens", "biology"),
    ("Enzyme", "Biological catalyst that speeds up reactions", "biology"),
    ("ATP", "Adenosine triphosphate, primary energy currency of cells", "biology"),

    # Technology Domain
    ("Cloud Computing", "Computing services delivered over the internet", "technology"),
    ("Blockchain", "Distributed ledger technology", "technology"),
    ("Internet of Things", "Network of connected physical devices", "technology"),
    ("Quantum Computing", "Computing using quantum mechanical phenomena", "technology"),
    ("Edge Computing", "Processing data closer to its source", "technology"),
    ("IaaS", "Infrastructure as a Service cloud model", "technology"),
    ("PaaS", "Platform as a Service cloud model", "technology"),
    ("SaaS", "Software as a Service cloud model", "technology"),

    # Finance Domain
    ("Portfolio Diversification", "Spreading investments to reduce risk", "finance"),
    ("Asset Allocation", "Distributing investments among different asset classes", "finance"),
    ("Compound Interest", "Interest calculated on principal and accumulated interest", "finance"),
    ("Index Fund", "Investment fund tracking a market index", "finance"),
    ("Modern Portfolio Theory", "Framework for optimizing investment returns", "finance"),

    # Healthcare Domain
    ("Electronic Health Records", "Digital patient health information", "healthcare"),
    ("Telemedicine", "Remote healthcare delivery via technology", "healthcare"),
    ("Precision Medicine", "Tailoring treatment to individual patients", "healthcare"),
    ("Preventive Medicine", "Focus on disease prevention", "healthcare"),
    ("Biomarker", "Measurable indicator of biological state or condition", "healthcare"),
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
                priority=GapPriority.IMPORTANT if i % 2 == 0 else GapPriority.CONTEXTUAL,
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
                resolution_method=ResolutionMethod.FULL_KG if i % 2 == 0 else ResolutionMethod.WEB_SEARCH,
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
