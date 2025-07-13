/**
 * Jest configuration for API client testing
 * This configuration avoids Expo-specific presets to prevent import scope issues
 * with Expo SDK 53+ "winter" runtime.
 */

module.exports = {
  // Use Node.js environment for API testing
  testEnvironment: 'jsdom',
  
  // Setup files
  setupFilesAfterEnv: ['<rootDir>/__tests__/setup.ts'],
  
  // Test patterns - only run API tests
  testMatch: [
    '**/__tests__/api/**/*.(test|spec).(js|jsx|ts|tsx)'
  ],
  
  // Coverage collection
  collectCoverageFrom: [
    'api/**/*.{js,jsx,ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/__tests__/**'
  ],
  
  // Coverage thresholds
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  
  // Module name mapping
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
    // Mock expo constants for API tests
    'expo-constants': '<rootDir>/__tests__/mocks/expo-constants.js'
  },
  
  // Transform configuration using standard Babel presets
  transform: {
    '^.+\\.(js|jsx|ts|tsx)$': ['babel-jest', {
      presets: [
        ['@babel/preset-env', { 
          targets: { node: 'current' },
          modules: 'commonjs'
        }],
        ['@babel/preset-react', { 
          runtime: 'automatic' 
        }],
        '@babel/preset-typescript'
      ]
    }]
  },
  
  // Transform ignore patterns - only transform necessary modules
  transformIgnorePatterns: [
    'node_modules/(?!(axios|@tanstack/react-query|@testing-library/react|react-native|@react-native|expo)/)'
  ],
  
  // Module file extensions
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  
  // Resolve modules
  resolver: undefined,
  
  // Clear mocks between tests
  clearMocks: true,
  
  // Reset modules between tests
  resetMocks: true,
  
  // Verbose output
  verbose: true,
  
  // Timeout for tests
  testTimeout: 10000,
  
  // Globals
  globals: {}
};
