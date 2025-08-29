import React from 'react';
import NlpConceptChart from './NlpConceptChart';

// Test data based on the example JSON
const testData = {
  "text": "apples",
  "lemma": "apple",
  "pos": "NOUN",
  "concepcy": {
    "related_terms": [
      {
        "subject": {
          "id": "/c/en/apple",
          "label": "apple",
          "language": "en",
          "term": "/c/en/apple"
        },
        "object": {
          "id": "/c/en/fruit",
          "label": "fruit",
          "language": "en",
          "term": "/c/en/fruit"
        },
        "relation": "RelatedTo",
        "text": "[[apple]] is related to [[fruit]]",
        "weight": 12.80968383684781
      },
      {
        "subject": {
          "id": "/c/en/apple",
          "label": "apple",
          "language": "en",
          "term": "/c/en/apple"
        },
        "object": {
          "id": "/c/en/red",
          "label": "red",
          "language": "en",
          "term": "/c/en/red"
        },
        "relation": "RelatedTo",
        "text": "[[apple]] is related to [[red]]",
        "weight": 9.309350138436088
      },
      {
        "subject": {
          "id": "/c/en/apple/n/wn/plant",
          "label": "apple",
          "language": "en",
          "term": "/c/en/apple"
        },
        "object": {
          "id": "/c/en/apple_tree/n/wn/plant",
          "label": "apple tree",
          "language": "en",
          "term": "/c/en/apple_tree"
        },
        "relation": "IsA",
        "text": "[[apple]] is a type of [[apple tree]]",
        "weight": 2.0
      },
      {
        "subject": {
          "id": "/c/en/apple",
          "label": "Apple",
          "language": "en",
          "term": "/c/en/apple"
        },
        "object": {
          "id": "/c/en/computer_brand",
          "label": "computer brand",
          "language": "en",
          "term": "/c/en/computer_brand"
        },
        "relation": "IsA",
        "text": "[[Apple]] is a kind of [[computer brand]].",
        "weight": 2.0
      },
      {
        "subject": {
          "id": "/c/en/apple/n/wn/food",
          "label": "apple",
          "language": "en",
          "term": "/c/en/apple"
        },
        "object": {
          "id": "/c/en/pome/n/wn/plant",
          "label": "pome",
          "language": "en",
          "term": "/c/en/pome"
        },
        "relation": "IsA",
        "text": "[[apple]] is a type of [[pome]]",
        "weight": 2.0
      },
      {
        "subject": {
          "id": "/c/en/apple/n/wn/food",
          "label": "apple",
          "language": "en",
          "term": "/c/en/apple"
        },
        "object": {
          "id": "/c/en/edible_fruit/n/wn/food",
          "label": "edible fruit",
          "language": "en",
          "term": "/c/en/edible_fruit"
        },
        "relation": "IsA",
        "text": "[[apple]] is a type of [[edible fruit]]",
        "weight": 2.0
      },
      {
        "subject": {
          "id": "/c/en/apple",
          "label": "An apple",
          "language": "en",
          "term": "/c/en/apple"
        },
        "object": {
          "id": "/c/en/core",
          "label": "a core",
          "language": "en",
          "term": "/c/en/core"
        },
        "relation": "HasA",
        "text": "[[An apple]] has [[a core]]",
        "weight": 4.898979485566356
      },
      {
        "subject": {
          "id": "/c/en/apple",
          "label": "An apple",
          "language": "en",
          "term": "/c/en/apple"
        },
        "object": {
          "id": "/c/en/many_cooking_uses",
          "label": "many cooking uses",
          "language": "en",
          "term": "/c/en/many_cooking_uses"
        },
        "relation": "HasA",
        "text": "[[An apple]] has [[many cooking uses]]",
        "weight": 2.0
      }
    ]
  },
  "wordnet": {
    "synsets": [
      {
        "name": "apple.n.01",
        "definition": "fruit with red or yellow or green skin and sweet to tart crisp whitish flesh",
        "lemmas": [
          "apple"
        ],
        "pos": "n",
        "offset": 7739125,
        "domain": "noun.food"
      },
      {
        "name": "apple.n.02",
        "definition": "native Eurasian tree widely cultivated in many varieties for its firm rounded edible fruits",
        "lemmas": [
          "apple",
          "orchard_apple_tree",
          "Malus_pumila"
        ],
        "pos": "n",
        "offset": 12633994,
        "domain": "noun.plant"
      }
    ],
    "definitions": [
      "fruit with red or yellow or green skin and sweet to tart crisp whitish flesh",
      "native Eurasian tree widely cultivated in many varieties for its firm rounded edible fruits"
    ]
  }
};

const TestNlpConceptChart: React.FC = () => {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">NLP Concept Chart Test</h2>
      <NlpConceptChart 
        data={testData}
        config={{
          "RelatedTo": 2,
          "IsA": 4,
          "HasA": 2
        }}
      />
    </div>
  );
};

export default TestNlpConceptChart;
