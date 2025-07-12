# Ensure project root is on sys.path for imports
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import tempfile
from fastapi.testclient import TestClient
from database.utils import init_db, get_session_local
from embeddings.generate_embeddings import generate_embedding
from app import create_app
import uuid
from sqlalchemy import text
from utils.logger import get_logger

logger = get_logger(__name__)

# Use a temporary file for the test database
test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{test_db_path}"
engine = init_db(database_url=SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, skip_vec=False)
TestingSessionLocal = get_session_local(engine)

# Create a test app instance with test DB engine/session
app = create_app(engine=engine, session_local=TestingSessionLocal, skip_vec=False)


def client():
    with TestClient(app) as c:
        yield c


def create_layer(client, title=None, definition=None, primary_predicate=None):
    unique_title = title if title else f"Test Layer {uuid.uuid4()}"
    payload = {
        "title": unique_title,
        "definition": definition or "Layer for integration test.",
        "primary_predicate": primary_predicate,
    }
    response = client.post("/api/layers/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def create_domain(client, title=None, definition=None, primary_predicate=None, layer_id=None):
    unique_title = title if title else f"Test Domain {uuid.uuid4()}"
    payload = {
        "title": unique_title,
        "definition": definition or "Domain for integration test.",
        "primary_predicate": primary_predicate,
        "layer_id": layer_id,
    }
    response = client.post("/api/domains/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def create_term(client, title=None, definition=None, primary_predicate=None, layer_id=None, domain_id=None):
    unique_title = title if title else f"Test Term {uuid.uuid4()}"
    payload = {
        "title": unique_title,
        "definition": definition or "Term for integration test.",
        "primary_predicate": primary_predicate,
        "layer_id": layer_id,
        "domain_id": domain_id,
    }
    response = client.post("/api/terms/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_term(client, title=f"Test Term {uuid.uuid4()}", definition=None, primary_predicate=None, layer_id=None, domain_id=None):
    data = create_term(client, title=title, definition=definition, primary_predicate=primary_predicate, layer_id=layer_id, domain_id=domain_id)
    assert "id" in data
    assert data["title"] == title, f"Expected title '{title}', got '{data['title']}'"
    assert data["definition"] == definition
    assert data["created_at"]
    assert data["layer_id"] == layer_id, f"Expected layer_id '{layer_id}', got '{data['layer_id']}'"
    assert data["domain_id"] == domain_id, f"Expected domain_id '{domain_id}', got '{data['domain_id']}'"
    return data


def test_find_term_by_title(client, title):
    response = client.post("/api/terms/find", json={"title": title, "limit": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) > 0, "No terms found with the given title"
    return data


def test_find_term_by_definition(client, definition):
    response = client.post("/api/terms/find", json={"definition": definition, "limit": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) > 0, "No terms found with the given definition"
    return data

if __name__ == "__main__":
    with TestClient(app) as client_instance:
        # Create a test layer for terms
        logger.info("Creating test layer for terms...")
        test_layer = create_layer(client_instance, title="Test Layer for Terms", definition="Layer for term tests.", primary_predicate="test_predicate")
        test_layer_id = test_layer["id"]

        # Create a test domain for terms
        logger.info("Creating test domain for terms...")
        test_domain = create_domain(client_instance, title="Test Domain for Terms", definition="Domain for term tests.", primary_predicate="test_predicate", layer_id=test_layer_id)
        test_domain_id = test_domain["id"]

        term_data = [
            {
                "title": f"Amazing test flights",
                "definition": "Amazing test flights are test flights which go really well and result in a wonderful outcome.",
                "primary_predicate": "test_predicate",
            },
            {
                "title": f"A wonderful sunset",
                "definition": "A wonderful sunset is a sunset that is particularly beautiful and inspiring.",
                "primary_predicate": "another_predicate",
            },
            {
                "title": f"Peanuts and jelly",
                "definition": "Peanuts and jelly is a classic sandwich combination that is both delicious and satisfying.",
                "primary_predicate": "third_predicate",
            },
        ]

        # Create multiple terms
        logger.info("Creating multiple terms...")
        term_results = []
        for term in term_data:
            term_result = test_create_term(
                client_instance,
                title=term["title"],
                definition=term["definition"],
                primary_predicate=term["primary_predicate"],
                layer_id=test_layer_id,
                domain_id=test_domain_id,
            )
            logger.info(
                f"Created term {term_result['id']} with title: {term_result['title']}, definition: {term_result['definition']}"
            )
            term_results.append(term_result)

        # Test the vector search functionality
        logger.info("Testing vector search functionality...")
        for term in term_results:
            try:
                logger.info(f"Searching for term with title: {term['title']}")
                results = test_find_term_by_title(client_instance, title=term["title"])
                assert results[0]["title"] == term['title'], f"Expected title '{term['title']}', got '{results[0]['title']}'"
                for result in results:
                    logger.info(f"Found term with ID: {result['id']}, Title: {result['title']} and score: {result.get('score', 'N/A')}")

                logger.info(f"Searching for term with definition: {term['definition']}")
                results = test_find_term_by_definition(client_instance, definition=term["definition"])
                assert results[0]["definition"] == term['definition'], f"Expected definition '{term['definition']}', got '{results[0]['definition']}'"
                for result in results:
                    logger.info(f"Found term with ID: {result['id']}, Definition: {result['definition']} and score: {result.get('score', 'N/A')}")
            except Exception as e:
                logger.error(f"Error finding term by title: {e}")

                # Try searching the database directly
                # title_emb = generate_embedding(term.get("title", None))
                title_emb = term.get("title_embedding", None)
                emb_str = "[" + ", ".join(f"{x:.6f}" for x in title_emb) + "]"
                if not emb_str:
                    logger.error(f"No embedding found for term with title: {term['title']}")
                    continue

                with TestingSessionLocal() as db:
                    logger.info(f"Searching for term with title: {term['title']}")
                    try:
                        sql = text(
                            f"""
                            SELECT id, distance
                            FROM terms_vec
                            WHERE title_embedding match :emb
                            ORDER BY distance
                            LIMIT :limit
                        """
                        )
                        rows = db.execute(sql, {"emb": emb_str, "limit": len(term_results)}).fetchall()
                        if rows:
                            for row in rows:
                                logger.info(f"Found term in DB with ID: {row[0]}, Distance: {row[1]}")
                        else:
                            logger.warning("No terms found in the database with the given embedding.")
                    except Exception as db_error:
                        logger.error(f"Database error while searching for term: {db_error}")

        # Test searching for a similar title
        similar_titles = ["A beautiful sunset", "A great flight"]
        for similar_title in similar_titles:
            try:
              logger.info(f"Testing search for similar title: {similar_title}")
              results = test_find_term_by_title(client_instance, title=similar_title)
              for result in results:
                  logger.info(f"Found term with ID: {result['id']}, Title: {result['title']} and score: {result.get('score', 'N/A')}")
            except Exception as e:
                logger.error(f"Error finding term by title: {e}")

        # Test searching for a similar definition
        similar_definitions = [
            "A beautiful sunset is a sight to behold.",
            "A great flight is one that is smooth and enjoyable.",
        ]
        for similar_definition in similar_definitions:
            try:
                logger.info(f"Testing search for similar definition: {similar_definition}")
                results = test_find_term_by_definition(client_instance, definition=similar_definition)
                for result in results:
                    logger.info(f"Found term with ID: {result['id']}, Definition: {result['definition']} and score: {result.get('score', 'N/A')}")
            except Exception as e:
                logger.error(f"Error finding term by definition: {e}")

        # Dump the contents of the database for debugging
        if False:
          with engine.connect() as connection:
              result = connection.execute(text("SELECT * FROM terms"))
              rows = result.fetchall()
              for row in rows:
                  logger.info(f"Term: {row}")

              result = connection.execute(text("SELECT * FROM terms_vec"))
              rows = result.fetchall()
              for row in rows:
                  logger.info(f"Term Vector: {row}")

    logger.info("Test completed successfully.")
    # Clean up the temporary database file
    os.close(test_db_fd)
    os.unlink(test_db_path)
