#!/usr/bin/env python3
"""
Simple test to verify concepCy can be imported and used
"""

import spacy

def main():
    print("✅ concepCy imported successfully!")
    
    # Create a new spaCy pipeline
    nlp = spacy.load("en_core_web_sm")
    
    predicates = [
        "RelatedTo",
        "FormOf",
        "IsA",
        "PartOf",
        "HasA",
        "UsedFor",
        "CapableOf",
        "AtLocation",
        "Causes",
        "HasSubevent",
        "HasFirstSubevent",
        "HasLastSubevent",
        "HasPrerequisite",
        "HasProperty",
        "MotivatedByGoal",
        "ObstructedBy",
        "Desires",
        "CreatedBy",
        "Synonym",
        "Antonym",
        "DistinctFrom",
        "DerivedFrom",
        "SymbolOf",
        "DefinedAs",
        "MannerOf",
        "LocatedNear",
        "HasContext",
        "SimilarTo",
        "EtymologicallyRelatedTo",
        "EtymologicallyDerivedFrom",
        "CausesDesire",
        "MadeOf",
        "ReceivesAction",
        "ExternalURL"
    ]

    nlp.add_pipe("concepcy",
                 config={
        "relations_of_interest": predicates,
        "filter_missing_text": True,
        "filter_edge_weight": 2,
    })

    doc = nlp("email")

    # Access all the "RelatedTo" relations from the Doc
    if False:
        print("--- All the 'RelatedTo' relations from the Doc ---")
        for word, relations in doc._.relatedto.items():
            print(f"Word: '{word}'\n{relations}")

    # Access the "RelatedTo" relations word by word
    if False:
        print("--- The 'RelatedTo' relations word by word ---")
        for token in doc:
            print(f"Word: '{token}'\n{token._.relatedto}\n")

    # See what other relations are available under doc._
    print("--- Other relations available ---")
    for attr in dir(doc._):
        if not attr.startswith("_"):
            print(f" - {attr}")
            print(getattr(doc._, attr))

    # dbpedia_raw_result
    if hasattr(doc._, 'dbpedia_raw_result') and doc._.dbpedia_raw_result:
        print(f"DBpedia raw result: {doc._.dbpedia_raw_result}")
    
    # instanceof
    if hasattr(doc._, 'instanceof') and doc._.instanceof:
        print(f"Instanceof: {doc._.instanceof}")

if __name__ == "__main__":
    main()
