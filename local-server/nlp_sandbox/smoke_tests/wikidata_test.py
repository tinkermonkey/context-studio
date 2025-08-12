from wikidata.client import Client

client = Client()
entity = client.get("Q42", load=True)  # Q42 is the Wikidata entity ID for Douglas Adams
print(f"Entity: {entity.label} ({entity.id})")
print(f"Description: {entity.description}")

# Print all properties and their values
for prop, value in entity.data['claims'].items():
    prop_entity = client.get(prop, load=False)
    print(f"Property: {prop_entity.label} ({prop})")
    for v in value:
        if 'mainsnak' in v and 'datavalue' in v['mainsnak']:
            datavalue = v['mainsnak']['datavalue']
            if datavalue['type'] == 'wikibase-entityid':
                value_entity = client.get(datavalue['value']['id'], load=False)
                print(f"  Value: {value_entity.label} ({value_entity.id})")
            else:
                print(f"  Value: {datavalue['value']}")
    print("-" * 40)