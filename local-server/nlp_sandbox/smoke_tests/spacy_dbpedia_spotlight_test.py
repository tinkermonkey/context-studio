import spacy

nlp = spacy.blank('en')
nlp.add_pipe('dbpedia_spotlight')

doc = nlp('A sentence about apple sauce.')
print([(ent.text, ent.kb_id_, ent._.dbpedia_raw_result['@similarityScore']) for ent in doc.ents])

print("Spans: ", doc.spans['dbpedia_spotlight'])

