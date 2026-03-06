"""
Embedding service adapters for Context Studio.

This package contains adapters that implement the EmbeddingService port
defined in domain/ontology/ports.py.

The EmbeddingService port defines two methods:
- embed_text(text: str) -> np.ndarray: Generate embedding for a text string
- similarity(embedding1, embedding2) -> float: Compute cosine similarity

Adapter implementations may use:
- Local sentence transformers (sentence-transformers library)
- OpenAI API (gpt-3.5-turbo embeddings)
- LLaMA embeddings (if running local LLM)

Per rearchitecture/architecture_design.md §5.3, the current embeddings/
directory contains the implementation. This adapter layer wraps that
implementation to conform to the domain port contract.
"""
