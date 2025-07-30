# Enhanced API Error Handling

This document describes the enhanced error handling system implemented to provide better error reporting and user experience.

## Overview

The enhanced error handling system provides:

1. **Comprehensive Error Types**: Specific error classes for different HTTP status codes
2. **Improved Error Parsing**: Better parsing of FastAPI validation errors and other detailed responses
3. **Enhanced Interceptors**: More sophisticated error handling in axios interceptors
4. **Form-Friendly Hooks**: Specialized hooks for form validation error handling
5. **Error Boundary Components**: React components for graceful error display
6. **Better Error Context**: Service and operation context for debugging

## API Client Updates

### Generated Types
The API client types are automatically generated from the OpenAPI specification using `openapi-typescript`:

```bash
npm run generate-types
```

This regenerates `src/api/client/types.ts` with the latest API schema including error response types.

### Enhanced Error Classes

Located in `src/api/errors/ApiError.ts`:

- **ApiError**: Base error class with enhanced properties
- **ValidationError**: Handles FastAPI validation errors with field-specific details
- **NotFoundError**: 404 errors
- **ConflictError**: 409 conflicts
- **BadRequestError**: 400 bad requests
- **UnauthorizedError**: 401 authentication errors
- **ForbiddenError**: 403 permission errors
- **TooManyRequestsError**: 429 rate limiting
- **InternalServerError**: 500 server errors
- **ServiceUnavailableError**: 503 service unavailable
- **NetworkError**: Network connectivity issues

### Error Handlers

Located in `src/api/errors/errorHandlers.ts`:

```typescript
// Handle errors with context
const error = handleApiError(err, {
  context: 'Creating domain',
  showToast: true,
  logError: true
});

// Get user-friendly error message
const message = getErrorMessage(error);

// Get detailed error information
const details = getDetailedErrorInfo(error);

// Check error types
if (isValidationError(error)) {
  const fieldErrors = error.validationErrors;
}
```

### Enhanced Interceptors

The axios interceptor in `src/api/client/interceptors.ts` now:

- Creates specific error types based on HTTP status codes
- Properly parses FastAPI validation error responses
- Includes endpoint and method information in errors
- Provides better error context for debugging

## Service Layer Enhancements

### Base Service

Enhanced `src/api/services/base.ts` includes:

```typescript
// Error context wrapper
protected async withErrorContext<T>(
  operation: () => Promise<T>,
  context: string
): Promise<T>

// Validation helpers
protected validateRequired<T>(value: T, paramName: string): T
protected sanitizeString(value: string, paramName: string, maxLength?: number): string
```

### Service Implementation

Services now use enhanced error handling:

```typescript
async create(data: DomainCreate): Promise<DomainOut> {
  return this.withErrorContext(
    () => {
      this.validateRequired(data, 'Domain data');
      this.validateRequired(data.title, 'Domain title');
      this.sanitizeString(data.title, 'Domain title', 255);
      
      return this.postResource<DomainOut>(ENDPOINTS.DOMAINS + '/', data);
    },
    'create domain'
  );
}
```

## React Hooks Enhancements

### Enhanced Mutation Hooks

Located in `src/api/hooks/domains/useDomainMutations.ts`:

```typescript
// Standard mutation with error handling
const { mutate, error } = useCreateDomain();

// Form-friendly mutation with validation error parsing
const { 
  mutate, 
  isPending, 
  formError, 
  isValidationError 
} = useCreateDomainWithFormErrors();
```

### Usage Example

```typescript
const { mutate, formError, isValidationError } = useCreateDomainWithFormErrors();

// Handle form submission
const handleSubmit = (data) => {
  mutate(data, {
    onSuccess: (result) => {
      // Handle success
    }
  });
};

// Display errors
if (formError) {
  if (isValidationError) {
    // Show field-specific errors
    const titleErrors = formError.fieldErrors.title;
  } else {
    // Show general error
    console.error(formError.message);
  }
}
```

## UI Components

### Error Boundary

Located in `src/components/misc/error_boundary.tsx`:

```typescript
// Wrap components with error boundary
<ApiErrorBoundary showDetails={true}>
  <MyComponent />
</ApiErrorBoundary>

// HOC wrapper
const SafeComponent = withApiErrorBoundary(MyComponent, { 
  showDetails: false 
});

// Inline error display
<InlineApiError error={error} showDetails={true} />
```

### Enhanced Form Example

Located in `src/components/forms/enhanced_domain_form.tsx`:

```typescript
const { mutate, isPending, formError, isValidationError } = useCreateDomainWithFormErrors();

// Get field-specific errors
const titleErrors = formError?.fieldErrors?.title || [];

// Display in form
<TextInput
  value={title}
  color={titleErrors.length > 0 ? 'failure' : undefined}
/>
{titleErrors.length > 0 && (
  <p className="text-red-600 text-sm mt-1">{titleErrors.join(', ')}</p>
)}
```

## Error Response Types

The system handles various error response formats:

### Validation Errors (422)
```json
{
  "detail": [
    {
      "loc": ["body", "title"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### General Errors
```json
{
  "message": "Error description",
  "code": "ERROR_CODE",
  "detail": { "additional": "context" }
}
```

## Best Practices

1. **Use Specific Error Types**: Import and use specific error classes rather than generic Error
2. **Provide Context**: Use `withErrorContext` in services to add operation context
3. **Validate Early**: Use validation helpers in services before making API calls
4. **Handle in UI**: Use form-friendly hooks for better UX
5. **Log Appropriately**: Use structured logging with error context
6. **Show User-Friendly Messages**: Use `getUserFriendlyMessage()` for display

## Migration Guide

### For Existing Services
1. Wrap operations with `withErrorContext()`
2. Add input validation using provided helpers
3. Import enhanced error types

### For Existing Components
1. Use form-friendly mutation hooks
2. Add error boundaries where appropriate
3. Display field-specific validation errors

### For Error Handling
1. Import error handlers from `errorHandlers.ts`
2. Use type-specific error checking functions
3. Implement proper error display patterns

## Development Workflow

1. **Update API**: Modify backend API endpoints
2. **Regenerate Types**: Run `npm run generate-types`
3. **Update Services**: Enhance services with validation and context
4. **Update Hooks**: Use enhanced mutation hooks in components
5. **Test Error Scenarios**: Verify error handling in various scenarios
6. **Type Check**: Run `npm run typecheck` to verify type safety
