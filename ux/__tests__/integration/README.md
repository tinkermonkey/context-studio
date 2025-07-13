# Integration Tests

This directory contains integration tests that require React Native environment setup and are not suitable for the pure API testing environment.

## Test Categories

### **Hook Tests**
Tests for React Query hooks that interact with the API:
- `layerHooks.test.tsx` - Tests for layer-related hooks
- `termsHooks.test.tsx` - Tests for term-related hooks  
- `relationshipsHooks.test.tsx` - Tests for relationship-related hooks

### **Integration Tests**
Tests that exercise multiple components working together:
- `integration.test.tsx` - General integration tests
- `termsRelationshipsIntegration.test.tsx` - Terms and relationships integration

## Running Integration Tests

### Prerequisites
These tests require:
- React Native environment setup
- `@testing-library/react-native`
- Expo environment variables and constants

### Commands

```bash
# Run all integration tests (may fail due to Expo SDK 53+ issues)
npm run test:integration

# Run integration tests in watch mode
npm run test:integration:watch

# Run specific integration test
npm run test:integration -- layerHooks.test.tsx
```

## Current Status

⚠️ **Known Issues**: These tests currently fail due to Expo SDK 53+ "winter" runtime conflicts with Jest. See `JEST_ISSUES_ANALYSIS.md` for details.

**Alternative Testing Approaches:**

1. **Manual Testing**: Use the example components in `components/examples/`
2. **App Testing**: Test hooks directly in the running Expo app
3. **E2E Testing**: Consider Detox for end-to-end testing
4. **Component Testing**: Use Storybook for isolated component testing

## Future Improvements

When Expo SDK Jest integration improves, these tests can be converted to run with:
- Updated Expo Jest presets
- Improved React Native testing library support
- Better environment isolation

## Test Structure

All integration tests follow the pattern:
- Use `@testing-library/react-native` for rendering
- Mock API responses with `axios-mock-adapter`
- Test hook behavior and component integration
- Verify error handling and loading states
