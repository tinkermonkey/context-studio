# Testing Strategy for Context Studio API Client

This document outlines the comprehensive testing strategy for the API client, covering unit tests, integration tests, and best practices.

## Testing Architecture

### 1. **Test Structure**
```
__tests__/
├── setup.ts                 # Jest configuration and global setup
├── utils/
│   └── testUtils.tsx        # Testing utilities and helpers
└── api/
    ├── layerService.test.ts    # Unit tests for layer service
    ├── layerHooks.test.tsx     # Integration tests for layer hooks
    ├── errorHandling.test.ts   # Error handling tests
    └── integration.test.tsx    # End-to-end integration tests
```

### 2. **Testing Layers**

#### **Unit Tests** (`*.test.ts`)
- Test individual services in isolation
- Mock HTTP requests with `axios-mock-adapter`
- Verify correct API calls and data transformation
- Test error handling scenarios

#### **Hook Tests** (`*.test.tsx`)
- Test React Query hooks with `@testing-library/react-hooks`
- Verify caching behavior and state management
- Test loading, success, and error states
- Verify cache invalidation on mutations

#### **Integration Tests** (`integration.test.tsx`)
- Test complete user workflows
- Test component interactions with API
- Verify end-to-end data flow

## Testing Tools

### **Core Dependencies**
- `jest` - Testing framework
- `@testing-library/react-native` - React Native testing utilities
- `@testing-library/jest-dom` - Additional Jest matchers
- `axios-mock-adapter` - HTTP request mocking
- `jest-expo` - Expo-specific Jest preset

### **Test Utilities**
- `testUtils.tsx` - Custom render functions and mock data
- `mockAxios` - Pre-configured Axios mock adapter
- Query client helpers for React Query testing

## Running Tests

### **Basic Commands**
```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run only API tests
npm run test:api
```

### **Test Patterns**

#### **Service Testing Pattern**
```typescript
describe('LayerService', () => {
  beforeEach(() => {
    resetMocks(); // Clear axios mocks
  });

  it('should fetch layers successfully', async () => {
    // Arrange
    const mockData = [mockLayerData];
    mockAxios.onGet('/api/layers/').reply(200, mockData);

    // Act
    const result = await layerService.list();

    // Assert
    expect(result).toEqual(mockData);
    expect(mockAxios.history.get).toHaveLength(1);
  });
});
```

#### **Hook Testing Pattern**
```typescript
describe('useLayers', () => {
  it('should fetch layers successfully', async () => {
    // Arrange
    mockAxios.onGet('/api/layers/').reply(200, [mockLayerData]);

    // Act
    const { result } = renderHook(() => useLayers(), {
      wrapper: createQueryWrapper(),
    });

    // Assert
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toEqual([mockLayerData]);
  });
});
```

#### **Error Testing Pattern**
```typescript
it('should handle API errors correctly', async () => {
  // Arrange
  mockAxios.onGet('/api/layers/').reply(500, { message: 'Server error' });

  // Act & Assert
  await expect(layerService.list()).rejects.toThrow(ApiError);
});
```

## Test Categories

### **1. Service Layer Tests**
- ✅ HTTP method calls (GET, POST, PUT, DELETE)
- ✅ Parameter passing
- ✅ Response data transformation
- ✅ Error handling for different status codes
- ✅ Network error handling
- ✅ Validation error parsing

### **2. Hook Tests**
- ✅ Query execution and caching
- ✅ Loading, success, and error states
- ✅ Parameter passing to queries
- ✅ Conditional query execution
- ✅ Mutation success handling
- ✅ Cache invalidation on mutations
- ✅ Optimistic updates

### **3. Error Handling Tests**
- ✅ Custom error classes
- ✅ Error message extraction
- ✅ Type guards for error identification
- ✅ Error handling utilities
- ✅ Toast message generation

### **4. Integration Tests**
- 🔄 Component + API integration
- 🔄 Complete user workflows
- 🔄 Error boundary testing
- 🔄 Loading state handling

## Best Practices

### **1. Test Organization**
- Group related tests with `describe` blocks
- Use descriptive test names that explain the scenario
- Follow Arrange-Act-Assert pattern
- Reset mocks between tests

### **2. Mock Management**
- Use `resetMocks()` in `beforeEach`
- Create realistic mock data
- Test both success and error scenarios
- Mock external dependencies properly

### **3. Async Testing**
- Use `waitFor` for async operations
- Test loading states before completion
- Handle cleanup properly with act()

### **4. Coverage Goals**
- Aim for 80%+ coverage on API client code
- Focus on critical paths and error handling
- Don't just chase coverage numbers

## Test Data

### **Mock Data Structure**
```typescript
export const mockLayerData = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  title: 'Test Layer',
  definition: 'A test layer definition',
  // ... other properties
};
```

### **Mock Patterns**
- Consistent UUIDs for relationships
- Realistic data that matches API schema
- Edge cases (null values, empty arrays)
- Error response structures

## Debugging Tests

### **Common Issues**
1. **Async timing** - Use `waitFor` and proper async/await
2. **Mock cleanup** - Ensure `resetMocks()` is called
3. **Query cache** - Create fresh query clients for each test
4. **Console noise** - Mock console methods in setup

### **Debugging Tips**
```typescript
// Log axios history for debugging
console.log('Request history:', mockAxios.history);

// Check query cache state
console.log('Query cache:', queryClient.getQueryCache());

// Debug hook state
console.log('Hook result:', result.current);
```

## Continuous Integration

### **CI Configuration**
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Node
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      - name: Install dependencies
        run: npm ci
      - name: Run tests
        run: npm run test:coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

## Performance Testing

### **Load Testing Considerations**
- Test with large datasets
- Verify query deduplication
- Test cache performance
- Monitor memory usage in long-running tests

### **Metrics to Track**
- Test execution time
- Coverage percentage
- Number of API calls in tests
- Cache hit rates

## Future Enhancements

### **Planned Improvements**
- [ ] Visual regression testing with Storybook
- [ ] E2E testing with Detox
- [ ] Performance testing with automated metrics
- [ ] Accessibility testing
- [ ] Snapshot testing for components

### **Tools to Consider**
- `@storybook/react-native` for component testing
- `detox` for E2E testing
- `react-native-testing-library` extensions
- `jest-bench` for performance testing

This testing strategy ensures high confidence in the API client's reliability and provides a solid foundation for future development.
