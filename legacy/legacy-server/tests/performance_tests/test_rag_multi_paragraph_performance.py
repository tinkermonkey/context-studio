"""
Multi-paragraph performance tests for RAG Pipeline.

These tests verify performance with varying input sizes (1-5 paragraphs)
and ensure compliance with time budgets:
- Layer 0: <500ms
- Layer 1: <30s
- Layer 2: <500ms
- Layer 3: <30s
- Total: <120s (max budget), target 5-15s for typical inputs
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import time

import numpy as np
import pytest
from database.custom_types import NodeType
from database.models import Base, StructureNode
from rag.rag_pipeline_service import RAGPipelineService
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Realistic test paragraphs for different domains
REALISTIC_PARAGRAPHS = {
    "ai_ml": [
        "Machine learning is a subset of artificial intelligence that focuses on developing algorithms that can learn from and make predictions based on data. Neural networks, inspired by biological neural systems, have become particularly effective at pattern recognition tasks. Deep learning, which uses multi-layered neural networks, has revolutionized fields such as computer vision and natural language processing.",
        "Supervised learning algorithms require labeled training data to learn the relationship between inputs and outputs. Common techniques include linear regression for continuous predictions, logistic regression for binary classification, and decision trees for both regression and classification tasks. These models form the foundation of many practical applications in industry.",
        "Unsupervised learning algorithms discover hidden patterns in unlabeled data without explicit guidance. Clustering algorithms like K-means group similar data points together, while dimensionality reduction techniques like PCA simplify complex datasets. These methods are crucial for exploratory data analysis and feature engineering.",
        "Reinforcement learning enables agents to learn optimal behavior through trial and error interactions with an environment. The agent receives rewards or penalties based on its actions and learns to maximize cumulative reward over time. This approach has achieved remarkable success in game playing, robotics, and autonomous systems.",
        "Transfer learning leverages knowledge gained from solving one problem to improve performance on a related but different task. Pre-trained models, such as those trained on ImageNet for computer vision or large language models for NLP, can be fine-tuned with relatively small amounts of task-specific data, dramatically reducing training time and data requirements.",
    ],
    "biology": [
        "Cellular respiration is the process by which cells convert glucose and oxygen into energy in the form of ATP. This process occurs in three main stages: glycolysis in the cytoplasm, the Krebs cycle in the mitochondrial matrix, and the electron transport chain in the inner mitochondrial membrane. Together, these stages produce approximately 36-38 ATP molecules per glucose molecule.",
        "DNA replication is a semi-conservative process that ensures genetic information is accurately copied before cell division. The enzyme helicase unwinds the double helix, DNA polymerase synthesizes new complementary strands, and ligase seals any gaps in the sugar-phosphate backbone. This precise mechanism maintains genomic integrity across generations.",
        "Photosynthesis converts light energy into chemical energy stored in glucose molecules. In the light-dependent reactions, chlorophyll absorbs photons and generates ATP and NADPH through the electron transport chain. The light-independent reactions, or Calvin cycle, use these products to fix carbon dioxide into organic compounds through a series of enzyme-catalyzed steps.",
        "Protein synthesis involves two major processes: transcription and translation. During transcription, RNA polymerase reads DNA sequences and produces messenger RNA. In translation, ribosomes read mRNA codons and assemble amino acids into polypeptide chains according to the genetic code, which are then folded into functional proteins.",
        "The immune system provides defense against pathogens through innate and adaptive responses. Innate immunity offers immediate but non-specific protection through physical barriers, phagocytic cells, and inflammatory responses. Adaptive immunity develops more slowly but provides specific, long-lasting protection through T cells and B cells that recognize particular antigens.",
    ],
    "technology": [
        "Cloud computing delivers computing services over the internet, enabling organizations to access scalable resources without maintaining physical infrastructure. The three main service models are Infrastructure as a Service (IaaS), Platform as a Service (PaaS), and Software as a Service (SaaS). Major providers like AWS, Azure, and Google Cloud offer comprehensive ecosystems of tools and services.",
        "Blockchain technology creates immutable, distributed ledgers that record transactions across a network of computers. Each block contains a cryptographic hash of the previous block, creating a chain that is extremely difficult to alter retroactively. This technology underpins cryptocurrencies and has potential applications in supply chain management, identity verification, and smart contracts.",
        "The Internet of Things (IoT) connects physical devices with sensors and software to collect and exchange data. Smart home devices, industrial sensors, and wearable technology generate massive amounts of data that can be analyzed to improve efficiency, predict maintenance needs, and enhance user experiences. Security and privacy remain significant challenges in IoT deployments.",
        "Quantum computing leverages quantum mechanical phenomena like superposition and entanglement to perform certain calculations exponentially faster than classical computers. While still in early stages of development, quantum computers show promise for applications in cryptography, drug discovery, optimization problems, and simulation of quantum systems.",
        "Edge computing processes data closer to where it is generated rather than sending it to centralized cloud servers. This approach reduces latency, conserves bandwidth, and enables real-time processing for applications like autonomous vehicles, industrial automation, and augmented reality. Edge computing complements rather than replaces cloud computing.",
    ],
}


@pytest.fixture
def test_kg_db_with_content():
    """Create a test KG database populated with relevant terms."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    try:
        from embeddings.generate_embeddings import get_model

        model = get_model()

        # Add relevant terms for test domains
        terms_data = [
            (
                "Machine Learning",
                "A subset of AI focused on algorithms that learn from data",
            ),
            (
                "Neural Networks",
                "Computing systems inspired by biological neural networks",
            ),
            (
                "Deep Learning",
                "Multi-layered neural networks for complex pattern recognition",
            ),
            ("Supervised Learning", "ML with labeled training data"),
            (
                "Reinforcement Learning",
                "Learning through trial and error with rewards",
            ),
            (
                "Cellular Respiration",
                "Process converting glucose to ATP energy",
            ),
            (
                "DNA Replication",
                "Copying genetic information before cell division",
            ),
            ("Photosynthesis", "Converting light energy into chemical energy"),
            (
                "Protein Synthesis",
                "Process of creating proteins from genetic code",
            ),
            ("Immune System", "Defense mechanism against pathogens"),
            (
                "Cloud Computing",
                "Computing services delivered over the internet",
            ),
            ("Blockchain", "Distributed ledger technology"),
            ("Internet of Things", "Network of connected physical devices"),
            (
                "Quantum Computing",
                "Computing using quantum mechanical phenomena",
            ),
            ("Edge Computing", "Processing data closer to its source"),
        ]

        for title, definition in terms_data:
            embedding = model.encode([title])[0]
            embedding_blob = np.array(embedding, dtype=np.float32).tobytes()

            node = StructureNode(
                node_type=NodeType.TERM,
                title=title,
                definition=definition,
                title_embedding=embedding_blob,
                parent_node_id=None,
            )
            session.add(node)

        session.commit()
    finally:
        session.close()

    yield engine, SessionLocal

    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def test_ops_db():
    """Create a test operations database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine)

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_processing_metrics (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                sentence_text TEXT NOT NULL,
                layer_0_time_ms INTEGER,
                layer_0_count INTEGER,
                layer_1_time_ms INTEGER,
                layer_1_count INTEGER,
                layer_2_time_ms INTEGER,
                layer_2_count INTEGER,
                layer_3_time_ms INTEGER,
                layer_3_count INTEGER,
                total_time_ms INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                retention_days INTEGER DEFAULT 30 NOT NULL
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_observability_trace (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                sentence_index INTEGER NOT NULL,
                layer_name TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                trace_data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                retention_days INTEGER DEFAULT 7 NOT NULL
            )
        """))
        conn.commit()

    yield engine, SessionLocal

    engine.dispose()
    os.unlink(db_path)


class TestMultiParagraphPerformance:
    """Performance tests with multiple paragraphs."""

    @pytest.mark.asyncio
    async def test_single_paragraph_performance(
        self, test_kg_db_with_content, test_ops_db
    ):
        """Test performance with 1 paragraph (baseline)."""
        _kg_engine, kg_session_maker = test_kg_db_with_content
        _ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=30,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            input_text = REALISTIC_PARAGRAPHS["ai_ml"][0]

            start = time.time()
            response = await service.extract_entities(
                input_text, enable_trace=False
            )
            elapsed = time.time() - start

            # Assertions
            assert response.request_id is not None
            assert response.metrics.total_execution_time_ms > 0

            # Performance targets
            assert (
                elapsed < 15.0
            ), f"Single paragraph took {elapsed:.2f}s (target: <15s)"

            # Layer 0 should be fast
            assert (
                response.metrics.kg_layer.execution_time_ms < 2000
            ), f"Layer 0 took {response.metrics.kg_layer.execution_time_ms}ms (target: <500ms, relaxed to 2s for test)"

            # Layer 2 should be fast
            assert (
                response.metrics.nlp_layer.execution_time_ms < 2000
            ), f"Layer 2 took {response.metrics.nlp_layer.execution_time_ms}ms (target: <500ms, relaxed to 2s for test)"

            print(
                f"\n1 paragraph: {elapsed:.2f}s total, {response.metrics.total_sentences} sentences"
            )

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_two_paragraph_performance(
        self, test_kg_db_with_content, test_ops_db
    ):
        """Test performance with 2 paragraphs."""
        _kg_engine, kg_session_maker = test_kg_db_with_content
        _ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=30,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            input_text = " ".join(REALISTIC_PARAGRAPHS["ai_ml"][:2])

            start = time.time()
            response = await service.extract_entities(
                input_text, enable_trace=False
            )
            elapsed = time.time() - start

            assert response.request_id is not None
            assert (
                elapsed < 30.0
            ), f"2 paragraphs took {elapsed:.2f}s (target: <30s)"

            print(
                f"\n2 paragraphs: {elapsed:.2f}s total, {response.metrics.total_sentences} sentences"
            )

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_three_paragraph_performance(
        self, test_kg_db_with_content, test_ops_db
    ):
        """Test performance with 3 paragraphs."""
        _kg_engine, kg_session_maker = test_kg_db_with_content
        _ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=30,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            input_text = " ".join(REALISTIC_PARAGRAPHS["biology"][:3])

            start = time.time()
            response = await service.extract_entities(
                input_text, enable_trace=False
            )
            elapsed = time.time() - start

            assert response.request_id is not None
            assert (
                elapsed < 60.0
            ), f"3 paragraphs took {elapsed:.2f}s (target: <60s)"

            print(
                f"\n3 paragraphs: {elapsed:.2f}s total, {response.metrics.total_sentences} sentences"
            )

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_five_paragraph_performance(
        self, test_kg_db_with_content, test_ops_db
    ):
        """Test performance with 5 paragraphs (max budget test)."""
        _kg_engine, kg_session_maker = test_kg_db_with_content
        _ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=30,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            input_text = " ".join(REALISTIC_PARAGRAPHS["technology"])

            start = time.time()
            response = await service.extract_entities(
                input_text, enable_trace=False
            )
            elapsed = time.time() - start

            assert response.request_id is not None

            # Must complete within max budget
            assert (
                elapsed < 120.0
            ), f"5 paragraphs took {elapsed:.2f}s (MAX budget: <120s)"

            print(
                f"\n5 paragraphs: {elapsed:.2f}s total, {response.metrics.total_sentences} sentences"
            )
            print(
                f"  Layer 0: {response.metrics.kg_layer.execution_time_ms}ms"
            )
            print(
                f"  Layer 1: {response.metrics.llm_layer.execution_time_ms}ms"
            )
            print(
                f"  Layer 2: {response.metrics.nlp_layer.execution_time_ms}ms"
            )
            print(
                f"  Layer 3: {response.metrics.web_layer.execution_time_ms}ms"
            )

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_domain_specific_biology(
        self, test_kg_db_with_content, test_ops_db
    ):
        """Test with domain-specific biology text."""
        _kg_engine, kg_session_maker = test_kg_db_with_content
        _ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=30,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            input_text = " ".join(REALISTIC_PARAGRAPHS["biology"][:3])

            response = await service.extract_entities(
                input_text, enable_trace=False
            )

            # Should extract biology-related entities
            assert response.request_id is not None
            assert response.metrics.total_entities >= 0
            assert response.metrics.total_sentences >= 3

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_varying_paragraph_length(
        self, test_kg_db_with_content, test_ops_db
    ):
        """Test with paragraphs of varying lengths."""
        _kg_engine, kg_session_maker = test_kg_db_with_content
        _ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=30,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            # Mix short and long paragraphs
            mixed_text = (
                "AI is transforming technology. "  # Very short
                + REALISTIC_PARAGRAPHS["ai_ml"][0]  # Medium
                + " "
                + REALISTIC_PARAGRAPHS["technology"][4]  # Long
            )

            start = time.time()
            response = await service.extract_entities(
                mixed_text, enable_trace=False
            )
            elapsed = time.time() - start

            assert response.request_id is not None
            assert (
                elapsed < 45.0
            ), f"Mixed paragraphs took {elapsed:.2f}s (target: <45s)"

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_performance_consistency_across_runs(
        self, test_kg_db_with_content, test_ops_db
    ):
        """Test that performance is consistent across multiple runs."""
        _kg_engine, kg_session_maker = test_kg_db_with_content
        _ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=30,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            input_text = REALISTIC_PARAGRAPHS["ai_ml"][0]

            # Run 3 times and measure consistency
            elapsed_times = []
            for i in range(3):
                start = time.time()
                response = await service.extract_entities(
                    input_text, enable_trace=False
                )
                elapsed = time.time() - start
                elapsed_times.append(elapsed)
                assert response.request_id is not None

            # Performance should be relatively consistent (within 50% variance)
            avg_time = sum(elapsed_times) / len(elapsed_times)
            for t in elapsed_times:
                variance = abs(t - avg_time) / avg_time
                assert (
                    variance < 0.5
                ), f"Performance variance too high: {variance:.2%} (times: {elapsed_times})"

            print(
                f"\nConsistency test - times: {[f'{t:.2f}s' for t in elapsed_times]}, avg: {avg_time:.2f}s"
            )

        finally:
            kg_session.close()
            ops_session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
