import os
import spacy
from sense2vec import Sense2VecComponent

nlp = spacy.load("en_core_web_sm")
s2v = nlp.add_pipe("sense2vec")

local_path = "../../downloads/s2v_reddit_2015_md"
abs_path = os.path.abspath(local_path)
if os.path.exists(abs_path):
    print(f"Loading sense2vec model from {abs_path}...")
    s2v.from_disk(abs_path)
else:
    print(f"Downloading sense2vec model to {abs_path}...")
    #s2v.to_disk(abs_path)
    raise FileNotFoundError(f"Sense2vec model not found at {abs_path}. Please download it first.")

doc = nlp("A sentence about apple sauce.")

print("Tokens and their sense2vec data:", doc._.s2v_phrases)
for token in doc:
    if token._.s2v_freq is not None:
        print(f"==\nToken: {token.text}\nFreq: {token._.s2v_freq}\nKey: {token._.s2v_key}\nOther senses: {token._.s2v_other_senses}\n==")

similar_list = []
most_similar = []
if len(most_similar) > 0:
  for similar in most_similar:
      print(f"Similar: {similar[0][0]} ({similar[0][1]}) - Score: {similar[1]}")
      similar_list.append({"word": similar[0][0], "sense": similar[0][1], "score": similar[1]})


print("Sense2Vec model loaded and tested successfully.", similar_list)