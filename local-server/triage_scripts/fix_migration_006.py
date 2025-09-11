#!/usr/bin/env python3
"""
Fix Migration 006 Issue

This script fixes databases that have the wrong migration 006 applied.
It removes the incorrect migration history entry and re-runs the correct migration.
"""

import os
import sys
import importlib.util
from sqlalchemy import create_engine, text
from database.migrations.migration_manager import MigrationManager

def fix_database(db_path: str, dry_run: bool = True):
    """Fix a single database file."""
    print(f"\n{'=' * 60}")
    print(f"Processing: {db_path}")
    print(f"{'=' * 60}")
    
    if not os.path.exists(db_path):
        print(f"❌ Database file does not exist: {db_path}")
        return False
    
    try:
        engine = create_engine(f"sqlite:///{db_path}")
        
        with engine.connect() as conn:
            # Check current state
            print("📊 Checking current state...")
            
            # Check schema history
            result = conn.execute(text("SELECT version, description, checksum FROM schema_history WHERE version = 6"))
            version_6_row = result.fetchone()
            
            if not version_6_row:
                print("ℹ️  No version 6 found in schema history")
                return True
                
            print(f"Current version 6: {version_6_row[1]}")
            print(f"Current checksum: {version_6_row[2]}")
            
            # Check if this is the wrong migration (pipeline flavors)
            wrong_checksum = "5d3d3be8d49727c435d3b9c6aa8dbd5f"
            correct_checksum = "094376e3dd8ccb2dc8e9b7215939c478"
            
            if version_6_row[2] == correct_checksum:
                print("✅ Database already has the correct migration 006")
                return True
            elif version_6_row[2] != wrong_checksum:
                print(f"⚠️  Unknown migration 006 checksum: {version_6_row[2]}")
                print("    Proceeding with caution...")
            
            # Check if change_events table exists
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='change_events'"))
            change_events_exists = result.fetchone()
            
            # Check if structure_nodes table exists
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='structure_nodes'"))
            structure_nodes_exists = result.fetchone()
            
            print(f"change_events table: {'EXISTS' if change_events_exists else 'MISSING'}")
            print(f"structure_nodes table: {'EXISTS' if structure_nodes_exists else 'MISSING'}")
            
            if change_events_exists and structure_nodes_exists:
                print("✅ Database already has required tables")
                return True
            
            if dry_run:
                print("\n🔍 DRY RUN MODE - Would perform the following actions:")
                print("1. Remove incorrect version 6 from schema_history")
                print("2. Remove version 7 from schema_history (will be re-applied)")
                print("3. Re-run migration 006 (structure nodes)")
                print("4. Re-run migration 007 (change management)")
                return True
            
            # Perform the fix
            print("\n🔧 FIXING DATABASE...")
            
            try:
                # Step 1: Remove version 6 and 7 from schema history
                print("1. Removing incorrect migrations from schema_history...")
                conn.execute(text("DELETE FROM schema_history WHERE version IN (6, 7)"))
                conn.commit()
                
                # Step 2: Load and run migration 006
                print("2. Loading and running correct migration 006...")
                migration_006_path = os.path.join(
                    os.path.dirname(__file__), 
                    "database/migrations/versions/006_nodes.py"
                )
                spec = importlib.util.spec_from_file_location("migration_006", migration_006_path)
                migration_006_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration_006_module)
                
                migration_006 = migration_006_module.Migration006()
                migration_006.up(conn)
                
                # Step 3: Add migration 006 to schema history
                print("3. Adding migration 006 to schema history...")
                import hashlib
                import time
                
                # Calculate checksum for the correct migration file
                migration_file_path = os.path.join(
                    os.path.dirname(__file__), 
                    "database/migrations/versions/006_nodes.py"
                )
                with open(migration_file_path, 'r') as f:
                    content = f.read()
                checksum = hashlib.md5(content.encode()).hexdigest()
                
                conn.execute(text("""
                    INSERT INTO schema_history 
                    (version, description, migration_file, checksum, execution_time_ms)
                    VALUES (:version, :description, :migration_file, :checksum, :execution_time_ms)
                """), {
                    'version': 6, 
                    'description': migration_006.description, 
                    'migration_file': "006_nodes.py", 
                    'checksum': checksum, 
                    'execution_time_ms': 0
                })
                conn.commit()
                
                # Step 4: Re-run migration 007 if it exists
                try:
                    migration_007_path = os.path.join(
                        os.path.dirname(__file__), 
                        "database/migrations/versions/007_change_management.py"
                    )
                    if os.path.exists(migration_007_path):
                        print("4. Loading and running migration 007...")
                        spec = importlib.util.spec_from_file_location("migration_007", migration_007_path)
                        migration_007_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(migration_007_module)
                        
                        migration_007 = migration_007_module.Migration007()
                        migration_007.up(conn)
                        
                        # Add to schema history
                        with open(migration_007_path, 'r') as f:
                            content = f.read()
                        checksum_007 = hashlib.md5(content.encode()).hexdigest()
                        
                        conn.execute(text("""
                            INSERT INTO schema_history 
                            (version, description, migration_file, checksum, execution_time_ms)
                            VALUES (:version, :description, :migration_file, :checksum, :execution_time_ms)
                        """), {
                            'version': 7, 
                            'description': migration_007.description, 
                            'migration_file': "007_change_management.py", 
                            'checksum': checksum_007, 
                            'execution_time_ms': 0
                        })
                        conn.commit()
                    else:
                        print("ℹ️  Migration 007 file not found, skipping...")
                    
                except Exception as e:
                    print(f"ℹ️  Migration 007 error: {e}, skipping...")
                
                print("✅ Database fixed successfully!")
                
                # Verify the fix
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='change_events'"))
                if result.fetchone():
                    print("✅ change_events table now exists")
                else:
                    print("❌ change_events table still missing")
                    return False
                
                return True
                
            except Exception as e:
                print(f"❌ Error during migration fix: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Error processing database: {e}")
        return False

def main():
    """Main function to fix affected databases."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix Migration 006 Issue")
    parser.add_argument("--dry-run", action="store_true", default=True,
                      help="Show what would be done without making changes")
    parser.add_argument("--apply", action="store_true", 
                      help="Actually apply the fixes")
    parser.add_argument("--database", type=str,
                      help="Fix specific database file")
    
    args = parser.parse_args()
    
    if args.apply:
        dry_run = False
        print("🚨 APPLY MODE - Changes will be made to the database!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return
    else:
        dry_run = True
        print("🔍 DRY RUN MODE - No changes will be made")
    
    # Determine which databases to fix
    if args.database:
        databases = [args.database]
    else:
        datasets_dir = os.path.expanduser("~/Documents/ContextStudio/datasets")
        databases = [
            os.path.join(datasets_dir, "local.db"),
            os.path.join(datasets_dir, "playground_dataset.db")
        ]
    
    print(f"Processing {len(databases)} database(s)...")
    
    success_count = 0
    for db_path in databases:
        if fix_database(db_path, dry_run=dry_run):
            success_count += 1
    
    print(f"\n{'=' * 60}")
    print(f"Summary: {success_count}/{len(databases)} databases processed successfully")
    
    if dry_run:
        print("\nTo apply the fixes, run with --apply flag:")
        print("python fix_migration_006.py --apply")

if __name__ == "__main__":
    main()