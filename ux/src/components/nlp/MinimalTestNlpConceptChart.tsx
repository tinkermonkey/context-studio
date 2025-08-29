import React from 'react';
import NlpConceptChart from './NlpConceptChart';

// Minimal test data to verify the component works
const minimalTestData = {
  text: "apple",
  lemma: "apple",
  pos: "NOUN",
  concepcy: {
    related_terms: [
      {
        subject: {
          id: "/c/en/apple",
          label: "apple",
          language: "en",
          term: "/c/en/apple"
        },
        object: {
          id: "/c/en/fruit",
          label: "fruit",
          language: "en",
          term: "/c/en/fruit"
        },
        relation: "RelatedTo",
        text: "[[apple]] is related to [[fruit]]",
        weight: 12.8
      },
      {
        subject: {
          id: "/c/en/apple",
          label: "apple",
          language: "en",
          term: "/c/en/apple"
        },
        object: {
          id: "/c/en/red",
          label: "red",
          language: "en",
          term: "/c/en/red"
        },
        relation: "RelatedTo",
        text: "[[apple]] is related to [[red]]",
        weight: 9.3
      },
      {
        subject: {
          id: "/c/en/apple",
          label: "apple",
          language: "en",
          term: "/c/en/apple"
        },
        object: {
          id: "/c/en/edible_fruit",
          label: "edible fruit",
          language: "en",
          term: "/c/en/edible_fruit"
        },
        relation: "IsA",
        text: "[[apple]] is a type of [[edible fruit]]",
        weight: 2.0
      }
    ]
  },
  wordnet: {
    synsets: [
      {
        name: "apple.n.01",
        definition: "fruit with red or yellow or green skin and sweet to tart crisp whitish flesh",
        lemmas: ["apple"],
        pos: "n",
        offset: 7739125,
        domain: "noun.food"
      }
    ],
    definitions: [
      "fruit with red or yellow or green skin and sweet to tart crisp whitish flesh"
    ]
  }
};

const MinimalTestNlpConceptChart: React.FC = () => {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">Minimal NLP Concept Chart Test</h2>
      <p className="mb-4 text-gray-600">
        This test uses a minimal dataset to verify the component is working correctly.
      </p>
      <NlpConceptChart 
        data={minimalTestData}
        config={{
          "RelatedTo": 2,
          "IsA": 1,
          "HasA": 1
        }}
      />
    </div>
  );
};

export default MinimalTestNlpConceptChart;
