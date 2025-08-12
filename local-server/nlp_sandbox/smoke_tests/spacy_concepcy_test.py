#!/usr/bin/env python3
"""
Simple test to verify concepCy can be imported and used
"""

import spacy
import concepcy

def main():
    print("✅ concepCy imported successfully!")
    
    # Create a new spaCy pipeline
    nlp = spacy.load("en_core_web_sm")
    
    nlp.add_pipe("concepcy")

    doc = nlp("WHO is a lovely company")

    # Access all the "RelatedTo" relations from the Doc
    print("--- All the 'RelatedTo' relations from the Doc ---")
    for word, relations in doc._.relatedto.items():
        print(f"Word: '{word}'\n{relations}")

    # Access the "RelatedTo" relations word by word
    print("--- The 'RelatedTo' relations word by word ---")
    for token in doc:
        print(f"Word: '{token}'\n{token._.relatedto}\n")

if __name__ == "__main__":
    main()
