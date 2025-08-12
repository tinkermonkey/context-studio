import spacy
nlp = spacy.blank('en')
nlp.add_pipe('dbpedia_spotlight')

doc = nlp('Google LLC is an American multinational technology company.')
print([(ent.text, ent.kb_id_, ent._.dbpedia_raw_result['@similarityScore']) for ent in doc.ents])