/**
 * Graph API Test
 *
 * Simple test file to verify graph API integration
 */

import { graphService } from "./services/graph";

// Test basic graph operations
export async function testGraphAPI() {
  try {
    console.log("Testing Graph API...");

    // Test getting graph stats
    console.log("Fetching graph statistics...");
    const stats = await graphService.getStats();
    console.log("Graph stats:", stats);

    // Test getting SPARQL examples
    console.log("Fetching SPARQL examples...");
    const examples = await graphService.getSparqlExamples();
    console.log("SPARQL examples:", examples);

    console.log("Graph API test completed successfully!");
    return true;
  } catch (error) {
    console.error("Graph API test failed:", error);
    return false;
  }
}
