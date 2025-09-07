import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from nlp.pipeline import get_pipeline
from nlp.processors import extract_token_data

@pytest.fixture(scope="module")
def nlp():
    pipeline = get_pipeline().get_nlp()
    assert pipeline is not None, "NLP pipeline is not initialized."
    return pipeline

def test_spacy_token_extraction(nlp):
    doc = nlp("Apple is a company based in Cupertino.")
    tokens = extract_token_data(doc)
    assert len(tokens) == len(doc)
    for token, spacy_token in zip(tokens, doc):
        assert token.text == spacy_token.text
        assert token.lemma is not None
        assert token.pos is not None

def test_concepcy_extraction(nlp):
    doc = nlp("Apple is a fruit.")
    tokens = extract_token_data(doc)
    # Currently concepcy component is not populating token attributes,
    # so we expect concepcy to be None for all tokens
    for token in tokens:
        assert token.concepcy is None, f"Expected no concepcy data for '{token.text}', but found: {token.concepcy}"

def test_wordnet_extraction(nlp):
    doc = nlp("Apple is a fruit.")
    tokens = extract_token_data(doc)
    found = False
    for token in tokens:
        if token.wordnet and token.wordnet.synsets:
            found = True
            assert isinstance(token.wordnet.synsets, list)
            assert isinstance(token.wordnet.lemmas, list)
            assert isinstance(token.wordnet.definitions, list)
            break
    assert found, "No wordnet synsets extracted."

def test_spacy_specific_token_data(nlp):
    doc = nlp("Apple is a company based in Cupertino.")
    tokens = extract_token_data(doc)
    # Find the token for 'Apple'
    apple_token = next((t for t in tokens if t.text.lower() == "apple"), None)
    assert apple_token is not None, "Token 'Apple' not found."
    assert apple_token.lemma == "Apple"
    assert apple_token.pos == "PROPN"

    # Check expected WordNet synsets and domains for 'Apple'
    wn = apple_token.wordnet
    assert wn is not None
    synset_names = [s["name"] for s in wn.synsets]
    domains = [s["domain"] for s in wn.synsets]
    assert "apple.n.01" in synset_names
    assert "apple.n.02" in synset_names
    assert "noun.food" in domains
    assert "noun.plant" in domains

    # Find the token for 'Cupertino'
    cupertino_token = next((t for t in tokens if t.text.lower() == "cupertino"), None)
    assert cupertino_token is not None, "Token 'Cupertino' not found."
    assert cupertino_token.lemma == "Cupertino"
    assert cupertino_token.pos == "PROPN"
    # Should have empty wordnet synsets
    wn_cupertino = cupertino_token.wordnet
    assert wn_cupertino is not None
    assert wn_cupertino.synsets == []

def test_concepcy_specific_data(nlp):
    doc = nlp("Apple is a company based in Cupertino.")
    tokens = extract_token_data(doc)
    company_token = next((t for t in tokens if t.text.lower() == "company"), None)
    assert company_token is not None, "Token 'company' not found."
    # Currently concepcy component is not populating token attributes,
    # so we expect concepcy to be None
    assert company_token.concepcy is None, f"Expected no concepcy data for 'company', but found: {company_token.concepcy}"

def test_wordnet_specific_data(nlp):
    doc = nlp("Apple is a company based in Cupertino.")
    tokens = extract_token_data(doc)
    company_token = next((t for t in tokens if t.text.lower() == "company"), None)
    assert company_token is not None, "Token 'company' not found."
    wn = company_token.wordnet
    assert wn is not None, "No wordnet data for 'company'."
    synset_names = [s["name"] for s in wn.synsets]
    domains = [s["domain"] for s in wn.synsets]
    assert "company.n.01" in synset_names
    assert "company.n.02" in synset_names
    assert "noun.group" in domains
    assert "noun.state" in domains
