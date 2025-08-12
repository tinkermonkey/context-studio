import argparse
import csv
import sys

import sys
import os
import csv
import argparse
import uuid
from sqlalchemy.orm import Session
from database.models import Layer, Domain, Term
from database.utils import get_engine, get_session_local, init_db
from utils.logger import get_logger

logger = get_logger("import_csv")

def get_or_create_import_layer(session: Session) -> Layer:
    layer = session.query(Layer).filter_by(title="Import").first()
    if not layer:
        layer = Layer(
            id=str(uuid.uuid4()),
            title="Import",
            definition="Imported layer for CSV import",
        )
        session.add(layer)
        session.commit()
        logger.info(f"Created Import layer with id: {layer.id}")
    else:
        logger.info(f"Using existing Import layer with id: {layer.id}")
    return layer

def read_csv_rows(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = [dict(row) for row in reader]
    return rows

def import_records(rows, session: Session, layer: Layer):
    # Track last seen Layer, Domain, and Term by depth for parent relationships
    last_layer = None
    last_domain = None
    last_terms_by_depth = {}

    for row in rows:
        try:
            depth = int(str(row.get("Depth")).strip())
        except (TypeError, ValueError):
            logger.warning(f"Row missing or invalid Depth: {row}")
            continue

        if depth == 0:
            # Layer
            layer_id = row.get("ID") or str(uuid.uuid4())
            title = row.get("Title")
            definition = row.get("Definition")
            lyr = session.query(Layer).filter_by(id=layer_id).first()
            if not lyr:
                lyr = Layer(
                    id=layer_id,
                    title=title,
                    definition=definition,
                )
                session.add(lyr)
                logger.info(f"Created Layer: {title} (ID: {layer_id})")
            else:
                lyr.title = title
                lyr.definition = definition
                logger.info(f"Updated Layer: {title} (ID: {layer_id})")
            session.commit()
            last_layer = lyr
        elif depth == 1:
            # Domain
            domain_id = row.get("ID") or str(uuid.uuid4())
            title = row.get("Title")
            definition = row.get("Definition")
            # Use last_layer if present, else fallback to provided layer
            layer_id = last_layer.id if last_layer else layer.id
            domain = session.query(Domain).filter_by(id=domain_id).first()
            if not domain:
                domain = Domain(
                    id=domain_id,
                    title=title,
                    definition=definition,
                    layer_id=layer_id,
                )
                session.add(domain)
                logger.info(f"Created Domain: {title} (ID: {domain_id})")
            else:
                domain.title = title
                domain.definition = definition
                domain.layer_id = layer_id
                logger.info(f"Updated Domain: {title} (ID: {domain_id})")
            session.commit()
            last_domain = domain
        elif depth > 1:
            # Term
            term_id = row.get("ID") or str(uuid.uuid4())
            title = row.get("Title")
            definition = row.get("Definition")
            parent_id = None
            # Set parent_term_id if previous term at depth-1 exists
            if (depth - 1) in last_terms_by_depth:
                parent_id = last_terms_by_depth[depth - 1].id
            # Use last_domain for domain_id, last_layer for layer_id
            domain_id = last_domain.id if last_domain else None
            layer_id = last_layer.id if last_layer else layer.id
            if not domain_id:
                logger.warning(f"No domain found for term {title} (ID: {term_id}), skipping.")
                continue
            try:
                term = session.query(Term).filter_by(id=term_id).first()
                if not term:
                    term = Term(
                        id=term_id,
                        title=title,
                        definition=definition,
                        domain_id=domain_id,
                        layer_id=layer_id,
                        parent_term_id=parent_id if parent_id else None,
                    )
                    session.add(term)
                    logger.info(f"Created Term: {title} (ID: {term_id})")
                else:
                    term.title = title
                    term.definition = definition
                    term.domain_id = domain_id
                    term.layer_id = layer_id
                    term.parent_term_id = parent_id if parent_id else None
                    logger.info(f"Updated Term: {title} (ID: {term_id})")
                last_terms_by_depth[depth] = term
                session.commit()
            except Exception as e:
                session.rollback()
                if 'UNIQUE constraint failed: terms.id' in str(e):
                    logger.error(f"Skipped duplicate Term with id {term_id} (title: {title}). This term already exists in the database. If you want to update it, please remove the duplicate or update the CSV.")
                else:
                    logger.error(f"Error processing Term {title} (ID: {term_id}): {e}")

def main():
    parser = argparse.ArgumentParser(description="Import taxonomy data from CSV into database.")
    parser.add_argument("-f", "--file", required=True, help="Path to the CSV file to import")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--test", action="store_true", help="Import only the first 10 rows for smoke testing")
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(10)  # 10 is logging.DEBUG

    # Setup DB
    engine = get_engine()
    init_db(engine)
    SessionLocal = get_session_local(engine)
    session = SessionLocal()

    try:
        layer = get_or_create_import_layer(session)
        logger.info("Reading CSV rows...")
        rows = read_csv_rows(args.file)
        if not rows:
            logger.error("No data found in the CSV file.")
            sys.exit(1)
        if args.test:
            logger.info("Test mode enabled: only importing the first 10 rows.")
            rows = rows[:10]
        logger.info(f"Importing {len(rows)} rows...")
        import_records(rows, session, layer)
        logger.info("Import complete.")
    except FileNotFoundError:
        logger.error(f"File not found: {args.file}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()

