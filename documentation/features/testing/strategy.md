# Testing Strategy

## Overview

Context Studio employs a comprehensive testing strategy that includes unit tests, integration tests, performance tests, and end-to-end testing. The testing infrastructure covers both backend Python services and frontend React components, ensuring reliability and maintainability across the entire system.

## Testing Philosophy

### Testing Pyramid
```
                    E2E Tests
                   /         \
              Integration Tests
             /                 \
           Unit Tests         Component Tests
         /          \        /              \
   Service Layer  API Layer  Components   Hooks
```

### Coverage Goals
- **Unit Tests**: 85%+ coverage for business logic
- **Integration Tests**: Critical workflows and API contracts
- **Performance Tests**: Key performance benchmarks
- **E2E Tests**: Primary user workflows

## Backend Testing Framework

### Technology Stack
- **pytest**: Primary testing framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking utilities
- **SQLAlchemy**: Database testing utilities
- **httpx**: HTTP client testing
- **faker**: Test data generation

### Test Organization

```
tests/
├── unit_tests/           # Service and business logic tests
│   ├── test_*.py        # Individual service tests
│   └── conftest.py      # Test configuration and fixtures
├── integration_tests/    # API and workflow tests
│   ├── test_*_api.py    # API endpoint tests
│   └── test_*_workflow.py # End-to-end workflow tests
├── performance_tests/    # Load and performance tests
│   ├── test_*_performance.py
│   └── benchmarks/      # Performance benchmarks
├── conftest.py          # Global test configuration
├── test_db_utils.py     # Database testing utilities
├── test_config.py       # Test configuration
└── test_environment.py  # Environment setup
```

### Test Configuration

#### Global Test Setup (`conftest.py`)
```python
import pytest
import asyncio
from pathlib import Path
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_database():
    """Create test database."""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()

    engine = create_engine(f"sqlite:///{temp_db.name}")
    # Apply migrations
    run_migrations(engine)

    yield engine

    # Cleanup
    Path(temp_db.name).unlink()

@pytest.fixture
def test_session(test_database):
    """Create database session for tests."""
    Session = sessionmaker(bind=test_database)
    session = Session()

    yield session

    session.rollback()
    session.close()

@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    from unittest.mock import Mock
    mock = Mock()
    mock.execute_pipeline.return_value = {
        "response": "Test response",
        "cost_usd": 0.01,
        "duration_ms": 1000
    }
    return mock
```

## Unit Testing

### Service Layer Testing

#### Structure Node Service Tests
```python
# test_node_service.py
import pytest
from services.node_service import NodeService
from database.models import StructureNode

@pytest.fixture
def node_service(test_session):
    return NodeService(test_session)

class TestNodeService:
    @pytest.mark.asyncio
    async def test_create_node(self, node_service):
        """Test node creation."""
        node_data = {
            "title": "Test Node",
            "description": "Test description",
            "node_type": "domain",
            "parent_id": None
        }

        result = await node_service.create_node(node_data)

        assert result.title == "Test Node"
        assert result.node_type == "domain"
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_create_node_with_parent(self, node_service):
        """Test node creation with parent."""
        # Create parent layer
        parent = await node_service.create_node({
            "title": "Parent Layer",
            "node_type": "layer"
        })

        # Create child domain
        child = await node_service.create_node({
            "title": "Child Domain",
            "node_type": "domain",
            "parent_id": parent.id
        })

        assert child.parent_id == parent.id

    @pytest.mark.asyncio
    async def test_hierarchy_validation(self, node_service):
        """Test that hierarchy rules are enforced."""
        domain = await node_service.create_node({
            "title": "Test Domain",
            "node_type": "domain"
        })

        # Should fail: domain cannot be parent of layer
        with pytest.raises(ValueError, match="Invalid hierarchy"):
            await node_service.create_node({
                "title": "Invalid Layer",
                "node_type": "layer",
                "parent_id": domain.id
            })

    @pytest.mark.asyncio
    async def test_search_nodes(self, node_service):
        """Test node search functionality."""
        # Create test nodes
        await node_service.create_node({
            "title": "Machine Learning",
            "node_type": "domain"
        })
        await node_service.create_node({
            "title": "Deep Learning",
            "node_type": "domain"
        })

        # Search for "learning"
        results = await node_service.search_nodes("learning")

        assert len(results) == 2
        assert all("learning" in r.title.lower() for r in results)
```

#### LLM Service Tests
```python
# test_llm_service.py
import pytest
from unittest.mock import AsyncMock, patch
from llm.service import LLMService
from llm.models import PipelineFlavor

@pytest.fixture
def llm_service(test_session):
    return LLMService(test_session)

class TestLLMService:
    @pytest.mark.asyncio
    async def test_execute_pipeline(self, llm_service):
        """Test pipeline execution."""
        # Create test flavor
        flavor = PipelineFlavor(
            name="test_flavor",
            provider="openai",
            model="gpt-3.5-turbo",
            user_prompt_template="Define: {{term}}"
        )

        with patch('llm.service.openai_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=MockOpenAIResponse(
                    content="Test definition",
                    usage={"prompt_tokens": 10, "completion_tokens": 20}
                )
            )

            result = await llm_service.execute_pipeline(
                flavor=flavor,
                inputs={"term": "Machine Learning"}
            )

            assert result.response == "Test definition"
            assert result.prompt_tokens == 10
            assert result.completion_tokens == 20

    @pytest.mark.asyncio
    async def test_cost_calculation(self, llm_service):
        """Test cost calculation for different providers."""
        result = llm_service.calculate_cost(
            provider="openai",
            model="gpt-4",
            prompt_tokens=1000,
            completion_tokens=500
        )

        # GPT-4 pricing: $0.03/1k prompt, $0.06/1k completion
        expected_cost = (1000 * 0.03 / 1000) + (500 * 0.06 / 1000)
        assert abs(result - expected_cost) < 0.001

class MockOpenAIResponse:
    def __init__(self, content, usage):
        self.choices = [MockChoice(content)]
        self.usage = usage

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockMessage:
    def __init__(self, content):
        self.content = content
```

## Integration Testing

### API Integration Tests

#### Structure Nodes API Tests
```python
# test_structure_nodes_api.py
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from app import app

@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

class TestStructureNodesAPI:
    @pytest.mark.asyncio
    async def test_create_node_endpoint(self, async_client):
        """Test POST /api/structure_nodes."""
        response = await async_client.post(
            "/api/structure_nodes",
            json={
                "title": "Test Node",
                "description": "Test description",
                "node_type": "layer"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Node"
        assert data["node_type"] == "layer"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_nodes_endpoint(self, async_client):
        """Test GET /api/structure_nodes."""
        # Create test nodes first
        await async_client.post("/api/structure_nodes", json={
            "title": "Layer 1",
            "node_type": "layer"
        })
        await async_client.post("/api/structure_nodes", json={
            "title": "Layer 2",
            "node_type": "layer"
        })

        response = await async_client.get("/api/structure_nodes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) >= 2

    @pytest.mark.asyncio
    async def test_node_hierarchy_creation(self, async_client):
        """Test creating node hierarchy through API."""
        # Create layer
        layer_response = await async_client.post("/api/structure_nodes", json={
            "title": "AI Layer",
            "node_type": "layer"
        })
        layer_id = layer_response.json()["id"]

        # Create domain
        domain_response = await async_client.post("/api/structure_nodes", json={
            "title": "Machine Learning",
            "node_type": "domain",
            "parent_id": layer_id
        })
        domain_id = domain_response.json()["id"]

        # Create term
        term_response = await async_client.post("/api/structure_nodes", json={
            "title": "Neural Network",
            "node_type": "term",
            "parent_id": domain_id
        })

        assert layer_response.status_code == 201
        assert domain_response.status_code == 201
        assert term_response.status_code == 201

        # Verify hierarchy
        term_data = term_response.json()
        assert term_data["parent_id"] == domain_id

    @pytest.mark.asyncio
    async def test_error_handling(self, async_client):
        """Test API error handling."""
        # Test invalid node type
        response = await async_client.post("/api/structure_nodes", json={
            "title": "Invalid Node",
            "node_type": "invalid_type"
        })

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data
```

### Workflow Integration Tests

#### Change Management Workflow
```python
# test_change_management_workflow.py
import pytest
from services.changeset_manager import ChangesetManager
from services.identity_manager import IdentityManager

@pytest.mark.asyncio
async def test_complete_change_workflow(test_session):
    """Test complete change management workflow."""
    identity_manager = IdentityManager(test_session)
    changeset_manager = ChangesetManager(test_session)

    # Create identity
    author = await identity_manager.create_identity({
        "display_name": "Test Author",
        "email": "author@test.com"
    })

    reviewer = await identity_manager.create_identity({
        "display_name": "Test Reviewer",
        "email": "reviewer@test.com"
    })

    # Create changeset
    changeset = await changeset_manager.create_changeset({
        "title": "Add ML concepts",
        "description": "Adding machine learning domain structure",
        "author_identity_id": author.id,
        "change_event_ids": ["event-1", "event-2"]
    })

    assert changeset.status == "draft"

    # Propose changeset
    await changeset_manager.propose_changeset(
        changeset.id,
        reviewers=[reviewer.id]
    )

    updated_changeset = await changeset_manager.get_changeset(changeset.id)
    assert updated_changeset.status == "proposed"

    # Review changeset
    await changeset_manager.review_changeset(
        changeset.id,
        reviewer.id,
        decision="approve",
        comments="Looks good"
    )

    # Merge changeset
    await changeset_manager.merge_changeset(changeset.id)

    final_changeset = await changeset_manager.get_changeset(changeset.id)
    assert final_changeset.status == "merged"
    assert final_changeset.merged_at is not None
```

## Performance Testing

### Load Testing

#### API Performance Tests
```python
# test_api_performance.py
import pytest
import asyncio
import time
from httpx import AsyncClient

class TestAPIPerformance:
    @pytest.mark.asyncio
    async def test_concurrent_node_creation(self):
        """Test API performance under concurrent load."""
        async def create_node(client, i):
            response = await client.post("/api/structure_nodes", json={
                "title": f"Performance Test Node {i}",
                "node_type": "domain"
            })
            return response.status_code == 201

        async with AsyncClient(app=app, base_url="http://test") as client:
            start_time = time.time()

            # Create 100 nodes concurrently
            tasks = [create_node(client, i) for i in range(100)]
            results = await asyncio.gather(*tasks)

            end_time = time.time()
            duration = end_time - start_time

            # Performance assertions
            assert all(results), "All requests should succeed"
            assert duration < 10.0, f"Should complete in <10s, took {duration:.2f}s"
            assert len(results) == 100

    @pytest.mark.asyncio
    async def test_search_performance(self):
        """Test search performance with large dataset."""
        # Create test dataset (this would be in setup)
        # ... code to create 1000+ nodes

        async with AsyncClient(app=app, base_url="http://test") as client:
            start_time = time.time()

            response = await client.get(
                "/api/structure_nodes/search",
                params={"q": "machine learning"}
            )

            end_time = time.time()
            duration = end_time - start_time

            assert response.status_code == 200
            assert duration < 1.0, f"Search should complete in <1s, took {duration:.2f}s"

    @pytest.mark.asyncio
    async def test_hierarchy_traversal_performance(self):
        """Test performance of deep hierarchy traversals."""
        # Create deep hierarchy
        # ... setup code

        async with AsyncClient(app=app, base_url="http://test") as client:
            start_time = time.time()

            response = await client.get(f"/api/structure_nodes/{leaf_node_id}/ancestors")

            end_time = time.time()
            duration = end_time - start_time

            assert response.status_code == 200
            assert duration < 0.5, f"Hierarchy traversal should be fast, took {duration:.2f}s"
```

### Database Performance Tests
```python
# test_database_performance.py
import pytest
import time
from sqlalchemy import text

class TestDatabasePerformance:
    def test_index_effectiveness(self, test_session):
        """Test that database indexes are being used effectively."""
        # Test query with EXPLAIN QUERY PLAN
        result = test_session.execute(
            text("EXPLAIN QUERY PLAN SELECT * FROM structure_nodes WHERE node_type = 'domain'")
        )

        plan = str(result.fetchall())
        assert "USING INDEX" in plan, "Query should use index"

    def test_bulk_insert_performance(self, test_session):
        """Test bulk insertion performance."""
        nodes_data = [
            {
                "title": f"Bulk Node {i}",
                "node_type": "domain",
                "description": f"Description {i}"
            }
            for i in range(1000)
        ]

        start_time = time.time()

        # Bulk insert
        test_session.execute(
            text("""
                INSERT INTO structure_nodes (title, node_type, description)
                VALUES (:title, :node_type, :description)
            """),
            nodes_data
        )
        test_session.commit()

        end_time = time.time()
        duration = end_time - start_time

        assert duration < 2.0, f"Bulk insert should be fast, took {duration:.2f}s"
```

## Frontend Testing

### Component Testing with Vitest

#### Test Setup
```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
});

// src/test/setup.ts
import '@testing-library/jest-dom';
import { server } from './mocks/server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

#### Component Tests
```typescript
// StructureNodeForm.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StructureNodeForm } from '../StructureNodeForm';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('StructureNodeForm', () => {
  it('renders form fields correctly', () => {
    render(
      <StructureNodeForm onSubmit={vi.fn()} onCancel={vi.fn()} />,
      { wrapper: TestWrapper }
    );

    expect(screen.getByLabelText('Title')).toBeInTheDocument();
    expect(screen.getByLabelText('Description')).toBeInTheDocument();
    expect(screen.getByLabelText('Node Type')).toBeInTheDocument();
  });

  it('validates required fields', async () => {
    const mockSubmit = vi.fn();

    render(
      <StructureNodeForm onSubmit={mockSubmit} onCancel={vi.fn()} />,
      { wrapper: TestWrapper }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByText('Title is required')).toBeInTheDocument();
    });

    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('submits form with valid data', async () => {
    const mockSubmit = vi.fn();

    render(
      <StructureNodeForm onSubmit={mockSubmit} onCancel={vi.fn()} />,
      { wrapper: TestWrapper }
    );

    fireEvent.change(screen.getByLabelText('Title'), {
      target: { value: 'Test Node' }
    });

    fireEvent.change(screen.getByLabelText('Description'), {
      target: { value: 'Test description' }
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith({
        title: 'Test Node',
        description: 'Test description',
        node_type: 'domain', // default value
      });
    });
  });
});
```

### Mock Service Worker (MSW)

#### API Mocking
```typescript
// src/test/mocks/handlers.ts
import { rest } from 'msw';

export const handlers = [
  // Structure nodes endpoints
  rest.get('/api/structure_nodes', (req, res, ctx) => {
    return res(
      ctx.json({
        nodes: [
          {
            id: '1',
            title: 'Test Layer',
            node_type: 'layer',
            description: 'Test layer description',
          },
          {
            id: '2',
            title: 'Test Domain',
            node_type: 'domain',
            parent_id: '1',
            description: 'Test domain description',
          },
        ],
        total: 2,
        page: 1,
        per_page: 50,
      })
    );
  }),

  rest.post('/api/structure_nodes', (req, res, ctx) => {
    const body = req.body as any;
    return res(
      ctx.status(201),
      ctx.json({
        id: 'new-node-id',
        ...body,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        version: 1,
      })
    );
  }),

  rest.get('/api/structure_nodes/:nodeId', (req, res, ctx) => {
    const { nodeId } = req.params;
    return res(
      ctx.json({
        id: nodeId,
        title: 'Test Node',
        node_type: 'domain',
        description: 'Test node description',
      })
    );
  }),
];

// src/test/mocks/server.ts
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

## Test Data Management

### Test Fixtures
```python
# test_fixtures.py
import pytest
from faker import Faker
from database.models import StructureNode, PipelineFlavor, Identity

fake = Faker()

@pytest.fixture
def sample_layer_data():
    return {
        "title": fake.catch_phrase(),
        "description": fake.text(max_nb_chars=200),
        "node_type": "layer"
    }

@pytest.fixture
def sample_domain_data(sample_layer):
    return {
        "title": fake.bs(),
        "description": fake.text(max_nb_chars=200),
        "node_type": "domain",
        "parent_id": sample_layer.id
    }

@pytest.fixture
def sample_llm_flavor():
    return PipelineFlavor(
        name=fake.slug(),
        description=fake.text(max_nb_chars=100),
        provider="openai",
        model="gpt-3.5-turbo",
        user_prompt_template="Define: {{term}}",
        parameters={"temperature": 0.7, "max_tokens": 500}
    )

class TestDataBuilder:
    """Builder pattern for creating test data."""

    def __init__(self, session):
        self.session = session
        self.fake = Faker()

    def create_hierarchy(self, depth=3, children_per_level=2):
        """Create a test hierarchy of specified depth."""
        layer = self.create_layer()

        if depth > 1:
            for _ in range(children_per_level):
                domain = self.create_domain(parent=layer)

                if depth > 2:
                    for _ in range(children_per_level):
                        self.create_term(parent=domain)

        return layer

    def create_layer(self, **overrides):
        data = {
            "title": self.fake.catch_phrase(),
            "description": self.fake.text(max_nb_chars=200),
            "node_type": "layer",
            **overrides
        }
        return StructureNode(**data)

    def create_domain(self, parent=None, **overrides):
        data = {
            "title": self.fake.bs(),
            "description": self.fake.text(max_nb_chars=200),
            "node_type": "domain",
            "parent_id": parent.id if parent else None,
            **overrides
        }
        return StructureNode(**data)
```

## Continuous Integration

### GitHub Actions Workflow
```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  backend-tests:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        cd local-server
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov

    - name: Run unit tests
      run: |
        cd local-server
        pytest tests/unit_tests -v --cov=. --cov-report=xml

    - name: Run integration tests
      run: |
        cd local-server
        pytest tests/integration_tests -v

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./local-server/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'

    - name: Install dependencies
      run: |
        cd ux
        npm ci

    - name: Run tests
      run: |
        cd ux
        npm run test:coverage

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./ux/coverage/coverage-final.json

  performance-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Run performance tests
      run: |
        cd local-server
        pytest tests/performance_tests -v --benchmark-only
```

## Best Practices

### Test Writing
1. **Follow AAA pattern**: Arrange, Act, Assert
2. **Use descriptive names**: Test names should describe the scenario
3. **Test one thing**: Each test should verify one specific behavior
4. **Use fixtures**: Share setup code through fixtures

### Test Maintenance
1. **Keep tests simple**: Avoid complex logic in tests
2. **Mock external dependencies**: Isolate units under test
3. **Regular cleanup**: Remove obsolete tests
4. **Update with code changes**: Keep tests synchronized with implementation

### Performance Testing
1. **Establish baselines**: Set performance benchmarks
2. **Monitor trends**: Track performance over time
3. **Test realistic scenarios**: Use production-like data volumes
4. **Automate performance tests**: Include in CI/CD pipeline

### Quality Assurance
1. **Code coverage**: Aim for high but meaningful coverage
2. **Review test quality**: Include tests in code reviews
3. **Flaky test management**: Address intermittent failures
4. **Documentation**: Document testing patterns and utilities