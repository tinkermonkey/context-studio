# mypy: ignore-errors
from nltk.corpus import wordnet

synsets = wordnet.synsets("truck")

for synset in synsets:
    print(f"Synset: {synset.name()}")
    print(f"POS: {synset.pos()}")
    print(f"Lexical File: {synset.lexname()}")
    print(f"ID: {synset.offset()}")
    print(f"Hypernyms: {', '.join(h.name() for h in synset.hypernyms())}")
    print(f"Hyponyms: {', '.join(h.name() for h in synset.hyponyms())}")
    print(f"Meronyms: {', '.join(m.name() for m in synset.part_meronyms())}")
    print(f"Holonyms: {', '.join(h.name() for h in synset.part_holonyms())}")
    print(f"Definition: {synset.definition()}")
    print(f"Lemmas: {', '.join(synset.lemma_names())}")
    print(f"Examples: {', '.join(synset.examples())}")
    print("-" * 40)
