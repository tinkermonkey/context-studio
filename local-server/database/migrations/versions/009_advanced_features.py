"""
Migration 009: Add Advanced Features - Branch Management, Conflict Resolution, and Analytics  # noqa: E501

This migration adds tables for Phase 4 advanced features including:
- Branch management with Git-like workflows
- Advanced conflict resolution system
- Incremental sync operation tracking
- Analytics and reporting support

Tables added:
- branches: Branch management with hierarchical structure
- branch_merge_requests: Merge request workflows with conflict tracking
- conflict_descriptors: Advanced conflict detection and resolution
- sync_operations: Incremental sync operation history
"""

from sqlalchemy import text
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

MIGRATION_VERSION = 9
MIGRATION_DESCRIPTION = "Add Advanced Features - Branch Management, Conflict Resolution, and Analytics"  # noqa: E501


def upgrade(connection):
    """Apply migration 009 - add advanced features tables."""
    logger.info(f"Applying migration {MIGRATION_VERSION}: {MIGRATION_DESCRIPTION}")  # noqa: E501

    try:
        # Enable foreign keys
        connection.execute(text("PRAGMA foreign_keys = ON"))

        # 1. Branches table for Git-like branch management
        connection.execute(text("""
        CREATE TABLE branches (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            branch_type TEXT NOT NULL CHECK (branch_type IN ('main', 'feature', 'release', 'hotfix')),  # noqa: E501
            base_branch_id TEXT,
            head_changeset_id TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            description TEXT,
            protected INTEGER DEFAULT 0 CHECK (protected IN (0, 1)),
            metadata TEXT,  -- JSON metadata
            FOREIGN KEY (base_branch_id) REFERENCES branches(id) ON DELETE SET NULL,  # noqa: E501
            FOREIGN KEY (head_changeset_id) REFERENCES changesets(id) ON DELETE SET NULL  # noqa: E501
        )
        """))

        # Index for efficient branch queries
        connection.execute(text("""
        CREATE INDEX idx_branches_type_created ON branches(branch_type, created_at DESC)  # noqa: E501
        """))

        connection.execute(text("""
        CREATE INDEX idx_branches_created_by ON branches(created_by, created_at DESC)  # noqa: E501
        """))

        connection.execute(text("""
        CREATE INDEX idx_branches_base_branch ON branches(base_branch_id)
        """))

        # 2. Branch merge requests table
        connection.execute(text("""
        CREATE TABLE branch_merge_requests (
            id TEXT PRIMARY KEY,
            source_branch_id TEXT NOT NULL,
            target_branch_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_by TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('open', 'approved', 'merged', 'closed', 'conflicts')),  # noqa: E501
            conflicts TEXT,  -- JSON array of conflicts
            created_at TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT,
            merged_at TEXT,
            merged_by TEXT,
            metadata TEXT,  -- JSON metadata
            FOREIGN KEY (source_branch_id) REFERENCES branches(id) ON DELETE CASCADE,  # noqa: E501
            FOREIGN KEY (target_branch_id) REFERENCES branches(id) ON DELETE CASCADE  # noqa: E501
        )
        """))

        # Indexes for merge request queries
        connection.execute(text("""
        CREATE INDEX idx_merge_requests_status ON branch_merge_requests(status, created_at DESC)  # noqa: E501
        """))

        connection.execute(text("""
        CREATE INDEX idx_merge_requests_created_by ON branch_merge_requests(created_by, created_at DESC)  # noqa: E501
        """))

        connection.execute(text("""
        CREATE INDEX idx_merge_requests_branches ON branch_merge_requests(source_branch_id, target_branch_id)  # noqa: E501
        """))

        # 3. Conflict descriptors table for advanced conflict resolution
        connection.execute(text("""
        CREATE TABLE conflict_descriptors (
            conflict_id TEXT PRIMARY KEY,
            conflict_type TEXT NOT NULL CHECK (conflict_type IN ('concurrent_modification', 'structural_conflict', 'dependency_conflict', 'semantic_conflict')),  # noqa: E501
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            local_version_id TEXT NOT NULL,
            remote_version_id TEXT NOT NULL,
            conflict_details TEXT,  -- JSON object with conflict specifics
            resolution_suggestions TEXT,  -- JSON array of suggestions
            severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),  # noqa: E501
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by TEXT,
            resolution_choice TEXT,  -- JSON object describing resolution
            FOREIGN KEY (local_version_id) REFERENCES entity_versions(id) ON DELETE CASCADE,  # noqa: E501
            FOREIGN KEY (remote_version_id) REFERENCES entity_versions(id) ON DELETE CASCADE  # noqa: E501
        )
        """))

        # Indexes for conflict resolution queries
        connection.execute(text("""
        CREATE INDEX idx_conflicts_entity ON conflict_descriptors(entity_type, entity_id)  # noqa: E501
        """))

        connection.execute(text("""
        CREATE INDEX idx_conflicts_severity ON conflict_descriptors(severity, created_at DESC)  # noqa: E501
        """))

        connection.execute(text("""
        CREATE INDEX idx_conflicts_resolution ON conflict_descriptors(resolved_at, resolved_by)  # noqa: E501
        """))

        # 4. Sync operations table for incremental sync tracking
        connection.execute(text("""
        CREATE TABLE sync_operations (
            id TEXT PRIMARY KEY,
            sync_type TEXT NOT NULL CHECK (sync_type IN ('incremental', 'full', 'partial')),  # noqa: E501
            started_at TEXT NOT NULL,
            completed_at TEXT,
            since_timestamp TEXT NOT NULL,
            until_timestamp TEXT,
            entity_types TEXT,  -- JSON array of entity types to sync
            synced_changes INTEGER DEFAULT 0,
            new_entities INTEGER DEFAULT 0,
            updated_entities INTEGER DEFAULT 0,
            errors TEXT,  -- JSON array of error details
            metadata TEXT  -- JSON metadata
        )
        """))

        # Indexes for sync operation queries
        connection.execute(text("""
        CREATE INDEX idx_sync_operations_type ON sync_operations(sync_type, started_at DESC)  # noqa: E501
        """))

        connection.execute(text("""
        CREATE INDEX idx_sync_operations_timestamp ON sync_operations(since_timestamp, until_timestamp)  # noqa: E501
        """))

        connection.execute(text("""
        CREATE INDEX idx_sync_operations_completed ON sync_operations(completed_at)  # noqa: E501
        """))

        # 5. Branch current state tracking table (for user working tree state)
        connection.execute(text("""
        CREATE TABLE user_branch_state (
            user_id TEXT NOT NULL,
            current_branch_id TEXT,
            switched_at TEXT NOT NULL,
            PRIMARY KEY (user_id),
            FOREIGN KEY (current_branch_id) REFERENCES branches(id) ON DELETE SET NULL  # noqa: E501
        )
        """))

        # 6. Add some useful views for analytics

        # View for branch hierarchy
        connection.execute(text("""
        CREATE VIEW branch_hierarchy AS
        WITH RECURSIVE branch_tree AS (
            -- Base case: root branches (no base_branch_id)
            SELECT id, name, branch_type, base_branch_id, head_changeset_id,
                   created_by, created_at, 0 as depth,
                   name as branch_path
            FROM branches
            WHERE base_branch_id IS NULL

            UNION ALL

            -- Recursive case: child branches
            SELECT b.id, b.name, b.branch_type, b.base_branch_id, b.head_changeset_id,  # noqa: E501
                   b.created_by, b.created_at, bt.depth + 1 as depth,
                   bt.branch_path || ' -> ' || b.name as branch_path
            FROM branches b
            INNER JOIN branch_tree bt ON b.base_branch_id = bt.id
        )
        SELECT * FROM branch_tree
        ORDER BY depth, created_at;
        """))

        # View for merge request analytics
        connection.execute(text("""
        CREATE VIEW merge_request_analytics AS
        SELECT mr.id, mr.source_branch_id, mr.target_branch_id, mr.title,
               mr.created_by, mr.status, mr.created_at, mr.approved_at, mr.merged_at,  # noqa: E501
               sb.name as source_branch_name, sb.branch_type as source_branch_type,  # noqa: E501
               tb.name as target_branch_name, tb.branch_type as target_branch_type,  # noqa: E501
               CASE
                   WHEN mr.approved_at IS NOT NULL AND mr.created_at IS NOT NULL  # noqa: E501
                   THEN (julianday(mr.approved_at) - julianday(mr.created_at)) * 24 * 60  # noqa: E501
                   ELSE NULL
               END as approval_time_minutes,
               CASE
                   WHEN mr.merged_at IS NOT NULL AND mr.approved_at IS NOT NULL
                   THEN (julianday(mr.merged_at) - julianday(mr.approved_at)) * 24 * 60  # noqa: E501
                   ELSE NULL
               END as merge_time_minutes,
               json_array_length(COALESCE(mr.conflicts, '[]')) as conflict_count  # noqa: E501
        FROM branch_merge_requests mr
        LEFT JOIN branches sb ON mr.source_branch_id = sb.id
        LEFT JOIN branches tb ON mr.target_branch_id = tb.id;
        """))

        # Update schema version
        connection.execute(text(f"""
        UPDATE schema_version SET version = {MIGRATION_VERSION}, updated_at = :updated_at  # noqa: E501
        """), {"updated_at": datetime.now().isoformat()})

        connection.commit()
        logger.info(f"Migration {MIGRATION_VERSION} completed successfully")

    except Exception as e:
        connection.rollback()
        logger.error(f"Migration {MIGRATION_VERSION} failed: {e}")
        raise


def downgrade(connection):
    """Rollback migration 009 - remove advanced features tables."""
    logger.info(f"Rolling back migration {MIGRATION_VERSION}")

    try:
        # Drop views first
        connection.execute(text("DROP VIEW IF EXISTS merge_request_analytics"))
        connection.execute(text("DROP VIEW IF EXISTS branch_hierarchy"))

        # Drop tables in reverse order (respecting foreign key constraints)
        connection.execute(text("DROP TABLE IF EXISTS user_branch_state"))
        connection.execute(text("DROP TABLE IF EXISTS sync_operations"))
        connection.execute(text("DROP TABLE IF EXISTS conflict_descriptors"))
        connection.execute(text("DROP TABLE IF EXISTS branch_merge_requests"))
        connection.execute(text("DROP TABLE IF EXISTS branches"))

        # Revert schema version
        connection.execute(text(f"""
        UPDATE schema_version SET version = {MIGRATION_VERSION - 1}, updated_at = :updated_at  # noqa: E501
        """), {"updated_at": datetime.now().isoformat()})

        connection.commit()
        logger.info(f"Migration {MIGRATION_VERSION} rollback completed")

    except Exception as e:
        connection.rollback()
        logger.error(f"Migration {MIGRATION_VERSION} rollback failed: {e}")
        raise
