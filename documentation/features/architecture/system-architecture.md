# System Architecture

## Overview

Context Studio is designed as a local-first knowledge graph management platform with a Python FastAPI backend, React TypeScript frontend, and SQLite database with vector extensions. The architecture supports multi-dataset management, advanced collaboration workflows, and integration with external AI services.

## High-Level Architecture

```mermaid
graph TB
    subgraph "Desktop Application (Planned)"
        T[Tauri Wrapper]
    end

    subgraph "Frontend Layer"
        F[React TypeScript App]
        R[TanStack Router]
        Q[TanStack Query]
        C[Generated API Client]
    end

    subgraph "Backend Layer"
        A[FastAPI Application]
        S[Service Layer]
        M[Data Models]
    end

    subgraph "Data Layer"
        D[SQLite Database]
        V[sqlite-vec Extension]
        P[Dataset Files]
    end

    subgraph "External Services"
        L[LLM Providers]
        N[NLP Services]
        E[Enrichment APIs]
    end

    T --> F
    F --> R
    F --> Q
    Q --> C
    C --> A
    A --> S
    S --> M
    M --> D
    D --> V
    A --> P
    A --> L
    A --> N
    A --> E
```

## Component Architecture

### Backend Components

```mermaid
graph TD
    subgraph "API Layer"
        API[FastAPI Routes]
        DEP[Dependencies]
        MOD[Pydantic Models]
    end

    subgraph "Service Layer"
        NS[Node Service]
        DS[Dataset Manager]
        LS[LLM Service]
        NLP[NLP Pipeline]
        VS[Version Manager]
        CS[Changeset Manager]
    end

    subgraph "Data Layer"
        DB[Database Manager]
        MIG[Migration Manager]
        VEC[Vector Service]
    end

    subgraph "External Integration"
        PROV[LLM Providers]
        EXT[External APIs]
        PROX[Proxy Manager]
    end

    API --> DEP
    DEP --> NS
    DEP --> DS
    DEP --> LS
    DEP --> NLP
    DEP --> VS
    DEP --> CS

    NS --> DB
    DS --> DB
    VS --> DB
    CS --> DB

    LS --> PROV
    NLP --> EXT
    EXT --> PROX

    DB --> VEC
    DB --> MIG
```

### Frontend Components

```mermaid
graph TD
    subgraph "Application Shell"
        SHELL[App Component]
        LAYOUT[Layout Components]
        NAV[Navigation]
    end

    subgraph "Feature Components"
        KG[Knowledge Graph UI]
        DSET[Dataset Management]
        LLM[LLM Pipeline UI]
        NLP_UI[NLP Analysis UI]
        TRACE[Traceability UI]
    end

    subgraph "Shared Components"
        FORMS[Form Components]
        TABLES[Data Tables]
        GRAPHS[Graph Visualization]
        MODALS[Modal Components]
    end

    subgraph "State Management"
        QUERY[TanStack Query]
        HOOKS[Custom Hooks]
        CONTEXT[React Context]
    end

    SHELL --> LAYOUT
    LAYOUT --> NAV
    LAYOUT --> KG
    LAYOUT --> DSET
    LAYOUT --> LLM
    LAYOUT --> NLP_UI
    LAYOUT --> TRACE

    KG --> FORMS
    KG --> TABLES
    KG --> GRAPHS
    DSET --> FORMS
    LLM --> FORMS
    NLP_UI --> MODALS

    FORMS --> HOOKS
    TABLES --> HOOKS
    GRAPHS --> HOOKS
    HOOKS --> QUERY
    HOOKS --> CONTEXT
```

## Data Flow Architecture

### Request/Response Flow

```mermaid
sequenceDiagram
    participant UI as Frontend UI
    participant API as FastAPI
    participant SVC as Service Layer
    participant DB as SQLite DB
    participant EXT as External APIs

    UI->>+API: HTTP Request
    API->>+SVC: Service Method Call
    SVC->>+DB: Database Query
    DB-->>-SVC: Query Result

    alt External Service Needed
        SVC->>+EXT: External API Call
        EXT-->>-SVC: External Response
    end

    SVC-->>-API: Service Response
    API-->>-UI: HTTP Response
```

### Change Event Flow

```mermaid
sequenceDiagram
    participant UI as User Action
    participant API as API Endpoint
    participant SVC as Service Layer
    participant EVT as Event System
    participant PROC as Event Processor
    participant DB as Database

    UI->>+API: Modify Entity
    API->>+SVC: Service Call
    SVC->>+DB: Update Entity
    DB-->>-SVC: Update Result
    SVC->>+EVT: Generate Change Event
    EVT->>+PROC: Queue Event
    PROC->>+DB: Process Event
    DB-->>-PROC: Processing Result
    PROC-->>-EVT: Event Processed
    EVT-->>-SVC: Event Confirmation
    SVC-->>-API: Service Response
    API-->>-UI: Response
```

## Technology Stack

### Backend Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | FastAPI | REST API server with automatic OpenAPI |
| Database | SQLite | Local-first data storage |
| Vector Database | sqlite-vec | Vector embeddings and similarity search |
| ORM | SQLAlchemy | Database abstraction and migrations |
| Async Support | asyncio | Asynchronous request handling |
| Validation | Pydantic | Data validation and serialization |
| Testing | pytest | Unit and integration testing |

### Frontend Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | React 18 | User interface library |
| Language | TypeScript | Type safety and development experience |
| Build Tool | Vite | Fast development and building |
| Routing | TanStack Router | Type-safe routing with search params |
| State Management | TanStack Query | Server state management and caching |
| UI Components | Flowbite-React | Tailwind CSS component library |
| Styling | Tailwind CSS | Utility-first CSS framework |
| Testing | Vitest + Testing Library | Component and integration testing |

### Development Tools

| Tool | Purpose |
|------|---------|
| Poetry | Python dependency management |
| npm | Node.js package management |
| ESLint | JavaScript/TypeScript linting |
| Prettier | Code formatting |
| Black | Python code formatting |
| mypy | Python type checking |

## Deployment Architecture

### Local Development

```mermaid
graph LR
    subgraph "Development Environment"
        DEV[Developer Machine]

        subgraph "Backend"
            FAST[FastAPI Server :8000]
            SQLITE[SQLite Files]
        end

        subgraph "Frontend"
            VITE[Vite Dev Server :5173]
        end

        subgraph "External Services"
            OPENAI[OpenAI API]
            ANTH[Anthropic API]
            DBP[DBpedia Spotlight]
        end
    end

    DEV --> FAST
    DEV --> VITE
    VITE --> FAST
    FAST --> SQLITE
    FAST --> OPENAI
    FAST --> ANTH
    FAST --> DBP
```

### Production Deployment (Planned)

```mermaid
graph TB
    subgraph "Desktop Application"
        TAURI[Tauri App]

        subgraph "Bundled Backend"
            API[FastAPI Server]
            DB[Local SQLite]
        end

        subgraph "Bundled Frontend"
            UI[React App]
        end
    end

    subgraph "External Services"
        LLM[LLM Providers]
        NLP[NLP Services]
    end

    TAURI --> API
    TAURI --> UI
    UI --> API
    API --> DB
    API --> LLM
    API --> NLP
```

## Security Architecture

### Data Security

- **Local-first**: All sensitive data stored locally
- **No cloud dependencies**: Core functionality works offline
- **API key management**: Secure storage of external service credentials
- **Database encryption**: Optional SQLite encryption support

### API Security

- **Input validation**: Comprehensive request validation with Pydantic
- **Error handling**: Sanitized error responses
- **Rate limiting**: Configurable request rate limits
- **CORS configuration**: Restricted cross-origin access

### Authentication (Future)

```mermaid
graph TD
    subgraph "Authentication Flow"
        LOGIN[Login Request]
        AUTH[Auth Provider]
        TOKEN[JWT Token]
        API[API Access]
    end

    LOGIN --> AUTH
    AUTH --> TOKEN
    TOKEN --> API
```

## Scalability Considerations

### Current Scale

- **Target**: Single user workstation
- **Dataset size**: Up to 1GB per dataset
- **Concurrent users**: 1 (local-first)
- **API throughput**: 100-1000 requests/minute

### Future Scale (Enterprise)

- **Multi-tenant**: Organization-level isolation
- **Distributed storage**: Remote sync capabilities
- **Load balancing**: Multiple API instances
- **Caching layers**: Redis for shared caching

## Integration Points

### External Service Integration

```mermaid
graph TD
    subgraph "Context Studio"
        CORE[Core System]
        PROXY[Proxy Manager]
        CACHE[Response Cache]
    end

    subgraph "AI Services"
        OPENAI[OpenAI]
        ANTHROPIC[Anthropic]
        HUGGING[HuggingFace]
    end

    subgraph "NLP Services"
        DBPEDIA[DBpedia Spotlight]
        CONCEPTNET[ConceptNet]
        WIKIDATA[Wikidata]
    end

    CORE --> PROXY
    PROXY --> CACHE
    PROXY --> OPENAI
    PROXY --> ANTHROPIC
    PROXY --> HUGGING
    PROXY --> DBPEDIA
    PROXY --> CONCEPTNET
    PROXY --> WIKIDATA
```

### Future Integrations (Planned)

- **MCP Server**: Model Context Protocol integration
- **Business Chat**: Slack, Teams, Discord connectors
- **Browser Extension**: Web content integration
- **Mobile Apps**: iOS and Android companion apps

## Performance Architecture

### Caching Strategy

```mermaid
graph TD
    subgraph "Caching Layers"
        L1[Frontend Cache<br/>TanStack Query]
        L2[API Response Cache<br/>Memory/Redis]
        L3[Database Query Cache<br/>SQLite]
        L4[External API Cache<br/>Proxy Manager]
    end

    L1 --> L2
    L2 --> L3
    L2 --> L4
```

### Database Optimization

- **Indexing strategy**: Comprehensive indexes for query patterns
- **Query optimization**: Analyzed and optimized query plans
- **Connection pooling**: Efficient database connection management
- **Vector indexing**: Optimized similarity search with sqlite-vec

### Async Architecture

- **Non-blocking I/O**: Async/await throughout the stack
- **Background processing**: Event processing in background tasks
- **Streaming responses**: Real-time data streaming for LLM responses
- **Parallel processing**: Concurrent external API calls

## Monitoring and Observability

### Metrics Collection

- **Application metrics**: Request rates, response times, error rates
- **Database metrics**: Query performance, connection pool usage
- **External service metrics**: API response times, success rates
- **Resource metrics**: CPU, memory, disk usage

### Logging Strategy

- **Structured logging**: JSON-formatted logs with context
- **Log levels**: Configurable verbosity levels
- **Request tracing**: Request ID tracking across components
- **Error tracking**: Comprehensive error logging and alerting

### Health Checks

- **Service health**: Individual component health monitoring
- **Dependency health**: External service availability
- **Database health**: Connection and performance checks
- **Overall system health**: Aggregated health status

## Development and Testing Architecture

### Testing Strategy

```mermaid
graph TD
    subgraph "Testing Pyramid"
        E2E[E2E Tests<br/>Playwright]
        INT[Integration Tests<br/>pytest + MSW]
        UNIT[Unit Tests<br/>pytest + Vitest]
    end

    subgraph "Test Infrastructure"
        MOCK[Mock Services]
        FIXTURES[Test Fixtures]
        DB[Test Databases]
    end

    E2E --> INT
    INT --> UNIT

    INT --> MOCK
    INT --> FIXTURES
    UNIT --> DB
```

### CI/CD Pipeline

```mermaid
graph LR
    CODE[Code Commit] --> LINT[Linting & Formatting]
    LINT --> UNIT[Unit Tests]
    UNIT --> INT[Integration Tests]
    INT --> PERF[Performance Tests]
    PERF --> BUILD[Build Artifacts]
    BUILD --> DEPLOY[Deploy/Package]
```

## Future Architecture Evolution

### Phase 1: Desktop Application
- Tauri wrapper for native desktop experience
- Offline-first capabilities
- Local file system integration

### Phase 2: Collaboration Features
- Real-time collaboration
- Conflict resolution improvements
- Advanced version control

### Phase 3: Enterprise Features
- Multi-tenant architecture
- Advanced security and compliance
- Scalable deployment options

### Phase 4: Ecosystem Integration
- MCP server implementation
- Business chat platform integration
- Browser extension and mobile apps