I've created a comprehensive test agent definition for context-studio-tester. The agent is grounded in actual project patterns and references real test files from the codebase:

**Key Features:**
- ✅ Covers all three test frameworks (pytest, Vitest, Playwright)
- ✅ References actual test files (`test_ontology_e2e.py`, `NlpAnalysisPanel.test.tsx`, `taxonomies.spec.ts`)
- ✅ Documents custom pytest markers (e2e, nlp, reference, llm, performance)
- ✅ Explains test organization (unit/integration/e2e/performance)
- ✅ Includes concrete command examples for running tests
- ✅ Provides diagnostic workflows for test failures
- ✅ Documents test patterns with real code examples
- ✅ Lists antipatterns specific to each framework
- ✅ Grounded in actual architecture (hexagonal, bounded contexts)

The agent can execute tests, diagnose failures, explain patterns, and validate test contracts across the entire stack.