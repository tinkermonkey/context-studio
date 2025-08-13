/**
 * NLP Service Tests
 * 
 * Basic tests for the NLP service integration
 */

import { nlpService } from '../services/nlp';

// Simple test function to verify the API integration
export const testNLPIntegration = async () => {
  const testText = "Hello world! This is a test sentence with Apple Inc.";
  
  console.log('🧪 Testing NLP Analysis API Integration');
  console.log('📝 Test text:', testText);
  
  try {
    // Test full analysis
    console.log('\n🔍 Testing full analysis...');
    const analysis = await nlpService.analyzeText(testText);
    console.log('✅ Full analysis successful:', {
      textLength: analysis.text.length,
      tokenCount: analysis.tokens?.length || 0,
      entityCount: analysis.entities?.length || 0
    });

    // Check tokens structure
    if (analysis.tokens && analysis.tokens.length > 0) {
      const sampleToken = analysis.tokens[0];
      console.log('📋 Sample token structure:', {
        text: sampleToken.text,
        lemma: sampleToken.lemma,
        pos: sampleToken.pos,
        tag: sampleToken.tag,
        hasWordNet: !!sampleToken.wordnet,
        hasConcepcy: !!sampleToken.concepcy,
        hasSense2Vec: !!sampleToken.sense2vec,
        sense2vecInModel: sampleToken.sense2vec?.in_s2v
      });
    }

    // Check entities structure
    if (analysis.entities && analysis.entities.length > 0) {
      const sampleEntity = analysis.entities[0];
      console.log('🏷️ Sample entity structure:', {
        text: sampleEntity.text,
        label: sampleEntity.label,
        kb_id: sampleEntity.kb_id,
        hasDBpedia: !!sampleEntity.dbpedia
      });
    }

    // Test token extraction
    console.log('\n🔤 Testing token extraction...');
    const tokens = await nlpService.extractTokens(testText);
    console.log('✅ Token extraction successful:', {
      tokenCount: tokens.length,
      sampleTokens: tokens.slice(0, 3).map(t => ({
        text: t.text,
        pos: t.pos,
        lemma: t.lemma
      }))
    });

    // Test entity extraction
    console.log('\n🏷️ Testing entity extraction...');
    const entities = await nlpService.extractEntities(testText);
    console.log('✅ Entity extraction successful:', {
      entityCount: entities.length,
      entityDetails: entities.map(e => ({
        text: e.text,
        label: e.label,
        kb_id: e.kb_id
      }))
    });

    console.log('\n🎉 All NLP API tests passed!');
    return true;

  } catch (error) {
    console.error('❌ NLP API test failed:', error);
    console.error('🔧 This might be due to:');
    console.error('   - Server not running');
    console.error('   - NLP endpoint not available');
    console.error('   - Network connectivity issues');
    console.error('   - API request format mismatch');
    return false;
  }
};

// Function to test with various text inputs
export const testNLPWithVariousInputs = async () => {
  const testCases = [
    "Simple text",
    "The quick brown fox jumps over the lazy dog.",
    "Apple Inc. is a technology company founded by Steve Jobs in Cupertino, California.",
    "Machine learning and artificial intelligence are transforming the world. Google and Microsoft are leading this revolution."
  ];

  console.log('🧪 Testing NLP with various inputs...');

  for (const testText of testCases) {
    try {
      console.log(`\n📝 Testing: "${testText}"`);
      const result = await nlpService.analyzeText(testText);
      
      // Log detailed results
      console.log(`✅ Success - Text: ${result.text.length} chars`);
      console.log(`   📊 Tokens: ${result.tokens?.length || 0}`);
      console.log(`   🏷️ Entities: ${result.entities?.length || 0}`);
      
      // Show token POS distribution
      if (result.tokens && result.tokens.length > 0) {
        const posCount: Record<string, number> = {};
        result.tokens.forEach(token => {
          if (token.pos) {
            posCount[token.pos] = (posCount[token.pos] || 0) + 1;
          }
        });
        console.log(`   📝 POS tags:`, posCount);
      }
      
      // Show entity types
      if (result.entities && result.entities.length > 0) {
        const entityTypes: Record<string, number> = {};
        result.entities.forEach(entity => {
          if (entity.label) {
            entityTypes[entity.label] = (entityTypes[entity.label] || 0) + 1;
          }
        });
        console.log(`   🏷️ Entity types:`, entityTypes);
      }
      
    } catch (error) {
      console.error(`❌ Failed for: "${testText}"`, error);
    }
  }
};

// Test specific NLP features
export const testNLPFeatures = async () => {
  const testText = "Barack Obama, the former President of the United States, visited Paris, France last year.";
  
  console.log('🧪 Testing specific NLP features...');
  console.log('📝 Test text:', testText);
  
  try {
    const result = await nlpService.analyzeText(testText);
    
    // Test token features
    console.log('\n🔤 Token Features:');
    result.tokens?.forEach((token, index) => {
      if (index < 5) { // Show first 5 tokens
        console.log(`   Token: "${token.text}"`);
        console.log(`     - Lemma: ${token.lemma || 'N/A'}`);
        console.log(`     - POS: ${token.pos || 'N/A'}`);
        console.log(`     - Tag: ${token.tag || 'N/A'}`);
        console.log(`     - Position: ${token.start}-${token.end}`);
        
        if (token.wordnet) {
          console.log(`     - WordNet synsets: ${token.wordnet.synsets?.length || 0}`);
          console.log(`     - WordNet definitions: ${token.wordnet.definitions?.length || 0}`);
        }
        
        if (token.concepcy) {
          console.log(`     - Concepcy score: ${token.concepcy.score || 'N/A'}`);
          console.log(`     - Related terms: ${token.concepcy.related_terms?.length || 0}`);
        }
        
        if (token.sense2vec) {
          console.log(`     - Sense2Vec in model: ${token.sense2vec.in_s2v || false}`);
          console.log(`     - Sense2Vec key: ${token.sense2vec.key || 'N/A'}`);
          console.log(`     - Sense2Vec frequency: ${token.sense2vec.freq || 'N/A'}`);
          console.log(`     - Similar senses: ${token.sense2vec.other_senses?.length || 0}`);
        }
        
        console.log('');
      }
    });
    
    // Test entity features
    console.log('\n🏷️ Entity Features:');
    result.entities?.forEach((entity, index) => {
      console.log(`   Entity: "${entity.text}"`);
      console.log(`     - Label: ${entity.label || 'N/A'}`);
      console.log(`     - KB ID: ${entity.kb_id || 'N/A'}`);
      
      if (entity.dbpedia) {
        console.log(`     - DBpedia URI: ${entity.dbpedia.uri || 'N/A'}`);
        console.log(`     - DBpedia label: ${entity.dbpedia.label || 'N/A'}`);
        console.log(`     - Similarity: ${entity.dbpedia.similarity || 'N/A'}`);
      }
      
      console.log('');
    });
    
    console.log('✅ Feature test completed successfully!');
    
  } catch (error) {
    console.error('❌ Feature test failed:', error);
  }
};
