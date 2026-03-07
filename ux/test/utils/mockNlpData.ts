// Use loose typing for test mocks to avoid tight coupling with service types
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const mockTokenData: any = {
  text: "database",
  lemma: "database",
  pos: "NOUN",
  tag: "NN",
  is_stop: false,
  wordnet: {
    synsets: [
      {
        name: "database.n.01",
        definition: "an organized body of related information",
        examples: ["the database contains sensitive information"],
        partOfSpeech: "noun",
      },
    ],
  },
  concepcy: {
    // cast to any for mock flexibility
    related_terms: [
      {
        relation: "IsA",
        terms: ["information_system", "data_structure"],
        scores: [0.8, 0.7],
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ] as any,
  },
};

export const mockEntityData = [
  {
    text: "Context Studio",
    label: "ORG",
    dbpedia: {
      uri: "https://dbpedia.org/resource/Context",
      label: "Context",
      similarity: 0.92,
    },
  },
];

export const mockAnalysis = {
  tokens: [
    mockTokenData,
    { ...mockTokenData, text: "the", is_stop: true, start: 1 },
  ],
  entities: mockEntityData,
};

export default mockTokenData;
