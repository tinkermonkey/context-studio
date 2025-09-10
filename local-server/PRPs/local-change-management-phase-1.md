# Local Change Management System - Phase 1 Product Requirement Prompt (PRP)

## Executive Summary

Implement a comprehensive local change management system for Context Studio that provides entity versioning, working tree state management, diff generation, and rollback capabilities. This system will integrate seamlessly with the existing ChangeEvent infrastructure and support the core entities (StructureNode and StructureNodeLink) used throughout the application.

## Context & Existing System Analysis

### Current Architecture

The Context Studio local server is built using:
- **Language**: Python with FastAPI
- **Database**: SQLite with SQLAlchemy 2.0
- **Testing**: pytest with comprehensive fixtures
- **Migration System**: Custom MigrationManager class

### Existing Data Models

The system currently manages two primary entities that require versioning:

```python
# From database/models.py
class StructureNode(Base):
    """Unified structure_node table for layers, domains, and terms."""
    __tablename__ = "structure_nodes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_type = Column(NodeTypeColumn(), nullable=False)
    parent_node_id = Column(String, ForeignKey("structure_nodes.id"), nullable=True)
    title = Column(String, nullable=False)
    definition = Column(Text, nullable=True)
    structural_predicate_id = Column(String, ForeignKey("predicates.id"), nullable=True)
    version = Column(Integer, default=1)  # Existing version field
    last_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StructureNodeLink(Base):
    """Unified links table for all structure_node relationships."""
    __tablename__ = "structure_node_links"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_node_id = Column(String, ForeignKey("structure_nodes.id"), nullable=False)
    target_node_id = Column(String, ForeignKey("structure_nodes.id"), nullable=False)
    predicate = Column(String, nullable=False)
    predicate_id = Column(String, ForeignKey("predicates.id"), nullable=True)
```

### Existing ChangeEvent System

The system already has a robust event processing system:

```python
# From database/models.py
class ChangeEvent(Base):
    """Unified events table for all change events across record types."""
    __tablename__ = "change_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)  # create, update, delete
    record_type = Column(RecordTypeColumn(), nullable=False)
    record_id = Column(String, nullable=True)
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
```

The EventProcessor (utils/event_processor.py) already handles these events with methods:
- `process_structure_node_event()`
- `process_structure_node_link_event()`

### API Patterns

Current API endpoints follow consistent patterns:

```python
# From api/structure_nodes.py
@router.post("/", response_model=NodeOut, status_code=201)
def create_node(structure_node: NodeCreate, node_service: NodeService = Depends(get_node_service)):
    # Standard create pattern with service layer

@router.put("/{node_id}", response_model=NodeOut)  
def update_node(node_id: UUID, node_update: NodeUpdate, node_service: NodeService = Depends(get_node_service)):
    # Standard update pattern with UUID path params

@router.delete("/{node_id}", status_code=204)
def delete_node(node_id: UUID, node_service: NodeService = Depends(get_node_service)):
    # Standard delete pattern
```

### Testing Infrastructure

The system uses pytest with comprehensive fixtures in tests/conftest.py:
- `db_session`: Database session fixture
- `test_app`: FastAPI test application
- `client`: Test client for API testing

## External Research & Best Practices

### Recommended Libraries

Based on 2024 research:

1. **DeepDiff** for JSON comparison:
   ```bash
   pip install deepdiff
   ```
   - Most comprehensive JSON diffing library
   - Handles complex nested structures
   - Categorizes differences (added, removed, changed)
   - 100% test coverage

2. **SQLite Versioning Best Practices**:
   - Use PRAGMA user_version for schema versioning
   - Implement migration-based version control
   - Transaction safety for all schema changes
   - Reference: https://www.sqliteforum.com/p/managing-database-versions-and-migrations

3. **FastAPI + SQLAlchemy 2.0 Patterns**:
   - Async support for better performance
   - Dependency injection for session management
   - Transactional decorators for data integrity
   - Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/

## Technical Requirements

### Database Schema Extensions

#### 1. Entity Versions Table

```sql
CREATE TABLE entity_versions (
    id TEXT PRIMARY KEY,                    -- UUID as TEXT
    entity_type TEXT NOT NULL CHECK (entity_type IN ('structure_node', 'structure_node_link')),
    entity_id TEXT NOT NULL,               -- References structure_nodes.id or structure_node_links.id  
    version_number INTEGER NOT NULL,       -- Incremental version counter
    content TEXT NOT NULL,                 -- Full entity snapshot as JSON
    state TEXT NOT NULL CHECK (state IN ('WORKING', 'STAGED', 'PROPOSED', 'APPROVED', 'MERGED', 'REJECTED')),
    parent_version_id TEXT,                -- References entity_versions.id
    changeset_id TEXT,                     -- Future use, nullable for now
    author_id TEXT NOT NULL,               -- User identifier
    created_at TEXT NOT NULL,              -- ISO timestamp
    metadata TEXT,                         -- Additional metadata as JSON
    
    FOREIGN KEY (parent_version_id) REFERENCES entity_versions(id),
    UNIQUE(entity_type, entity_id, version_number)
);

CREATE INDEX idx_entity_versions_entity ON entity_versions(entity_type, entity_id);
CREATE INDEX idx_entity_versions_state ON entity_versions(state);
CREATE INDEX idx_entity_versions_created ON entity_versions(created_at);
```

#### 2. Working Tree State Table

```sql
CREATE TABLE working_tree (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    current_version_id TEXT NOT NULL,      -- Current working version
    canonical_version_id TEXT NOT NULL,    -- Last committed/merged version
    staged BOOLEAN DEFAULT FALSE,          -- Whether changes are staged
    modified_at TEXT NOT NULL,             -- Last modification timestamp
    
    PRIMARY KEY (entity_type, entity_id),
    FOREIGN KEY (current_version_id) REFERENCES entity_versions(id),
    FOREIGN KEY (canonical_version_id) REFERENCES entity_versions(id)
);

CREATE INDEX idx_working_tree_staged ON working_tree(staged);
CREATE INDEX idx_working_tree_modified ON working_tree(modified_at);
```

#### 3. ChangeEvent Integration

```sql
-- Extend existing change_events table
ALTER TABLE change_events ADD COLUMN version_id TEXT;
ALTER TABLE change_events ADD COLUMN change_state TEXT CHECK (change_state IN ('WORKING', 'STAGED', 'PROPOSED', 'APPROVED', 'MERGED', 'REJECTED'));

CREATE INDEX idx_change_events_version ON change_events(version_id);
CREATE INDEX idx_change_events_state ON change_events(change_state);
```

### Core Service Classes

#### 1. Version Manager Service

```python
# services/version_manager.py
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import uuid
from deepdiff import DeepDiff

class ChangeState(Enum):
    WORKING = "WORKING"
    STAGED = "STAGED" 
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    MERGED = "MERGED"
    REJECTED = "REJECTED"

@dataclass
class EntityVersion:
    id: str
    entity_type: str
    entity_id: str
    version_number: int
    content: Dict[str, Any]
    state: ChangeState
    parent_version_id: Optional[str]
    changeset_id: Optional[str]
    author_id: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None

class VersionManager:
    """Manages entity versioning with SQLite storage."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def create_version(self, entity_type: str, entity_id: str, content: Dict[str, Any], 
                      author_id: str, state: ChangeState = ChangeState.WORKING) -> EntityVersion:
        """Create a new version of an entity."""
        
    def get_entity_versions(self, entity_type: str, entity_id: str) -> List[EntityVersion]:
        """Get all versions of an entity ordered by version number."""
        
    def get_current_version(self, entity_type: str, entity_id: str) -> Optional[EntityVersion]:
        """Get the current working version of an entity."""
        
    def rollback_to_version(self, entity_type: str, entity_id: str, 
                           version_number: int, author_id: str) -> EntityVersion:
        """Rollback entity to a specific version."""
```

#### 2. Working Tree Manager

```python
# services/working_tree_manager.py
@dataclass
class WorkingTreeEntry:
    entity_type: str
    entity_id: str
    current_version_id: str
    canonical_version_id: str
    staged: bool
    modified_at: datetime

class WorkingTreeManager:
    """Manages working tree state and staging operations."""
    
    def __init__(self, db_session, version_manager: VersionManager):
        self.db = db_session
        self.version_manager = version_manager
    
    def get_working_changes(self) -> List[WorkingTreeEntry]:
        """Get all entities with working changes."""
        
    def stage_entity(self, entity_type: str, entity_id: str) -> bool:
        """Stage an entity for commit."""
        
    def generate_working_diff(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Generate diff between working and canonical versions using DeepDiff."""
```

#### 3. Diff Generator Service

```python
# services/diff_generator.py
from deepdiff import DeepDiff

@dataclass
class EntityDiff:
    entity_type: str
    entity_id: str
    before_version: Optional[EntityVersion]
    after_version: EntityVersion
    changes: Dict[str, Any]  # DeepDiff result
    
class DiffGenerator:
    """Generates diffs between entity versions using DeepDiff."""
    
    def generate_diff(self, before_content: Dict[str, Any], 
                     after_content: Dict[str, Any]) -> Dict[str, Any]:
        """Generate structured diff using DeepDiff."""
        return DeepDiff(before_content, after_content, ignore_order=True)
```

### API Endpoints

Following existing patterns from api/structure_nodes.py:

#### Version Management Endpoints

```python
# api/version_management.py
from fastapi import APIRouter, Depends, HTTPException, Path
from uuid import UUID
from typing import List

router = APIRouter(prefix="/api/versions", tags=["version_management"])

@router.get("/entities/{entity_type}/{entity_id}/versions", response_model=List[EntityVersionOut])
def get_entity_versions(
    entity_type: str = Path(..., description="Entity type (structure_node, structure_node_link)"),
    entity_id: UUID = Path(..., description="Entity ID"),
    version_service: VersionManager = Depends(get_version_manager)
):
    """Get version history for an entity."""

@router.get("/entities/{entity_type}/{entity_id}/versions/{version_number}", response_model=EntityVersionOut)
def get_entity_version(
    entity_type: str, entity_id: UUID, version_number: int,
    version_service: VersionManager = Depends(get_version_manager)
):
    """Get specific version of an entity."""

@router.get("/entities/{entity_type}/{entity_id}/diff")
def get_working_diff(
    entity_type: str, entity_id: UUID,
    diff_service: DiffGenerator = Depends(get_diff_generator)
):
    """Get diff between working and canonical versions."""

@router.post("/entities/{entity_type}/{entity_id}/rollback", response_model=EntityVersionOut)
def rollback_entity(
    entity_type: str, entity_id: UUID,
    rollback_request: RollbackRequest,
    version_service: VersionManager = Depends(get_version_manager)
):
    """Rollback entity to specific version."""
```

### Integration with Existing EventProcessor

Extend the existing EventProcessor in utils/event_processor.py:

```python
# utils/event_processor.py (modifications)
class EventProcessor:
    def __init__(self, database_url: str, poll_interval: float = 1.0, max_events: int = 100):
        # ... existing initialization ...
        self.version_manager = None  # Will be injected
        
    def process_structure_node_event(self, event):
        """Enhanced to create versions on entity changes."""
        # Create version when entity is modified
        if self.version_manager and event.operation in ['create', 'update']:
            content = event.new_data or event.old_data
            self.version_manager.create_version(
                entity_type='structure_node',
                entity_id=event.record_id,
                content=content,
                author_id='system'
            )
        
        # Call existing logic
        self.logger.info(f"Processing structure_node event: {event.operation} id={event.id}")
```

## Implementation Blueprint

### Phase 1: Database Schema and Migration

1. **Create Migration Script**: `database/migrations/versions/007_change_management.py`
   - Add entity_versions table
   - Add working_tree table  
   - Extend change_events table
   - Create all necessary indexes

2. **Update Migration Manager**: Ensure compatibility with existing system

### Phase 2: Core Services Implementation

1. **Implement VersionManager**: Core versioning logic with SQLite operations
2. **Implement WorkingTreeManager**: State tracking and staging operations
3. **Implement DiffGenerator**: Using DeepDiff for JSON comparison
4. **Create Service Dependencies**: Following existing dependency injection patterns

### Phase 3: EventProcessor Integration

1. **Extend EventProcessor**: Add version creation on entity changes
2. **Update ChangeEvent Handlers**: Link events to versions
3. **Test Integration**: Ensure seamless event processing

### Phase 4: API Implementation

1. **Create Version Management Endpoints**: Following existing API patterns
2. **Create Working Tree Endpoints**: For staging/unstaging operations
3. **Add Pydantic Models**: Request/response schemas
4. **Implement Error Handling**: Consistent with existing patterns

### Phase 5: Testing and Validation

1. **Unit Tests**: All core service classes
2. **Integration Tests**: End-to-end API functionality
3. **Performance Tests**: Version operations under load
4. **Migration Testing**: Schema changes with existing data

## Validation Gates (Must Pass)

Execute these commands to validate implementation:

```bash
# 1. Syntax and Style Check
source .venv/bin/activate && python -m ruff check --fix . && python -m mypy .

# 2. Database Migration Test
python database/migrations/migration_manager.py up

# 3. Unit Tests
python -m pytest tests/unit_tests/test_version_manager.py -v
python -m pytest tests/unit_tests/test_working_tree_manager.py -v  
python -m pytest tests/unit_tests/test_diff_generator.py -v

# 4. Integration Tests
python -m pytest tests/integration_tests/test_change_management_integration.py -v

# 5. API Tests
python -m pytest tests/integration_tests/test_version_api_integration.py -v

# 6. Performance Tests
python -m pytest tests/performance_tests/test_version_performance.py -v

# 7. Full Test Suite
python -m pytest tests/ -v --tb=short
```

## Task Implementation Order

Execute these tasks in order for successful implementation:

### Task 1: Database Foundation
- Create migration script 007_change_management.py
- Implement entity_versions, working_tree tables
- Extend change_events table
- Test migration up/down

### Task 2: Core Services
- Implement VersionManager class with CRUD operations
- Implement WorkingTreeManager for state management
- Implement DiffGenerator using DeepDiff
- Create service factory dependencies

### Task 3: EventProcessor Integration  
- Extend EventProcessor to create versions on changes
- Link ChangeEvents to entity_versions
- Test event processing with version creation

### Task 4: API Layer
- Create version management API endpoints
- Create working tree API endpoints  
- Implement Pydantic request/response models
- Add comprehensive error handling

### Task 5: Testing Suite
- Write unit tests for all core classes
- Write integration tests for API endpoints
- Write performance tests for version operations
- Ensure 100% test coverage for critical paths

### Task 6: Documentation and Cleanup
- Update API documentation
- Add inline code documentation
- Create usage examples
- Final validation and testing

## Code Quality Requirements

### Following Existing Patterns

1. **Database Models**: Follow existing SQLAlchemy patterns in database/models.py
2. **API Structure**: Mirror patterns from api/structure_nodes.py
3. **Service Layer**: Follow dependency injection patterns
4. **Testing**: Use existing fixtures from tests/conftest.py
5. **Error Handling**: Consistent with existing HTTPException patterns

### Performance Considerations

1. **Batch Operations**: Use SQLAlchemy bulk operations where possible
2. **Indexing**: Proper database indexes for query performance
3. **Memory Management**: Stream large result sets, avoid loading all versions
4. **Connection Pooling**: Reuse existing database connection patterns

### Security Considerations

1. **Input Validation**: Use Pydantic models for all API inputs
2. **SQL Injection**: Use parameterized queries only
3. **Access Control**: Implement proper author_id validation
4. **Data Integrity**: Use database transactions for multi-table operations

## External Documentation References

### Core Libraries
- **DeepDiff Documentation**: https://deepdiff.readthedocs.io/
- **FastAPI SQL Tutorial**: https://fastapi.tiangolo.com/tutorial/sql-databases/
- **SQLAlchemy 2.0 Migration Guide**: https://docs.sqlalchemy.org/en/20/changelog/migration_20.html

### Best Practices
- **SQLite Versioning**: https://www.sqliteforum.com/p/managing-database-versions-and-migrations
- **Database Version Control**: https://enterprisecraftsmanship.com/posts/database-versioning-best-practices/
- **FastAPI Best Practices**: https://github.com/zhanymkanov/fastapi-best-practices

## Success Criteria

### Functional Requirements
- ✅ All entity modifications create versions automatically
- ✅ Version history accessible via API
- ✅ Working tree state correctly tracked
- ✅ Staging/unstaging operations work correctly
- ✅ Diff generation between any two versions
- ✅ Rollback functionality restores entities correctly
- ✅ Integration with existing ChangeEvent system seamless

### Performance Requirements
- ✅ Version creation < 50ms per entity
- ✅ Version history queries < 200ms
- ✅ Diff generation < 100ms for typical entities
- ✅ Support 1000+ versions per entity
- ✅ Migration completes without data loss

### Quality Requirements
- ✅ 100% test coverage for core functionality
- ✅ All validation gates pass
- ✅ No breaking changes to existing APIs
- ✅ Consistent error handling and logging
- ✅ Comprehensive API documentation

## Quality Score

**Confidence Level: 9/10** - One-pass implementation success expected

**Rationale:**
- Comprehensive context provided about existing system
- Real code examples from codebase included
- External research validates technical approach
- Clear implementation order with validation gates
- Follows established patterns and conventions
- Executable validation commands provided
- Detailed task breakdown with dependencies mapped

**Risk Mitigation:**
- DeepDiff library well-documented and stable
- SQLite versioning patterns are proven
- EventProcessor integration builds on existing system
- Migration strategy maintains backward compatibility
- Comprehensive testing strategy reduces integration risk