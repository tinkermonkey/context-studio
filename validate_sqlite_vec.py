#!/usr/bin/env python3
"""
SQLite-vec validation script for ARM64/aarch64 architecture
Validates extension loading, architecture compatibility, and basic operations
"""

import sqlite3
import platform
import sqlite_vec
import tempfile
import os

def validate_sqlite_vec():
    """Validate sqlite-vec installation and ARM64 compatibility."""

    print("🔍 SQLite-vec Validation")
    print("=" * 50)

    # 1. Architecture validation
    arch = platform.machine()
    print(f"✓ System Architecture: {arch}")
    if arch != 'aarch64':
        print(f"⚠️  Warning: Expected aarch64, got {arch}")
    else:
        print("✓ ARM64/aarch64 architecture confirmed")

    # 2. SQLite info
    print(f"✓ SQLite Version: {sqlite3.sqlite_version}")

    # 3. Extension loading test
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        conn = sqlite3.connect(db_path)
        conn.enable_load_extension(True)

        # Load sqlite-vec extension
        sqlite_vec.load(conn)
        print("✓ sqlite-vec extension loaded successfully")

        # Get version info
        version = conn.execute("SELECT vec_version()").fetchone()[0]
        print(f"✓ sqlite-vec version: {version}")

        # 4. Basic vector operations test
        # Create virtual table
        conn.execute("""
            CREATE VIRTUAL TABLE test_vectors USING vec0(
                id TEXT PRIMARY KEY,
                embedding FLOAT[4]
            )
        """)
        print("✓ Vector virtual table created")

        # Test vector serialization
        test_vector = [0.1, 0.2, 0.3, 0.4]
        serialized = sqlite_vec.serialize_float32(test_vector)
        length = conn.execute("SELECT vec_length(?)", [serialized]).fetchone()[0]

        if length == 4:
            print("✓ Vector serialization and length calculation working")
        else:
            print(f"❌ Vector length mismatch: expected 4, got {length}")
            return False

        # Test vector insertion and similarity search
        conn.execute("""
            INSERT INTO test_vectors (id, embedding) VALUES
            ('vec1', '[0.1, 0.2, 0.3, 0.4]'),
            ('vec2', '[0.5, 0.6, 0.7, 0.8]')
        """)

        # Test KNN query
        result = conn.execute("""
            SELECT id, distance FROM test_vectors
            WHERE embedding MATCH '[0.1, 0.2, 0.3, 0.4]'
            ORDER BY distance LIMIT 1
        """).fetchone()

        if result and result[0] == 'vec1' and result[1] == 0.0:
            print("✓ Vector similarity search working")
        else:
            print(f"❌ Vector search failed: {result}")
            return False

        print("=" * 50)
        print("🎉 All validations passed! sqlite-vec is properly installed for ARM64")
        return True

    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        return False

    finally:
        if 'conn' in locals():
            conn.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

if __name__ == "__main__":
    success = validate_sqlite_vec()
    exit(0 if success else 1)
