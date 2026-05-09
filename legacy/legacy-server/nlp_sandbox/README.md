# Context Studio NLP Playground

This folder contains various POCs and notebooks for figuring out aspects of the NLP pipeline.

## Context Sources

A primary use case for the NLP pipeline is to bring various open sources into the Layer / Domain / Term definition workflow to both accelerate it but also to ground the definitions in commonly accepted usages.

Sources found so far that fit the bill and can be integrated through spaCy are:

- ConceptNet

  - spaCy integration: [concepCy](https://github.com/JulesBelveze/concepcy)

  - smoke test: `nlp_sandbox/smoke_tests/concepcy_test.py`

- DbPedia

  - spaCy integration: [DBpedia Spotlight](https://github.com/MartinoMensio/spacy-dbpedia-spotlight)

  - smoke test: `nlp_sandbox/smoke_tests/dbpedia_spotlight_test.py`

- Wiktionary

 - 

- PyDictionary

  - 

- Wikidata

- 

- Wordnet

  - spaCy integration: [spaCy wordnet](https://github.com/argilla-io/spacy-wordnet)

  - smoke test: `nlp_sandbox/smoke_tests/spacy_wordnet_test.py`
