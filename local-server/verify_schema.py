"""
Verification script to check external_predicates table schema.
"""
import tempfile
import os
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from sqlalchemy import text

# Create a temporary database
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
    db_path = tf.name

try:
    # Initialize database
    config = ReferenceConfig()
    with ReferenceManager(config, db_path=db_path) as manager:
        # Query the schema to verify external_predicates table exists
        with manager.engine.connect() as conn:
            # Get all tables
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
            tables = [row[0] for row in result]
            print('Tables in database:')
            for table in tables:
                print(f'  - {table}')

            # Check for external_predicates table
            if 'external_predicates' in tables:
                print('\n✓ external_predicates table exists')

                # Get column info
                result = conn.execute(text("PRAGMA table_info(external_predicates)"))
                print('\nColumns in external_predicates:')
                for row in result:
                    print(f'  - {row[1]} ({row[2]}) {"NOT NULL" if row[3] else "NULL"} {"PRIMARY KEY" if row[5] else ""}')

                # Get indexes
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='external_predicates'"))
                indexes = [row[0] for row in result]
                print(f'\nIndexes on external_predicates: {len(indexes)}')
                for idx in indexes:
                    print(f'  - {idx}')

                # Get constraints
                result = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='external_predicates'"))
                create_sql = result.fetchone()[0]
                if 'UNIQUE' in create_sql:
                    print('\n✓ UNIQUE constraint found in table definition')
                print('\nTable CREATE SQL:')
                print(create_sql)
            else:
                print('\n✗ external_predicates table NOT found!')
finally:
    if os.path.exists(db_path):
        os.unlink(db_path)
