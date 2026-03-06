"""Migration 011: Remove Branch Management System"""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
from utils.logger import get_logger

logger = get_logger(__name__)


class Migration011(Migration):
    """Remove Branch Management System migration."""

    version = 11
    description = "Remove Branch Management System"

    def up(self, connection: Connection) -> None:
        """Apply migration 011 - remove branch management system."""
        logger.info(f"Applying migration {self.version}: {self.description}")

        try:
            # Enable foreign keys
            connection.execute(text("PRAGMA foreign_keys = ON"))

            # Drop views first (they depend on tables)
            logger.info("Dropping branch-related views...")
            connection.execute(text("DROP VIEW IF EXISTS merge_request_analytics"))
            connection.execute(text("DROP VIEW IF EXISTS branch_hierarchy"))

            # Drop tables in reverse dependency order
            logger.info("Dropping branch-related tables...")
            connection.execute(text("DROP TABLE IF EXISTS user_branch_state"))
            connection.execute(text("DROP TABLE IF EXISTS branch_merge_requests"))
            connection.execute(text("DROP TABLE IF EXISTS branches"))

            # Note: We keep conflict_descriptors and sync_operations as they may be used
            # by non-branch functionality (proposals, changesets, etc.)

            logger.info(f"Migration {self.version} applied successfully")

        except Exception as e:
            logger.error(f"Failed to apply migration {self.version}: {e}")
            raise

    def down(self, connection: Connection) -> None:
        """Rollback migration 011 - recreate branch management tables."""
        logger.warning(f"Rolling back migration {self.version} - this will recreate empty branch tables")

        try:
            # Enable foreign keys
            connection.execute(text("PRAGMA foreign_keys = ON"))

            # Recreate branches table
            connection.execute(text("""
            CREATE TABLE branches (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                branch_type TEXT NOT NULL CHECK (branch_type IN ('main', 'feature', 'release', 'hotfix')),  
                base_branch_id TEXT,
                head_changeset_id TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                description TEXT,
                protected INTEGER DEFAULT 0 CHECK (protected IN (0, 1)),
                metadata TEXT,  -- JSON metadata
                FOREIGN KEY (base_branch_id) REFERENCES branches(id) ON DELETE SET NULL,  
                FOREIGN KEY (head_changeset_id) REFERENCES changesets(id) ON DELETE SET NULL  
            )
            """))

            # Recreate branch merge requests table
            connection.execute(text("""
            CREATE TABLE branch_merge_requests (
                id TEXT PRIMARY KEY,
                source_branch_id TEXT NOT NULL,
                target_branch_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_by TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('open', 'approved', 'merged', 'closed', 'conflicts')),  
                conflicts TEXT,  -- JSON array of conflicts
                created_at TEXT NOT NULL,
                approved_by TEXT,
                approved_at TEXT,
                merged_at TEXT,
                metadata TEXT,  -- JSON metadata
                FOREIGN KEY (source_branch_id) REFERENCES branches(id) ON DELETE CASCADE,  
                FOREIGN KEY (target_branch_id) REFERENCES branches(id) ON DELETE CASCADE  
            )
            """))

            # Recreate user branch state table
            connection.execute(text("""
            CREATE TABLE user_branch_state (
                user_id TEXT NOT NULL,
                current_branch_id TEXT,
                switched_at TEXT NOT NULL,
                PRIMARY KEY (user_id),
                FOREIGN KEY (current_branch_id) REFERENCES branches(id) ON DELETE SET NULL  
            )
            """))

            # Recreate indexes
            connection.execute(text("CREATE INDEX idx_branches_type_created ON branches(branch_type, created_at DESC)"))
            connection.execute(text("CREATE INDEX idx_branches_created_by ON branches(created_by, created_at DESC)"))
            connection.execute(text("CREATE INDEX idx_branches_base_branch ON branches(base_branch_id)"))
            connection.execute(text("CREATE INDEX idx_merge_requests_status ON branch_merge_requests(status, created_at DESC)"))
            connection.execute(text("CREATE INDEX idx_merge_requests_created_by ON branch_merge_requests(created_by, created_at DESC)"))
            connection.execute(text("CREATE INDEX idx_merge_requests_branches ON branch_merge_requests(source_branch_id, target_branch_id)"))

            # Recreate views
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
                SELECT b.id, b.name, b.branch_type, b.base_branch_id, b.head_changeset_id,  
                       b.created_by, b.created_at, bt.depth + 1 as depth,
                       bt.branch_path || ' -> ' || b.name as branch_path
                FROM branches b
                INNER JOIN branch_tree bt ON b.base_branch_id = bt.id
            )
            SELECT * FROM branch_tree
            """))

            connection.execute(text("""
            CREATE VIEW merge_request_analytics AS
            SELECT mr.id, mr.source_branch_id, mr.target_branch_id, mr.title,
                   mr.status, mr.created_by, mr.created_at, mr.merged_at,
                   sb.name as source_branch_name, sb.branch_type as source_branch_type,  
                   tb.name as target_branch_name, tb.branch_type as target_branch_type,  
                   CASE
                       WHEN mr.merged_at IS NOT NULL THEN
                           CAST((julianday(mr.merged_at) - julianday(mr.created_at)) * 24 * 60 AS INTEGER)  
                       ELSE NULL
                   END as merge_time_minutes,
                   CASE
                       WHEN mr.conflicts IS NOT NULL AND mr.conflicts != '[]' THEN 1  
                       ELSE 0
                   END as had_conflicts,
                   LENGTH(mr.conflicts) - LENGTH(REPLACE(mr.conflicts, ',', '')) + 1 as conflict_count  
            FROM branch_merge_requests mr
            LEFT JOIN branches sb ON mr.source_branch_id = sb.id
            LEFT JOIN branches tb ON mr.target_branch_id = tb.id;
            """))

            logger.info(f"Migration {self.version} rolled back successfully")

        except Exception as e:
            logger.error(f"Failed to rollback migration {self.version}: {e}")
            raise
