# https://github.com/argilla-io/spacy-wordnet
# python -m nltk.downloader wordnet
# python -m nltk.downloader omw

import spacy


# Load an spacy model
nlp = spacy.load('en_core_web_sm')
# Spacy 3.x
nlp.add_pipe("spacy_wordnet", after='tagger')
# Spacy 2.x
# nlp.add_pipe(WordnetAnnotator(nlp, name="spacy_wordnet"), after='tagger')
token = nlp('prices')[0]

# wordnet object link spacy token with nltk wordnet interface by giving acces to
# synsets and lemmas 
print(f"Synsets: {token._.wordnet.synsets()}")
print(f"Lemmas: {token._.wordnet.lemmas()}")

# And automatically tags with wordnet domains
print(f"Domains: {token._.wordnet.wordnet_domains()}")

economy_domains = ['finance', 'banking']
enriched_sentence = []
sentence = nlp('I want to withdraw 5,000 euros')

# For each token in the sentence
for token in sentence:
    # We get those synsets within the desired domains
    synsets = token._.wordnet.wordnet_synsets_for_domain(economy_domains)
    if not synsets:
        enriched_sentence.append(token.text)
    else:
        lemmas_for_synset = [lemma for s in synsets for lemma in s.lemma_names()]
        # If we found a synset in the economy domains
        # we get the variants and add them to the enriched sentence
        enriched_sentence.append('({})'.format('|'.join(set(lemmas_for_synset))))

# Let's see our enriched sentence
print(' '.join(enriched_sentence))
# >> I (need|want|require) to (draw|withdraw|draw_off|take_out) 5,000 euros