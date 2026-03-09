# mypy: ignore-errors
"""
Import ontology CSV into the unified structure_nodes schema.

This script imports hierarchical taxonomy data from CSV files into the current
StructureNode-based database schema, replacing the deprecated import_csv.py utility.  # noqa: E501
"""

import argparse
import csv
import sys
from typing import Dict, Optional

from sqlalchemy.orm import Session
from database.utils import get_current_engine, get_session_local, init_db
from database.models import StructureNode
from database.enums import NodeType
from embeddings.generate_embeddings import generate_embedding
from utils.logger import get_logger

logger = get_logger("import_ontology_csv")


def read_csv_rows(file_path: str) -> list:
    """Read CSV file and return rows as list of dictionaries."""
    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        rows = [dict(row) for row in reader]
    return rows


def get_node_type_from_depth(depth: int) -> NodeType:
    """Convert CSV depth to NodeType enum."""
    if depth == 0:
        return NodeType.LAYER
    elif depth == 1:
        return NodeType.DOMAIN
    else:
        return NodeType.TERM


def generate_embeddings_safe(text: str) -> Optional[bytes]:
    """Generate embedding with error handling."""
    if not text:
        return None
    try:
        return generate_embedding(text)
    except Exception as e:
        logger.warning(f"Failed to generate embedding: {e}")
        return None


def import_records(rows: list, session: Session, update_existing: bool = True):
    """
    Import records from CSV into structure_nodes table.

    Args:
        rows: List of dictionaries from CSV
        session: Database session
        update_existing: If True, update existing nodes by ID. If False, skip duplicates.  # noqa: E501
    """
    # Track last seen nodes by depth for parent relationships
    last_nodes_by_depth: Dict[int, StructureNode] = {}

    created_count = 0
    updated_count = 0
    skipped_count = 0

    for row_num, row in enumerate(rows, start=2):  # Start at 2 (1 is header)
        try:
            # Parse depth
            try:
                depth = int(str(row.get("Depth", "")).strip())
            except (TypeError, ValueError):
                logger.warning(
                    f"Row {row_num}: Missing or invalid Depth value, skipping"
                )  # noqa: E501
                skipped_count += 1
                continue

            # Extract fields
            node_id = row.get("ID", "").strip() or None
            title = row.get("Title", "").strip()
            definition = row.get("Definition", "").strip() or None

            if not title:
                logger.warning(f"Row {row_num}: Missing Title, skipping")
                skipped_count += 1
                continue

            # Determine node type
            node_type = get_node_type_from_depth(depth)

            # Determine parent node
            parent_node_id = None
            if depth > 0:
                # Find parent from previous depth level
                parent_depth = depth - 1
                if parent_depth in last_nodes_by_depth:
                    parent_node_id = last_nodes_by_depth[parent_depth].id
                else:
                    logger.warning(
                        f"Row {row_num}: No parent found at depth {parent_depth} for {title}, skipping"
                    )  # noqa: E501
                    skipped_count += 1
                    continue

            # Check if node with this ID already exists
            existing_node = None
            if node_id:
                existing_node = (
                    session.query(StructureNode).filter_by(id=node_id).first()
                )  # noqa: E501

            if existing_node:
                if update_existing:
                    # Update existing node
                    existing_node.title = title
                    existing_node.definition = definition
                    existing_node.node_type = node_type
                    existing_node.parent_node_id = parent_node_id

                    # Regenerate embeddings
                    existing_node.title_embedding = generate_embeddings_safe(
                        title
                    )  # noqa: E501
                    existing_node.definition_embedding = generate_embeddings_safe(
                        definition
                    )  # noqa: E501

                    session.commit()
                    logger.info(
                        f"Row {row_num}: Updated {node_type.value} '{title}' (ID: {node_id})"
                    )  # noqa: E501
                    updated_count += 1
                    last_nodes_by_depth[depth] = existing_node
                else:
                    logger.info(
                        f"Row {row_num}: Node with ID {node_id} exists, skipping"
                    )  # noqa: E501
                    skipped_count += 1
                    last_nodes_by_depth[depth] = existing_node
            else:
                # Create new node
                node = StructureNode(
                    id=node_id,  # Will auto-generate if None
                    node_type=node_type,
                    parent_node_id=parent_node_id,
                    title=title,
                    definition=definition,
                    title_embedding=generate_embeddings_safe(title),
                    definition_embedding=generate_embeddings_safe(definition),
                )

                session.add(node)
                session.commit()
                logger.info(
                    f"Row {row_num}: Created {node_type.value} '{title}' (ID: {node.id})"
                )  # noqa: E501
                created_count += 1
                last_nodes_by_depth[depth] = node

        except Exception as e:
            session.rollback()
            logger.error(
                f"Row {row_num}: Error processing '{row.get('Title', 'unknown')}': {e}"
            )  # noqa: E501
            skipped_count += 1
            continue

    logger.info(
        f"Import complete: {created_count} created, {updated_count} updated, {skipped_count} skipped"
    )  # noqa: E501


def main():
    parser = argparse.ArgumentParser(
        description="Import ontology CSV into structure_nodes database schema."
    )
    parser.add_argument(
        "-f", "--file", required=True, help="Path to the CSV file to import"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--test", action="store_true", help="Import only the first 10 rows for testing"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip existing nodes instead of updating them",
    )
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(10)  # DEBUG level

    # Setup database - use active dataset
    engine = get_current_engine()
    logger.info(f"Using active database: {engine.url}")
    init_db(engine)
    SessionLocal = get_session_local(engine)
    session = SessionLocal()

    try:
        logger.info(f"Reading CSV file: {args.file}")
        rows = read_csv_rows(args.file)

        if not rows:
            logger.error("No data found in the CSV file.")
            sys.exit(1)

        if args.test:
            logger.info("Test mode enabled: importing first 10 rows only")
            rows = rows[:10]

        logger.info(f"Importing {len(rows)} rows...")
        import_records(rows, session, update_existing=not args.skip_existing)
        logger.info("Import complete")

    except FileNotFoundError:
        logger.error(f"File not found: {args.file}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
