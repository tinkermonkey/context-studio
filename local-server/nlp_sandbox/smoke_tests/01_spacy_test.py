import spacy

nlp = spacy.load("en_core_web_lg")

doc = nlp('A sentence about apple sauce, I like tacos.')

for ent in doc.ents:
    print((ent.text, ent.kb_id_, ent._.dbpedia_raw_result['@similarityScore']))

for token in doc:
    print("-" * 40)
    print(f"{'Token':>10}: ({token.i}) {token.text}")
    #print(f"{'Lemma':>10}: {token.lemma_}, POS: {token.pos_}, Tag: {token.tag_}, Dep: {token.dep_}, Shape: {token.shape_}, Alpha: {token.is_alpha}, Stop: {token.is_stop}")
    print(f"{'Lemma':>10}: {token.lemma_}")
    print(f"{'POS':>10}: {token.pos_}")
    #print(f"{'Tag':>10}: {token.tag}")
    print(f"{'Tag':>10}: {token.tag_}")
    print(f"{'Dep':>10}: {token.dep_}")
    print(f"{'Head':>10}: {token.head.text} (ID: {token.head.i}, IDX: {token.head.idx})")
    print(f"{'Ancestors':>10}: {', '.join([ancestor.text + ' (ID: ' + str(ancestor.i) + ', IDX: ' + str(ancestor.idx) + ')' for ancestor in token.ancestors])}")
    print(f"{'Conjuncts':>10}: {list(token.conjuncts)}")
    print(f"{'Children':>10}: {', '.join([child.text + ' (ID: ' + str(child.i) + ', IDX: ' + str(child.idx) + ')' for child in token.children])}")
    print(f"{'Subtree':>10}: {list(token.subtree)}")
    #print(f"{'Morph':>10}: {token.morph}")
    print(f"{'Sentiment':>10}: {token.sentiment}")
    print(f"{'Index':>10}: {token.idx}")
    #print(f"{'Dep':>10}: {token.dep}")
    #print(f"{'Pos':>10}: {token.pos}")
    print(f"{'Is OOV':>10}: {token.is_oov}")
    print(f"{'Like URL':>10}: {token.like_url}")
    #print(f"{'Is Sent. Start':>10}: {token.is_sent_start}")
    #print(f"{'Is Sent. End':>10}: {token.is_sent_end}")
    print(f"{'Is Digit':>10}: {token.is_digit}")
    print(f"{'Is Stop':>10}: {token.is_stop}")
    print(f"{'Ent ID':>10}: {token.ent_id_}")
    print(f"{'KB Ent ID':>10}: {token.ent_kb_id_}")
    print(f"{'Ent IOB':>10}: {token.ent_iob_}")
    print(f"{'Ent Type':>10}: {token.ent_type_}")
    #print(f"{'Sent':>10}: {token.sent}")
