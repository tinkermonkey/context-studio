# Scope Pruning: Remove Branch Management System

## Overview

This PRP addresses the removal of unnecessary complexity from the Context Studio application by completely removing the Branch Management System functionality. This includes all code, database tables, API endpoints, and tests related to Git-like branching workflows while preserving the proposal and changeset management capabilities.

## Problem Statement

The application has accumulated unnecessary complexity through the implementation of branch management features that are no longer needed. The requirement is to remove this functionality entirely with no backwards compatibility, simplifying the codebase while retaining proposal and changeset management capabilities for the remote upstream workflow.

## Research Findings

### Codebase Analysis

The branch management system is extensively implemented across multiple layers:

#### Core Files to Remove:
- `api/branch_management.py` - Branch management API endpoints
- `api/models/branch_management.py` - Branch data models  
- `services/branch_manager.py` - Core branch management service
- `services/branch_models.py` - Branch domain models
- `tests/unit_tests/test_branch_manager.py` - Unit tests
- `tests/integration_tests/test_phase4_branch_workflows.py` - Integration tests

#### Database Schema Impact:
From `database/migrations/versions/009_advanced_features.py`:
- `branches` table - Core branch entity storage
- `branch_merge_requests` table - Merge request workflows  
- `user_branch_state` table - User working tree state tracking
- `branch_hierarchy` view - Hierarchical branch relationships
- Multiple indexes supporting branch operations

#### Related Components to Preserve:
Based on analysis of `documentation/requirements/14_change_mgmt/14.8_phase4_advanced_features_design.md`, the following should be retained:
- Proposal management system
- Changeset management
- Conflict resolution engine (non-branch specific parts)
- Version management
- S3 synchronization (non-branch specific)

### External Research: Best Practices

#### Code Cleanup Strategy
According to industry best practices (web.dev, vfunction.com):
- **Consistent naming**: Use "prune" terminology for intentional code removal
- **Separate commits**: Code cleanup should be in separate commits from functional changes
- **Source control safety**: Always ensure code is checked into source control before removal
- **Human review**: Combine automated detection with human verification

#### Database Migration Safety
Based on SQLAlchemy/Alembic best practices:
- **DDL vs DML limitation**: CREATE/DROP TABLE operations (DDL) aren't covered by transaction rollbacks
- **Backup requirement**: Always backup database before applying destructive migrations
- **Test rollbacks**: Thoroughly test downgrade operations in non-production environments
- **Data loss warning**: Dropping tables causes irreversible data loss

## Implementation Blueprint

### Phase 1: Preparation and Backup
```python
# Create database backup before any changes
def create_backup():
    backup_path = f"backups/pre_branch_removal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2("database/context_studio.db", backup_path)
    return backup_path
```

### Phase 2: Database Schema Cleanup
Create new migration to remove branch-related tables:

```python
# Migration: Remove branch management tables
def upgrade():
    # Drop views first (depend on tables)
    connection.execute(text("DROP VIEW IF EXISTS branch_hierarchy"))
    connection.execute(text("DROP VIEW IF EXISTS merge_request_details"))
    
    # Drop tables in reverse dependency order
    connection.execute(text("DROP TABLE IF EXISTS user_branch_state"))
    connection.execute(text("DROP TABLE IF EXISTS branch_merge_requests"))  
    connection.execute(text("DROP TABLE IF EXISTS branches"))

def downgrade():
    # WARNING: This will cause data loss - only for development
    # Recreate tables if needed for rollback
    pass
```

### Phase 3: Code Removal
Remove files in dependency order:
1. Tests first (no dependencies)
2. API endpoints 
3. Service layer
4. Models and utilities

### Phase 4: Integration Cleanup
Remove branch-related:
- Import statements
- Configuration references  
- Documentation updates
- Route registrations

### Phase 5: Validation and Testing
Ensure proposal/changeset functionality remains intact.

## Critical Context for Implementation

### Existing Patterns to Follow

#### Migration Pattern
From `database/migrations/templates/migration_template.py`:
```python
MIGRATION_VERSION = "011"
MIGRATION_DESCRIPTION = "Remove Branch Management System"

def upgrade(connection):
    # Drop operations
    pass
    
def downgrade(connection):  
    # Warning: Data loss operations
    pass
```

#### Service Removal Pattern
Based on existing service architecture, ensure:
- Remove from `services/service_factory.py` registrations
- Update `api/__init__.py` route registrations
- Clean up `config.py` references

### Dependencies to Preserve

From analysis of changeset management design:
- `services/changeset_manager.py` - Keep (core functionality)
- `services/proposal_manager.py` - Keep (voting/approval workflow)
- `services/conflict_resolution_engine.py` - Keep but remove branch-specific methods
- `services/incremental_sync_engine.py` - Keep but remove branch partitioning

### API Endpoints to Remove
All endpoints from `/api/branches/*`:
- `POST /api/branches` - Branch creation
- `GET /api/branches` - Branch listing
- `POST /api/branches/{branch_id}/switch` - Branch switching
- `POST /api/branches/merge-requests` - Merge request creation
- `POST /api/branches/merge-requests/{merge_request_id}/merge` - Branch merging

## Implementation Tasks

### Task 1: Database Migration
- Create migration `011_remove_branch_management.py`
- Drop branch-related tables and views
- Test migration rollback in development
- **Files**: `database/migrations/versions/011_remove_branch_management.py`

### Task 2: Remove Service Layer
- Delete `services/branch_manager.py`
- Delete `services/branch_models.py` 
- Update `services/service_factory.py` to remove registrations
- **Files**: `services/branch_manager.py`, `services/branch_models.py`, `services/service_factory.py`

### Task 3: Remove API Layer
- Delete `api/branch_management.py`
- Delete `api/models/branch_management.py`
- Update `api/__init__.py` to remove route registrations
- **Files**: `api/branch_management.py`, `api/models/branch_management.py`, `api/__init__.py`

### Task 4: Remove Tests
- Delete `tests/unit_tests/test_branch_manager.py`
- Delete `tests/integration_tests/test_phase4_branch_workflows.py`
- **Files**: Test files in `tests/` directory

### Task 5: Clean Dependencies
- Remove branch-related imports from remaining files
- Update configuration files
- Clean up documentation references
- **Files**: Various files with branch imports/references

### Task 6: Update Conflict Resolution
- Remove branch-specific methods from `services/conflict_resolution_engine.py`
- Keep general conflict resolution capabilities
- **Files**: `services/conflict_resolution_engine.py`

### Task 7: Validation
- Run full test suite
- Verify proposal/changeset functionality intact
- Test database migration rollback
- **Validation**: Complete system test

## Error Handling Strategy

### Database Migration Errors
```python
try:
    connection.execute(text("DROP TABLE IF EXISTS branches"))
except Exception as e:
    logger.error(f"Failed to drop branches table: {e}")
    # Don't continue if core table drop fails
    raise
```

### Dependency Reference Errors
- Use comprehensive search to find all branch references
- Test incremental removal in development environment
- Verify no circular dependencies exist

## Risk Mitigation

### Data Loss Prevention
- **Critical**: Create full database backup before migration
- Test migration in development environment first
- Document rollback procedures (though data loss is expected)

### Functionality Preservation
- Isolate proposal/changeset code during testing
- Run comprehensive integration tests
- Verify S3 sync functionality remains intact

## External Resources

### Best Practices Documentation
- **Code Cleanup**: https://web.dev/articles/remove-unused-code
- **Dead Code Detection**: https://vfunction.com/blog/dead-code/
- **Feature Flag Cleanup**: https://www.statsig.com/perspectives/tips-for-unused-feature-flag-clean-up

### Database Migration Safety
- **SQLAlchemy Migration Guide**: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- **Schema Change Best Practices**: https://www.pingcap.com/article/best-practices-alembic-schema-migration/
- **Rollback Considerations**: https://docs.sqlalchemy.org/en/20/orm/session_basics.html

## Validation Gates

### Syntax and Style Check
```bash
# Check Python syntax and style
ruff check --fix .
mypy .
```

### Unit Tests
```bash
# Run unit tests to ensure no broken dependencies
python -m pytest tests/unit_tests/ -v --tb=short
```

### Integration Tests
```bash
# Verify core functionality remains intact
python -m pytest tests/integration_tests/ -v --tb=short -k "not branch"
```

### Database Migration Test
```bash
# Test migration in development
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic upgrade head
```

### API Endpoint Verification
```bash
# Verify branch endpoints are removed and others work
python -c "
import requests
import sys
try:
    response = requests.get('http://localhost:8000/api/branches')
    if response.status_code != 404:
        print('ERROR: Branch endpoints still accessible')
        sys.exit(1)
    else:
        print('SUCCESS: Branch endpoints properly removed')
except requests.exceptions.ConnectionError:
    print('INFO: Server not running, manual verification needed')
"
```

### Full System Test
```bash
# Comprehensive system validation
python -m pytest tests/ -v --tb=short -k "not branch" 
python -m pytest tests/integration_tests/test_proposals.py -v
python -m pytest tests/integration_tests/test_changeset.py -v
```

## Success Criteria

1. **Code Removal**: All branch management files successfully removed
2. **Database Cleanup**: Branch tables dropped without affecting other data
3. **API Verification**: Branch endpoints return 404, other endpoints functional
4. **Test Suite**: All non-branch tests pass
5. **Core Functionality**: Proposal and changeset workflows remain fully functional
6. **Documentation**: Updated to reflect removed functionality

## Confidence Score: 8/10

This PRP provides comprehensive context for successful one-pass implementation because:

✅ **Complete file inventory** with specific paths identified
✅ **Database schema understanding** from migration analysis  
✅ **External best practices** integrated from industry sources
✅ **Executable validation gates** provided for each phase
✅ **Risk mitigation strategies** for data loss prevention
✅ **Dependency preservation** clearly documented
✅ **Implementation task breakdown** in logical order

**Confidence reduced by**: Complexity of ensuring all branch references are found and the inherent risk of data loss in production environments.

## Post-Implementation Notes

After successful removal:
- Update system documentation to reflect simplified architecture
- Consider creating a brief migration guide for users
- Monitor system performance improvements from reduced complexity
- Archive branch-related documentation for historical reference