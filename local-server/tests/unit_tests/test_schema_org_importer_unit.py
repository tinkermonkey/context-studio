"""
Unit tests for Schema.org importer components.

These tests focus on individual methods and components without requiring
a full database setup.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from reference_db.config import ReferenceConfig
from reference_db.schema_org_importer import (
    SchemaOrgImporter,
    DownloadError,
    ParseError,
    EmbeddingError,
    LockError
)


class TestExtractId:
    """Test _extract_id helper method."""

    def test_extract_id_from_dict(self):
        """Test extracting @id from dictionary."""
        importer = SchemaOrgImporter(
            ReferenceConfig(),
            Mock()
        )

        value = {"@id": "https://schema.org/Thing"}
        result = importer._extract_id(value)
        assert result == "https://schema.org/Thing"

    def test_extract_id_from_string(self):
        """Test extracting @id from string."""
        importer = SchemaOrgImporter(
            ReferenceConfig(),
            Mock()
        )

        value = "https://schema.org/Thing"
        result = importer._extract_id(value)
        assert result == "https://schema.org/Thing"

    def test_extract_id_from_none(self):
        """Test extracting @id from None returns None."""
        importer = SchemaOrgImporter(
            ReferenceConfig(),
            Mock()
        )

        result = importer._extract_id(None)
        assert result is None

    def test_extract_id_from_invalid_dict(self):
        """Test extracting @id from dict without @id key."""
        importer = SchemaOrgImporter(
            ReferenceConfig(),
            Mock()
        )

        value = {"somekey": "value"}
        result = importer._extract_id(value)
        assert result is None


class TestURLValidation:
    """Test URL validation for security."""

    def test_https_url_accepted(self):
        """Test HTTPS URLs are accepted."""
        config = ReferenceConfig(
            schema_org_api_url="https://schema.org/version/latest/schemaorg-current-https.jsonld"
        )
        importer = SchemaOrgImporter(config, Mock())

        # Should not raise
        mock_response = Mock()
        mock_response.text = "{}"
        mock_response.raise_for_status = Mock()

        with patch('requests.get', return_value=mock_response):
            try:
                importer._download_with_retry()
            except Exception as e:
                # May fail for other reasons, but not URL validation
                assert "security" not in str(e).lower()

    def test_http_localhost_accepted(self):
        """Test HTTP localhost URLs are accepted."""
        config = ReferenceConfig(
            schema_org_api_url="http://localhost:8000/schema.jsonld"
        )
        importer = SchemaOrgImporter(config, Mock())

        mock_response = Mock()
        mock_response.text = "{}"
        mock_response.raise_for_status = Mock()

        with patch('requests.get', return_value=mock_response):
            try:
                importer._download_with_retry()
            except Exception as e:
                assert "security" not in str(e).lower()

    def test_http_127_accepted(self):
        """Test HTTP 127.0.0.1 URLs are accepted."""
        config = ReferenceConfig(
            schema_org_api_url="http://127.0.0.1:8000/schema.jsonld"
        )
        importer = SchemaOrgImporter(config, Mock())

        mock_response = Mock()
        mock_response.text = "{}"
        mock_response.raise_for_status = Mock()

        with patch('requests.get', return_value=mock_response):
            try:
                importer._download_with_retry()
            except Exception as e:
                assert "security" not in str(e).lower()

    def test_http_remote_rejected(self):
        """Test HTTP remote URLs are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            config = ReferenceConfig(
                schema_org_api_url="http://evil.com/schema.jsonld"
            )

        error_msg = str(exc_info.value).lower()
        assert "security" in error_msg or "https" in error_msg


class TestRetryLogic:
    """Test exponential backoff retry logic."""

    def test_retry_exponential_backoff(self):
        """Test retry uses exponential backoff."""
        config = ReferenceConfig(retry_count=3)
        importer = SchemaOrgImporter(config, Mock())

        call_times = []

        def mock_get(*args, **kwargs):
            call_times.append(datetime.now())
            raise Exception("Network error")

        with patch('requests.get', side_effect=mock_get):
            with patch('time.sleep') as mock_sleep:
                with pytest.raises(DownloadError):
                    importer._download_with_retry()

                # Should sleep 1s, 2s (exponential backoff)
                assert mock_sleep.call_count == 2
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert sleep_calls == [1, 2]

    def test_retry_count_configurable(self):
        """Test retry count is configurable."""
        config = ReferenceConfig(retry_count=5)
        importer = SchemaOrgImporter(config, Mock())

        with patch('requests.get', side_effect=Exception("Network error")):
            with patch('time.sleep'):
                with pytest.raises(DownloadError) as exc_info:
                    importer._download_with_retry()

                assert "5 attempts" in str(exc_info.value)


class TestBatchProcessing:
    """Test batch processing configuration."""

    def test_batch_size_configurable(self):
        """Test batch size is configurable."""
        config = ReferenceConfig(batch_size=50)
        importer = SchemaOrgImporter(config, Mock())

        assert config.batch_size == 50

    def test_batch_size_validation(self):
        """Test batch size validation."""
        # Too large
        with pytest.raises(Exception):  # Pydantic ValidationError
            ReferenceConfig(batch_size=5000)

        # Too small
        with pytest.raises(Exception):
            ReferenceConfig(batch_size=0)

    def test_embedding_batch_processing(self):
        """Test embeddings are generated in batches."""
        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        items = [
            {
                "@id": f"https://schema.org/Item{i}",
                "rdfs:label": f"Item{i}",
                "rdfs:comment": f"Description {i}"
            }
            for i in range(5)
        ]

        # Mock embedding generation - patch where it's used, not where it's defined
        with patch('reference_db.schema_org_importer.generate_embedding',
                  return_value=b'\x00' * (384 * 4)):  # 384 dimensions * 4 bytes per float32
            result = importer._generate_embeddings_batch(items, batch_size=2)

            assert len(result) == 5
            for item in result:
                assert item["title_embedding"] is not None
                assert item["definition_embedding"] is not None


class TestEmbeddingFields:
    """Test separate embedding generation for title and definition."""

    def test_title_and_definition_embedded_separately(self):
        """Test title and definition get separate embeddings."""
        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        items = [
            {
                "@id": "https://schema.org/Thing",
                "rdfs:label": "Thing",
                "rdfs:comment": "The most generic type"
            }
        ]

        call_count = 0
        def mock_generate_embedding(text):
            nonlocal call_count
            call_count += 1
            # Return proper sized embedding (384 dimensions * 4 bytes)
            return b'\x00' * (384 * 4)

        with patch('reference_db.schema_org_importer.generate_embedding',
                  side_effect=mock_generate_embedding):
            result = importer._generate_embeddings_batch(items)

            assert len(result) == 1
            assert result[0]["title_embedding"] is not None
            assert result[0]["definition_embedding"] is not None
            assert call_count == 2  # Called twice: once for title, once for definition

    def test_empty_fields_skip_embedding(self):
        """Test empty title or definition fields skip embedding generation."""
        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        items = [
            {
                "@id": "https://schema.org/Thing",
                "rdfs:label": "Thing",
                # No comment/definition
            }
        ]

        with patch('reference_db.schema_org_importer.generate_embedding',
                  return_value=b'\x00' * (384 * 4)) as mock_embed:
            result = importer._generate_embeddings_batch(items)

            assert len(result) == 1
            assert result[0]["title_embedding"] is not None
            assert result[0]["definition_embedding"] is None
            # Called only once for title
            assert mock_embed.call_count == 1


class TestRelationshipExtraction:
    """Test relationship extraction logic."""

    def test_extract_subclass_single(self):
        """Test extracting single subClassOf relationship."""
        item = {
            "@id": "https://schema.org/Person",
            "rdfs:subClassOf": {"@id": "https://schema.org/Thing"}
        }

        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"
        mock_manager.session = Mock()

        importer = SchemaOrgImporter(config, mock_manager)

        node_map = {
            "https://schema.org/Person": "uuid-person",
            "https://schema.org/Thing": "uuid-thing"
        }

        # This would normally be called within _insert_relationships_transaction
        # For unit test, we'll verify the logic works correctly
        subclass = item.get("rdfs:subClassOf")
        parent_id = importer._extract_id(subclass)

        assert parent_id == "https://schema.org/Thing"
        assert parent_id in node_map

    def test_extract_subclass_multiple(self):
        """Test extracting multiple subClassOf relationships."""
        item = {
            "@id": "https://schema.org/Person",
            "rdfs:subClassOf": [
                {"@id": "https://schema.org/Thing"},
                {"@id": "https://schema.org/Agent"}
            ]
        }

        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        subclass = item.get("rdfs:subClassOf")
        assert isinstance(subclass, list)
        assert len(subclass) == 2

        parent_ids = [importer._extract_id(sc) for sc in subclass]
        assert "https://schema.org/Thing" in parent_ids
        assert "https://schema.org/Agent" in parent_ids

    def test_extract_domain_includes(self):
        """Test extracting domainIncludes relationships."""
        item = {
            "@id": "https://schema.org/name",
            "schema:domainIncludes": [
                {"@id": "https://schema.org/Thing"},
                {"@id": "https://schema.org/Person"}
            ]
        }

        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        domain = item.get("schema:domainIncludes")
        assert isinstance(domain, list)

        domain_ids = [importer._extract_id(d) for d in domain]
        assert len(domain_ids) == 2

    def test_extract_range_includes(self):
        """Test extracting rangeIncludes relationships."""
        item = {
            "@id": "https://schema.org/name",
            "schema:rangeIncludes": {"@id": "https://schema.org/Text"}
        }

        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        range_val = item.get("schema:rangeIncludes")
        range_id = importer._extract_id(range_val)

        assert range_id == "https://schema.org/Text"

    def test_extract_inverse_of(self):
        """Test extracting inverseOf relationships."""
        item = {
            "@id": "https://schema.org/parent",
            "schema:inverseOf": {"@id": "https://schema.org/children"}
        }

        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        inverse = item.get("schema:inverseOf")
        inverse_id = importer._extract_id(inverse)

        assert inverse_id == "https://schema.org/children"


class TestLockFileManagement:
    """Test lock file creation and cleanup."""

    def test_lock_file_path_construction(self):
        """Test lock file path is correctly constructed."""
        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        assert importer.lock_path == "/tmp/test.db.import.lock"

    def test_lock_file_content(self):
        """Test lock file contains correct metadata."""
        import tempfile
        import os

        config = ReferenceConfig()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            mock_manager = Mock()
            mock_manager.db_path = db_path

            importer = SchemaOrgImporter(config, mock_manager)

            try:
                importer._acquire_lock()

                with open(importer.lock_path, 'r') as f:
                    lock_data = json.load(f)

                assert "pid" in lock_data
                assert "timestamp" in lock_data
                assert lock_data["pid"] == os.getpid()

            finally:
                importer._release_lock()


class TestErrorMessages:
    """Test error messages are clear and actionable."""

    def test_download_error_message(self):
        """Test download error includes retry information."""
        config = ReferenceConfig(retry_count=3)
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        with patch('requests.get', side_effect=Exception("Network timeout")):
            with patch('time.sleep'):
                with pytest.raises(DownloadError) as exc_info:
                    importer._download_with_retry()

                error_msg = str(exc_info.value)
                assert "3 attempts" in error_msg
                assert "Network timeout" in error_msg

    def test_embedding_error_includes_failed_ids(self):
        """Test embedding error includes list of failed IDs."""
        config = ReferenceConfig()
        mock_manager = Mock()
        mock_manager.db_path = "/tmp/test.db"

        importer = SchemaOrgImporter(config, mock_manager)

        items = [
            {"@id": "https://schema.org/Thing", "rdfs:label": "Thing", "rdfs:comment": "Test"}
        ]

        with patch('reference_db.schema_org_importer.generate_embedding',
                  side_effect=Exception("API error")):
            with pytest.raises(EmbeddingError) as exc_info:
                importer._generate_embeddings_batch(items)

            error_msg = str(exc_info.value)
            assert "failed" in error_msg.lower()
            assert "https://schema.org/Thing" in error_msg

    def test_lock_error_message(self):
        """Test lock error provides clear guidance."""
        import tempfile
        import os

        config = ReferenceConfig()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            mock_manager = Mock()
            mock_manager.db_path = db_path

            importer1 = SchemaOrgImporter(config, mock_manager)
            importer2 = SchemaOrgImporter(config, mock_manager)

            try:
                importer1._acquire_lock()

                with pytest.raises(LockError) as exc_info:
                    importer2._acquire_lock()

                error_msg = str(exc_info.value)
                assert "in progress" in error_msg.lower()

            finally:
                importer1._release_lock()
