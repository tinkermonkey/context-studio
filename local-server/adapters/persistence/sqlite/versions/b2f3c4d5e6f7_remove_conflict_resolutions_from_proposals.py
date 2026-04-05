"""Remove conflict_resolutions field from proposals table

This field was added beyond the architecture specification. The proposals table
schema per the spec is: id, changeset_id, state, submitted_at, reviewed_at, reviewer_notes

Revision ID: b2f3c4d5e6f7
Revises: a1fd835be0a1
Create Date: 2026-04-05 03:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2f3c4d5e6f7'
down_revision = 'a1fd835be0a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
    # Create a new proposals table without conflict_resolutions
    op.execute("""
        CREATE TABLE proposals_new (
            id VARCHAR(36) NOT NULL,
            changeset_id VARCHAR(36) NOT NULL,
            state VARCHAR(20) NOT NULL DEFAULT 'open',
            submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at DATETIME,
            reviewer_notes TEXT,
            PRIMARY KEY (id),
            FOREIGN KEY (changeset_id) REFERENCES changesets (id) ON DELETE CASCADE
        )
    """)

    # Copy data from old table to new table
    op.execute("""
        INSERT INTO proposals_new (id, changeset_id, state, submitted_at, reviewed_at, reviewer_notes)
        SELECT id, changeset_id, state, submitted_at, reviewed_at, reviewer_notes FROM proposals
    """)

    # Drop old table
    op.execute("DROP TABLE proposals")

    # Rename new table to original name
    op.execute("ALTER TABLE proposals_new RENAME TO proposals")

    # Recreate the index
    op.create_index('ix_proposals_changeset_id', 'proposals', ['changeset_id'])


def downgrade() -> None:
    # Drop the index
    op.drop_index('ix_proposals_changeset_id', table_name='proposals')

    # Create old proposals table with conflict_resolutions
    op.execute("""
        CREATE TABLE proposals_old (
            id VARCHAR(36) NOT NULL,
            changeset_id VARCHAR(36) NOT NULL,
            state VARCHAR(20) NOT NULL DEFAULT 'open',
            submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at DATETIME,
            reviewer_notes TEXT,
            conflict_resolutions JSON NOT NULL DEFAULT '{}',
            PRIMARY KEY (id),
            FOREIGN KEY (changeset_id) REFERENCES changesets (id) ON DELETE CASCADE
        )
    """)

    # Copy data back
    op.execute("""
        INSERT INTO proposals_old (id, changeset_id, state, submitted_at, reviewed_at, reviewer_notes, conflict_resolutions)
        SELECT id, changeset_id, state, submitted_at, reviewed_at, reviewer_notes, '{}' FROM proposals
    """)

    # Drop new table
    op.execute("DROP TABLE proposals")

    # Rename old table back
    op.execute("ALTER TABLE proposals_old RENAME TO proposals")

    # Recreate the index
    op.create_index('ix_proposals_changeset_id', 'proposals', ['changeset_id'])
