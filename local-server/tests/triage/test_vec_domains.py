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


def test_create_domain(client, title=f"Test Domain {uuid.uuid4()}", definition=None, primary_predicate=None, layer_id=None):
    data = create_domain(client, title=title, definition=definition, primary_predicate=primary_predicate, layer_id=layer_id)
    assert "id" in data
    assert data["title"] == title, f"Expected title '{title}', got '{data['title']}'"
    assert data["definition"] == definition
    assert data["created_at"]
    assert data["layer_id"] == layer_id, f"Expected layer_id '{layer_id}', got '{data['layer_id']}'"
    return data


def test_find_domain_by_title(client, title):
    response = client.post("/api/domains/find", json={"title": title, "limit": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) > 0, "No domains found with the given title"
    return data


def test_find_domain_by_definition(client, definition):
    response = client.post("/api/domains/find", json={"definition": definition, "limit": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) > 0, "No domains found with the given definition"
    return data


if __name__ == "__main__":
    with TestClient(app) as client_instance:
        # Create a test layer for domains
        logger.info("Creating test layer for domains...")
        test_layer = create_layer(client_instance, title="Test Layer for Domains", definition="Layer for domain tests.", primary_predicate="test_predicate")
        test_layer_id = test_layer["id"]

        domain_data = [
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

        # Create multiple domains
        logger.info("Creating multiple domains...")
        domain_results = []
        for domain in domain_data:
            domain_result = test_create_domain(
                client_instance,
                title=domain["title"],
                definition=domain["definition"],
                primary_predicate=domain["primary_predicate"],
                layer_id=test_layer_id,
            )
            logger.info(
                f"Created domain {domain_result['id']} with title: {domain_result['title']}, definition: {domain_result['definition']}"
            )
            domain_results.append(domain_result)

        # Test the vector search functionality
        logger.info("Testing vector search functionality...")
        for domain in domain_results:
            try:
                logger.info(f"Searching for domain with title: {domain['title']}")
                results = test_find_domain_by_title(client_instance, title=domain["title"])
                assert results[0]["title"] == domain['title'], f"Expected title '{domain['title']}', got '{results[0]['title']}'"
                for result in results:
                    logger.info(f"Found domain with ID: {result['id']}, Title: {result['title']} and score: {result.get('score', 'N/A')}")

                logger.info(f"Searching for domain with definition: {domain['definition']}")
                results = test_find_domain_by_definition(client_instance, definition=domain["definition"])
                assert results[0]["definition"] == domain['definition'], f"Expected definition '{domain['definition']}', got '{results[0]['definition']}'"
                for result in results:
                    logger.info(f"Found domain with ID: {result['id']}, Definition: {result['definition']} and score: {result.get('score', 'N/A')}")
            except Exception as e:
                logger.error(f"Error finding domain by title: {e}")

                # Try searching the database directly
                # title_emb = generate_embedding(domain.get("title", None))
                title_emb = domain.get("title_embedding", None)
                emb_str = "[" + ", ".join(f"{x:.6f}" for x in title_emb) + "]"
                if not emb_str:
                    logger.error(f"No embedding found for domain with title: {domain['title']}")
                    continue

                with TestingSessionLocal() as db:
                    logger.info(f"Searching for domain with title: {domain['title']}")
                    try:
                        sql = text(
                            f"""
                            SELECT id, distance
                            FROM domains_vec
                            WHERE title_embedding match :emb
                            ORDER BY distance
                            LIMIT :limit
                        """
                        )
                        rows = db.execute(sql, {"emb": emb_str, "limit": len(domain_results)}).fetchall()
                        if rows:
                            for row in rows:
                                logger.info(f"Found domain in DB with ID: {row[0]}, Distance: {row[1]}")
                        else:
                            logger.warning("No domains found in the database with the given embedding.")
                    except Exception as db_error:
                        logger.error(f"Database error while searching for domain: {db_error}")

        # Test searching for a similar title
        similar_titles = ["A beautiful sunset", "A great flight"]
        for similar_title in similar_titles:
            try:
              logger.info(f"Testing search for similar title: {similar_title}")
              results = test_find_domain_by_title(client_instance, title=similar_title)
              for result in results:
                  logger.info(f"Found domain with ID: {result['id']}, Title: {result['title']} and score: {result.get('score', 'N/A')}")
            except Exception as e:
                logger.error(f"Error finding domain by title: {e}")

        # Test searching for a similar definition
        similar_definitions = [
            "A beautiful sunset is a sight to behold.",
            "A great flight is one that is smooth and enjoyable.",
        ]
        for similar_definition in similar_definitions:
            try:
                logger.info(f"Testing search for similar definition: {similar_definition}")
                results = test_find_domain_by_definition(client_instance, definition=similar_definition)
                for result in results:
                    logger.info(f"Found domain with ID: {result['id']}, Definition: {result['definition']} and score: {result.get('score', 'N/A')}")
            except Exception as e:
                logger.error(f"Error finding domain by definition: {e}")

        # Dump the contents of the database for debugging
        if True:
          with engine.connect() as connection:
              result = connection.execute(text("SELECT * FROM domains"))
              rows = result.fetchall()
              for row in rows:
                  logger.info(f"Domain: {row}")

              result = connection.execute(text("SELECT * FROM domains_vec"))
              rows = result.fetchall()
              for row in rows:
                  logger.info(f"Domain Vector: {row}")

    logger.info("Test completed successfully.")
    # Clean up the temporary database file
    os.close(test_db_fd)
    os.unlink(test_db_path)
