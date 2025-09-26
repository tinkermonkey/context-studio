# Context Studio UX

Front-end code for the Context Studio app. This is front-end code only, the back-end is in a separate repository.

## Core Principles

**IMPORTANT: You MUST follow these principles in all code changes and PRP generations:**

### KISS (Keep It Simple, Stupid)

- Simplicity should be a key goal in design
- Choose straightforward solutions over complex ones whenever possible
- Simple solutions are easier to understand, maintain, and debug

### YAGNI (You Aren't Gonna Need It)

- Avoid building functionality on speculation
- Implement features only when they are needed, not when you anticipate they might be useful in the future

## Technology Stack

- **Language**: TypeScript
- **Components**: Flowbite React, TanStack Tables, TanStack Forms
- **Build Tool**: Vite
- **Routing**: TanStack Router
- **State Management**: TanStack Query
- **CSS Framework**: Tailwind CSS
- **Icons**: Lucide React Native
- **API Client**: Type-safe API client built with Axios and OpenAPI
- **UI State**: Zustand for complex ui state management
- **Testing**: Jest, React Testing Library

## Best Practices

- Write clean, readable, and maintainable code
- Use meaningful variable and function names, don't use terms like "enhanced", "improved", "optimized" in names
- When api signatures change, run the `npm run generate-types` command to regenerate the api types and then update the hooks and services as needed

### Code Style

- Don't create documentation files unless explicitly requested
- All markdown reports and summaries other than README.md should be placed in the `documentation/task_reports` directory
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
│   │   ├── services/               # API service files
│   │   ├── hooks/                  # Custom React hooks for API interactions
│   │   └── types/                  # Type definitions for API responses
│   │
│   ├── components/                 # Reusable React components
│   │   ├── node_selectors/         # Components for selecting nodes (e.g., layers, nodes)
│   │   ├── node_tables/            # Components for displaying node tables
│   │   ├── ui/                     # UI components (e.g., buttons, inputs)
│   │   └── layout/                 # Layout components
```

### UI Architecture

1. **React**: All UX must be `react` components

2. **Flowbite React**: Flowbite React components should be used for interface elements where possible

3. **Promote User Focus**: UX should be clean and focused without extraneous elements and decoration

4. **Error Handling**: Implement error catching within user workflows utilizing tools like useButterToast to communicate errors

5. **Asynchronous**: Where possible user interactions should be asynchronous to maintain performance and statelessness

### Testing and Reliability

3. **Graceful Degradation**: Implement fallback strategies when components fail

4. **Comprehensive Unit Tests**: Test individual components and functions in isolation where possible

5. **End-to-End Testing**: Create scenarios that test the full user journey

6. **Good Logging**: Make sure all files have good logging.
