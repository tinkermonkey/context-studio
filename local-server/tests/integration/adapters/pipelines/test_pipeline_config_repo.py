"""
Integration tests for PipelineConfigurationRepository.

Tests CRUD operations, soft-delete, config_ref uniqueness, and error handling.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.persistence.sqlite.operations.models import OperationsBase
from adapters.persistence.sqlite.pipeline_config_repo import (
    PipelineConfigurationRepository,
)
from domain.pipelines.exceptions import PipelineStorageError


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OperationsBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def repo(session_factory):
    return PipelineConfigurationRepository(session_factory)


def _make_config(repo, name="My Config", pipeline_type="individual_extraction", impl_id="default"):
    return repo.create(
        pipeline_type=pipeline_type,
        implementation_id=impl_id,
        name=name,
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        user_prompt_template="Extract: {text}",
    )


class TestPipelineConfigurationRepositoryCreate:
    def test_create_returns_record_with_id(self, repo):
        record = _make_config(repo)
        assert record.id is not None
        assert len(record.id) == 36  # UUID format

    def test_create_sets_version_to_1(self, repo):
        record = _make_config(repo)
        assert record.version == 1

    def test_create_sets_config_ref_from_name(self, repo):
        record = _make_config(repo, name="My Config")
        assert record.config_ref.startswith("cfg_my_config")

    def test_create_persists_fields(self, repo):
        record = _make_config(repo, name="Test Config")
        assert record.name == "Test Config"
        assert record.provider == "anthropic"
        assert record.model == "claude-3-5-sonnet-20241022"
        assert record.enabled is True
        assert record.deleted_at is None

    def test_create_slug_collision_appends_suffix(self, repo):
        """Two configs whose names produce the same slug get distinct config_refs."""
        r1 = _make_config(repo, name="Test Config")
        r2 = _make_config(repo, name="Test Config!")
        assert r1.config_ref != r2.config_ref
        assert r2.config_ref.startswith("cfg_test_config")

    def test_create_no_collision_uses_clean_slug(self, repo):
        record = _make_config(repo, name="Unique Name")
        assert record.config_ref == "cfg_unique_name"

    def test_create_raises_storage_error_on_db_failure(self, repo):
        mock_session = MagicMock()
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.commit.side_effect = SQLAlchemyError("boom")
        with patch.object(repo, "_session", return_value=mock_session):
            with pytest.raises(PipelineStorageError, match="Failed to create"):
                repo.create(
                    pipeline_type="individual_extraction",
                    implementation_id="default",
                    name="Fail",
                    provider="openai",
                    model="gpt-4o",
                    user_prompt_template="Extract: {text}",
                )


class TestPipelineConfigurationRepositoryGet:
    def test_get_returns_record(self, repo):
        created = _make_config(repo)
        fetched = repo.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_returns_none_for_unknown_id(self, repo):
        assert repo.get("00000000-0000-0000-0000-000000000000") is None

    def test_get_returns_none_for_deleted_record(self, repo):
        created = _make_config(repo)
        repo.soft_delete(created.id)
        assert repo.get(created.id) is None


class TestPipelineConfigurationRepositoryUpdate:
    def test_update_increments_version(self, repo):
        created = _make_config(repo)
        updated = repo.update(
            config_id=created.id,
            name="New Name",
            provider="openai",
            model="gpt-4o",
            user_prompt_template="Updated: {text}",
        )
        assert updated.version == 2

    def test_update_persists_new_name(self, repo):
        created = _make_config(repo)
        updated = repo.update(
            config_id=created.id,
            name="Renamed",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            user_prompt_template="Extract: {text}",
        )
        assert updated.name == "Renamed"

    def test_update_returns_none_for_missing_id(self, repo):
        result = repo.update(
            config_id="00000000-0000-0000-0000-000000000000",
            name="x",
            provider="x",
            model="x",
            user_prompt_template="x",
        )
        assert result is None

    def test_update_returns_none_for_deleted_record(self, repo):
        created = _make_config(repo)
        repo.soft_delete(created.id)
        result = repo.update(
            config_id=created.id,
            name="x",
            provider="x",
            model="x",
            user_prompt_template="x",
        )
        assert result is None


class TestPipelineConfigurationRepositoryListForType:
    def test_list_for_type_returns_matching_records(self, repo):
        _make_config(repo, name="A", pipeline_type="individual_extraction")
        _make_config(repo, name="B", pipeline_type="individual_extraction")
        _make_config(repo, name="C", pipeline_type="schema_extraction")
        results = repo.list_for_type("individual_extraction", "default")
        assert len(results) == 2

    def test_list_for_type_excludes_deleted(self, repo):
        r1 = _make_config(repo, name="Keep")
        r2 = _make_config(repo, name="Delete")
        repo.soft_delete(r2.id)
        results = repo.list_for_type("individual_extraction", "default")
        ids = [r.id for r in results]
        assert r1.id in ids
        assert r2.id not in ids


class TestPipelineConfigurationRepositoryListAll:
    def test_list_all_excludes_deleted(self, repo):
        r1 = _make_config(repo, name="Keep")
        r2 = _make_config(repo, name="Delete")
        repo.soft_delete(r2.id)
        results = repo.list_all()
        ids = [r.id for r in results]
        assert r1.id in ids
        assert r2.id not in ids


class TestPipelineConfigurationRepositorySoftDelete:
    def test_soft_delete_returns_true(self, repo):
        created = _make_config(repo)
        assert repo.soft_delete(created.id) is True

    def test_soft_delete_hides_from_get(self, repo):
        created = _make_config(repo)
        repo.soft_delete(created.id)
        assert repo.get(created.id) is None

    def test_soft_delete_returns_false_for_missing(self, repo):
        assert repo.soft_delete("00000000-0000-0000-0000-000000000000") is False

    def test_soft_delete_returns_false_for_already_deleted(self, repo):
        created = _make_config(repo)
        repo.soft_delete(created.id)
        assert repo.soft_delete(created.id) is False


class TestPipelineConfigurationRepositoryListKnownConfigRefs:
    def test_includes_active_refs(self, repo):
        _make_config(repo, name="Active Config")
        refs = repo.list_known_config_refs("individual_extraction", "default")
        assert "cfg_active_config" in refs

    def test_includes_deleted_refs(self, repo):
        created = _make_config(repo, name="Gone Config")
        repo.soft_delete(created.id)
        refs = repo.list_known_config_refs("individual_extraction", "default")
        assert "cfg_gone_config" in refs
