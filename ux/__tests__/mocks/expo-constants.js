/**
 * Mock for expo-constants to avoid import issues during API testing
 */

module.exports = {
  expoConfig: {
    extra: {
      API_URL: 'http://localhost:8000'
    }
  },
  ExecutionEnvironment: {
    StoreClient: 'StoreClient',
    Standalone: 'Standalone'
  }
};
