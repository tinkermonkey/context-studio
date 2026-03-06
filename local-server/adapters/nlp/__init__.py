"""
NLP service adapters for Context Studio.

This package contains adapters that implement the NLPProcessor port
defined in domain/extraction/ports.py.

The NLPProcessor port defines:
- extract_entities(text: str) -> NLPResult: Extract entities and relations from text
- tokenize(text: str) -> Sequence[str]: Tokenize text
- pos_tag(tokens: Sequence[str]) -> Sequence[tuple[str, str]]: Part-of-speech tagging
- dependency_parse(text: str) -> Sequence[tuple[int, int, str]]: Dependency parsing

Adapter implementations may use:
- spaCy (most common, supports 20+ languages)
- NLTK (legacy, still useful for some POS tasks)
- Stanford CoreNLP (via py-corenlp)
- Hugging Face transformers (fine-tuned NER/RE models)

Per rearchitecture/architecture_design.md §5.5, the current nlp/ directory
contains the spaCy wrapper. This adapter layer wraps that implementation
to conform to the domain port contract.

NLPResult includes:
- entities: Sequence[NLPEntity] (type, text, start, end, confidence)
- relations: Sequence[tuple[NLPEntity, NLPEntity, str]] (subject, object, predicate)
- tokens: Sequence[str]
- pos_tags: Sequence[tuple[str, str]]
"""
