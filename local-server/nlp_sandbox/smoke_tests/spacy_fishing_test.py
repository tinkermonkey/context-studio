import spacy

text_en = "Victor Hugo and Honoré de Balzac are French writers who lived in Paris."
#text_en = "Truck"

nlp_model_en = spacy.load("en_core_web_sm")

config = {
    "extra_info": False,
    "api_ef_base": "http://nerd.huma-num.fr/nerd/service",
}

nlp_model_en.add_pipe("entityfishing", config=config)

doc_en = nlp_model_en(text_en)

for ent in doc_en.ents:
  print((ent.text, ent.label_, ent._.kb_qid, ent._.url_wikidata, ent._.nerd_score))