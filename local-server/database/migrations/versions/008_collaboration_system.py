"""Migration 008: Add Collaboration System - Changesets, proposals, voting, and identity management."""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)


class Migration008(Migration):
    """Add comprehensive collaboration system for change management workflows."""

    version = 8
    description = "Add Collaboration System - Changesets, proposals, voting, and identity management"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Starting Collaboration System migration...")

        connection.execute(text("PRAGMA foreign_keys=off;"))

        try:
            # Step 1: Create changesets table
            self._create_changesets_table(connection)

            # Step 2: Create proposals table
            self._create_proposals_table(connection)

            # Step 3: Create proposal_votes table
            self._create_proposal_votes_table(connection)

            # Step 4: Create user_identities table
            self._create_user_identities_table(connection)

            # Step 5: Create user_trust_relationships table
            self._create_user_trust_relationships_table(connection)

            # Step 6: Create verification_codes table
            self._create_verification_codes_table(connection)

            # Step 7: Create indexes
            self._create_indexes(connection)

            # Step 8: Validate migration
            self._validate_migration(connection)

            logger.info("Collaboration System migration completed successfully!")

        except Exception as e:
            logger.error(f"Collaboration System migration failed: {e}")
            raise
        finally:
            connection.execute(text("PRAGMA foreign_keys=on;"))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info("Rolling back Collaboration System migration...")

        connection.execute(text("PRAGMA foreign_keys=off;"))

        try:
            # Drop all tables in reverse order
            connection.execute(text("DROP TABLE IF EXISTS verification_codes;"))
            connection.execute(text("DROP TABLE IF EXISTS user_trust_relationships;"))
            connection.execute(text("DROP TABLE IF EXISTS user_identities;"))
            connection.execute(text("DROP TABLE IF EXISTS proposal_votes;"))
            connection.execute(text("DROP TABLE IF EXISTS proposals;"))
            connection.execute(text("DROP TABLE IF EXISTS changesets;"))

            logger.info("Collaboration System migration rollback completed!")

        except Exception as e:
            logger.error(f"Collaboration System rollback failed: {e}")
            raise
        finally:
            connection.execute(text("PRAGMA foreign_keys=on;"))

    def _create_changesets_table(self, connection: Connection) -> None:
        """Create the changesets table."""
        logger.info("Creating changesets table...")

        connection.execute(text("""
            CREATE TABLE changesets (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                state TEXT NOT NULL CHECK (state IN ('DRAFT', 'PROPOSED', 'APPROVED', 'MERGED', 'REJECTED')),  
                branch_name TEXT,
                parent_changeset_id TEXT,
                author_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                merged_at TEXT,
                metadata TEXT,

                FOREIGN KEY (parent_changeset_id) REFERENCES changesets(id)
            );
        """))

        logger.info("Successfully created changesets table")

    def _create_proposals_table(self, connection: Connection) -> None:
        """Create the proposals table."""
        logger.info("Creating proposals table...")

        connection.execute(text("""
            CREATE TABLE proposals (
                id TEXT PRIMARY KEY,
                changeset_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL CHECK (status IN ('open', 'approved', 'rejected', 'merged')),  
                required_approvals INTEGER DEFAULT 1,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                closed_at TEXT,
                merge_commit_id TEXT,
                metadata TEXT,

                FOREIGN KEY (changeset_id) REFERENCES changesets(id)
            );
        """))

        logger.info("Successfully created proposals table")

    def _create_proposal_votes_table(self, connection: Connection) -> None:
        """Create the proposal_votes table."""
        logger.info("Creating proposal_votes table...")

        connection.execute(text("""
            CREATE TABLE proposal_votes (
                proposal_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                vote TEXT NOT NULL CHECK (vote IN ('approve', 'reject', 'abstain')),  
                comment TEXT,
                voted_at TEXT NOT NULL,

                PRIMARY KEY (proposal_id, user_id),
                FOREIGN KEY (proposal_id) REFERENCES proposals(id)
            );
        """))

        logger.info("Successfully created proposal_votes table")

    def _create_user_identities_table(self, connection: Connection) -> None:
        """Create the user_identities table."""
        logger.info("Creating user_identities table...")

        connection.execute(text("""
            CREATE TABLE user_identities (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                public_key TEXT,
                verified BOOLEAN DEFAULT FALSE,
                trust_level INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                verified_at TEXT
            );
        """))

        logger.info("Successfully created user_identities table")

    def _create_user_trust_relationships_table(self, connection: Connection) -> None:
        """Create the user_trust_relationships table."""
        logger.info("Creating user_trust_relationships table...")

        connection.execute(text("""
            CREATE TABLE user_trust_relationships (
                trustee_user_id TEXT NOT NULL,
                trusted_user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,

                PRIMARY KEY (trustee_user_id, trusted_user_id),
                FOREIGN KEY (trustee_user_id) REFERENCES user_identities(user_id),  
                FOREIGN KEY (trusted_user_id) REFERENCES user_identities(user_id)  
            );
        """))

        logger.info("Successfully created user_trust_relationships table")

    def _create_verification_codes_table(self, connection: Connection) -> None:
        """Create the verification_codes table."""
        logger.info("Creating verification_codes table...")

        connection.execute(text("""
            CREATE TABLE verification_codes (
                user_id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,

                FOREIGN KEY (user_id) REFERENCES user_identities(user_id)
            );
        """))

        logger.info("Successfully created verification_codes table")

    def _create_indexes(self, connection: Connection) -> None:
        """Create indexes for performance."""
        logger.info("Creating indexes...")

        # Changesets indexes
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_changesets_author ON changesets(author_id);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_changesets_state ON changesets(state);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_changesets_created ON changesets(created_at);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_changesets_parent ON changesets(parent_changeset_id);"
            )
        )

        # Proposals indexes
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_proposals_changeset ON proposals(changeset_id);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_proposals_created_by ON proposals(created_by);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_proposals_created ON proposals(created_at);"
            )
        )

        # Proposal votes indexes
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_proposal_votes_proposal ON proposal_votes(proposal_id);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_proposal_votes_user ON proposal_votes(user_id);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_proposal_votes_vote ON proposal_votes(vote);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_proposal_votes_voted_at ON proposal_votes(voted_at);"
            )
        )

        # User identities indexes
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_identities_email ON user_identities(email);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_identities_verified ON user_identities(verified);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_identities_trust_level ON user_identities(trust_level);"
            )
        )

        # User trust relationships indexes
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_trust_trusted ON user_trust_relationships(trusted_user_id);"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_trust_trustee ON user_trust_relationships(trustee_user_id);"
            )
        )

        # Verification codes indexes
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_verification_codes_expires ON verification_codes(expires_at);"
            )
        )

        logger.info("Successfully created all indexes")

    def _validate_migration(self, connection: Connection) -> None:
        """Validate migration integrity."""
        logger.info("Validating migration integrity...")

        # Check that all tables were created
        required_tables = [
            "changesets",
            "proposals",
            "proposal_votes",
            "user_identities",
            "user_trust_relationships",
            "verification_codes",
        ]

        for table_name in required_tables:
            result = connection.execute(text(f"""
                SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'
            """)).fetchone()

            if not result:
                raise Exception(f"{table_name} table was not created")

        # Validate that required indexes exist
        indexes = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='index' AND (
                name LIKE 'idx_changesets_%' OR
                name LIKE 'idx_proposals_%' OR
                name LIKE 'idx_proposal_votes_%' OR
                name LIKE 'idx_user_%' OR
                name LIKE 'idx_verification_%'
            )
        """)).fetchall()

        if len(indexes) < 17:  # We created 17 indexes
            logger.warning(f"Expected 17 collaboration indexes, found {len(indexes)}")

        # Test table constraints by attempting invalid inserts
        try:
            # Test invalid changeset state
            connection.execute(text("""
                INSERT INTO changesets (id, title, state, author_id, created_at)  
                VALUES ('test', 'test', 'INVALID', 'test', datetime('now'))
            """))
            raise Exception("Changeset state constraint failed")
        except Exception as e:
            if "CHECK constraint failed" not in str(e):
                raise Exception(
                    "Changeset state constraint validation failed unexpectedly"
                )

        try:
            # Test invalid proposal status
            connection.execute(text("""
                INSERT INTO proposals (id, changeset_id, title, status, created_by, created_at)  
                VALUES ('test', 'test', 'test', 'invalid', 'test', datetime('now'))  
            """))
            raise Exception("Proposal status constraint failed")
        except Exception as e:
            if "CHECK constraint failed" not in str(e):
                raise Exception(
                    "Proposal status constraint validation failed unexpectedly"
                )

        try:
            # Test invalid vote
            connection.execute(text("""
                INSERT INTO proposal_votes (proposal_id, user_id, vote, voted_at)  
                VALUES ('test', 'test', 'invalid', datetime('now'))
            """))
            raise Exception("Vote constraint failed")
        except Exception as e:
            if "CHECK constraint failed" not in str(e):
                raise Exception("Vote constraint validation failed unexpectedly")

        logger.info("Migration validation passed!")
