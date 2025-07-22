# Context Studio UX

Front-end code for the Context Studio app. This is front-end code only, the back-end is in a separate repository.

## Technology Stack
- **Language**: TypeScript
- **Components**: Flowbite React
- **Routing**: TanStack Router
- **State Management**: TanStack Query
- **CSS Framework**: Tailwind CSS
- **Icons**: Lucide React Native
- **API Client**: Type-safe API client built with Axios and OpenAPI
- **Testing**: Jest, React Testing Library

## Best Practices

### Code Style
- All markdown reports and summaries other than README.md should be placed in the `documentation/task_reports` directory
- use absolute imports for components and hooks
- Use `@/` as the base path for imports

### API Client Architecture
- Prefer type-safe clients generated from OpenAPI specs
- Use TanStack Query for state management and caching
- Implement proper error handling with custom error classes
- Structure API code in services layer with React hooks

### Testing Strategy
- Unit tests for services and utilities
- Integration tests for React hooks and components
- Mock external dependencies (APIs, native modules)
- Separate test configs for different test types (API vs integration)

### Documentation Standards
- Technical reports should include implementation details, architecture decisions, and current status
- Include code examples and usage patterns
- Document known issues and workarounds


### Code Structure
```text
/
├── .env                            # Dev environment variables (not in git)
├── .env.example                    # Environment variables example (in git)
├── .env.production                 # Production environment variables (not in git, very sensitive)
├── README.md                       # Project documentation
├── tailwind.config.js              # Tailwind configuration
├── tsconfig.json                   # Typescript config
│
├── package.json                    # Project dependencies and scripts
│
├── node_modules/                   # Ignore this, managed by npm
├── expo-archive/                   # Ignore this, it is for historical purposes only and contains the old Expo app which this is replacing
│
├── src/                            # Source code
│   ├── api/                        # API client and services
```

### UI Architecture

1. **React**: All UX must be `react` components

2. **Flowbite React**: Flowbite React components should be used for layout

3. **Responsive Layout**: A single UX will be used for desktop, tablet, and phones. Where possible, handle the responsiveness in the layout. Where needed, ensure the styling is responsive.

4. **Promote User Focus**: UX should be clean and focused without extraneous elements and decoration

5. **Error Handling**: Implement error catching within user workflows utilizing tools like useButterToast to communicate errors

6. **Asynchronous**: Where possible user interactions should be asynchronous to maintain performance and statelessness

### Testing and Reliability

3. **Graceful Degradation**: Implement fallback strategies when components fail

4. **Comprehensive Unit Tests**: Test individual components and functions in isolation where possible

5. **End-to-End Testing**: Create scenarios that test the full user journey

6. **Good Logging**: Make sure all files have good logging.