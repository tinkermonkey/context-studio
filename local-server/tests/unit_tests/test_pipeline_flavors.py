"""
Unit tests for pipeline flavor functionality.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.service import PipelineFlavorService
from llm.models import (
    PipelineType,
    CreatePipelineFlavorRequest,
    UpdatePipelineFlavorRequest,
    LLMConfig,
    PipelineFlavor,
)
from llm.exceptions import FlavorNotFoundError, FlavorValidationError


class TestPipelineFlavorService:
    """Test cases for PipelineFlavorService"""

    @pytest.fixture
    def flavor_service(self):
        """Create a PipelineFlavorService instance for testing"""
        return PipelineFlavorService()

    @pytest.fixture
    def sample_create_request(self):
        """Create a sample flavor creation request"""
        return CreatePipelineFlavorRequest(
            pipeline=PipelineType.SUGGEST_TERM_DEFINITION,
            title="Test Flavor",
            llm_provider="openai",
            llm_model="gpt-4",
            llm_config=LLMConfig(temperature=0.7, max_tokens=1000),
            system_prompt="Test system prompt for term definition",
            user_prompt="Test user prompt template with {term} placeholder",
        )

    @pytest.fixture
    def sample_update_request(self):
        """Create a sample flavor update request"""
        return UpdatePipelineFlavorRequest(
            title="Updated Test Flavor",
            llm_config=LLMConfig(temperature=0.5, max_tokens=1500),
            system_prompt="Updated system prompt",
            enabled=False,
        )

    @pytest.fixture
    def mock_flavor_row(self):
        """Create a mock database row for a flavor"""
        return [
            "test-flavor-id",
            "suggest_term_definition",
            "Test Flavor",
            "openai",
            "gpt-4",
            '{"temperature": 0.7, "max_tokens": 1000}',
            "Test system prompt",
            "Test user prompt",
            1,
            True,
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        ]

    @pytest.mark.asyncio
    async def test_create_flavor_success(
        self, flavor_service, sample_create_request, mock_flavor_row
    ):
        """Test successful flavor creation"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            # Mock database operations
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock no existing flavor with same title
            mock_session.execute.return_value.fetchone.side_effect = [
                None,
                mock_flavor_row,
            ]

            result = await flavor_service.create_flavor(sample_create_request)

            # Verify result
            assert result is not None
            assert isinstance(result, PipelineFlavor)
            assert result.title == "Test Flavor"
            assert result.pipeline == PipelineType.SUGGEST_TERM_DEFINITION

            # Verify database calls
            assert (
                mock_session.execute.call_count >= 2
            )  # Check existing + Insert + Select
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_flavor_duplicate_title(
        self, flavor_service, sample_create_request
    ):
        """Test flavor creation with duplicate title"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock existing flavor with same title
            mock_session.execute.return_value.fetchone.return_value = ["existing_id"]

            with pytest.raises(FlavorValidationError) as exc_info:
                await flavor_service.create_flavor(sample_create_request)

            assert "already exists for pipeline" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_flavor_success(
        self, flavor_service, sample_update_request, mock_flavor_row
    ):
        """Test successful flavor update"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock existing flavor
            updated_row = mock_flavor_row.copy()
            updated_row[2] = "Updated Test Flavor"  # title
            updated_row[9] = False  # enabled

            mock_session.execute.return_value.fetchone.side_effect = [
                mock_flavor_row,
                updated_row,
            ]

            result = await flavor_service.update_flavor(
                "test-flavor-id", sample_update_request
            )

            # Verify result
            assert result is not None
            assert isinstance(result, PipelineFlavor)

            # Verify database calls
            assert (
                mock_session.execute.call_count >= 2
            )  # Get existing + Update + Get updated
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_nonexistent_flavor(
        self, flavor_service, sample_update_request
    ):
        """Test updating non-existent flavor"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock no existing flavor
            mock_session.execute.return_value.fetchone.return_value = None

            with pytest.raises(FlavorNotFoundError) as exc_info:
                await flavor_service.update_flavor(
                    "nonexistent-id", sample_update_request
                )

            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_default_flavor_title_forbidden(
        self, flavor_service, sample_update_request
    ):
        """Test that renaming default flavor is forbidden"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock existing default flavor
            default_row = [
                "default-id",
                "suggest_term_definition",
                "Default",
                "openai",
                "gpt-3.5-turbo",
                '{"temperature": 0.0}',
                "System prompt",
                "User prompt",
                1,
                True,
                datetime.utcnow(),
                datetime.utcnow(),
            ]
            mock_session.execute.return_value.fetchone.return_value = default_row

            # Try to rename default flavor
            rename_request = UpdatePipelineFlavorRequest(title="New Name")

            with pytest.raises(FlavorValidationError) as exc_info:
                await flavor_service.update_flavor("default-id", rename_request)

            assert "Cannot rename the Default flavor" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_flavor_success(self, flavor_service):
        """Test successful flavor deletion"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock existing non-default flavor
            mock_session.execute.return_value.fetchone.return_value = ["Test Flavor"]
            mock_session.execute.return_value.rowcount = 1

            result = await flavor_service.delete_flavor("test-flavor-id")

            # Verify result
            assert result is True

            # Verify database calls
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_default_flavor_forbidden(self, flavor_service):
        """Test that deleting default flavor is forbidden"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock existing default flavor
            mock_session.execute.return_value.fetchone.return_value = ["Default"]

            with pytest.raises(FlavorValidationError) as exc_info:
                await flavor_service.delete_flavor("default-id")

            assert "Cannot delete the Default flavor" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_flavor(self, flavor_service):
        """Test deleting non-existent flavor"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock no existing flavor
            mock_session.execute.return_value.fetchone.return_value = None

            with pytest.raises(FlavorNotFoundError) as exc_info:
                await flavor_service.delete_flavor("nonexistent-id")

            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_flavor_by_id_success(self, flavor_service, mock_flavor_row):
        """Test successfully getting a flavor by ID"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.fetchone.return_value = mock_flavor_row

            result = await flavor_service.get_flavor_by_id("test-flavor-id")

            # Verify result
            assert result is not None
            assert isinstance(result, PipelineFlavor)
            assert result.id == "test-flavor-id"
            assert result.title == "Test Flavor"

    @pytest.mark.asyncio
    async def test_get_flavor_by_id_not_found(self, flavor_service):
        """Test getting non-existent flavor by ID"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.fetchone.return_value = None

            with pytest.raises(FlavorNotFoundError) as exc_info:
                await flavor_service.get_flavor_by_id("nonexistent-id")

            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_flavor_by_title_success(self, flavor_service, mock_flavor_row):
        """Test successfully getting a flavor by title"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.fetchone.return_value = mock_flavor_row

            result = await flavor_service.get_flavor_by_title(
                PipelineType.SUGGEST_TERM_DEFINITION, "Test Flavor"
            )

            # Verify result
            assert result is not None
            assert isinstance(result, PipelineFlavor)
            assert result.title == "Test Flavor"
            assert result.pipeline == PipelineType.SUGGEST_TERM_DEFINITION

    @pytest.mark.asyncio
    async def test_get_flavor_by_title_not_found(self, flavor_service):
        """Test getting non-existent flavor by title"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.fetchone.return_value = None

            with pytest.raises(FlavorNotFoundError) as exc_info:
                await flavor_service.get_flavor_by_title(
                    PipelineType.SUGGEST_TERM_DEFINITION, "Nonexistent Flavor"
                )

            assert "not found for pipeline" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_flavors_all(self, flavor_service, mock_flavor_row):
        """Test listing all flavors"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.fetchall.return_value = [
                mock_flavor_row,
                mock_flavor_row,
            ]

            result = await flavor_service.list_flavors()

            # Verify result (includes default flavors + user flavors)
            assert isinstance(result, list)
            assert len(result) >= 2  # At least default flavors for each pipeline type
            # The exact count depends on how many default flavors are generated

    @pytest.mark.asyncio
    async def test_list_flavors_by_pipeline(self, flavor_service, mock_flavor_row):
        """Test listing flavors filtered by pipeline"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.fetchall.return_value = [mock_flavor_row]

            result = await flavor_service.list_flavors(
                PipelineType.SUGGEST_TERM_DEFINITION
            )

            # Verify result (includes default flavor + user flavors)
            assert isinstance(result, list)
            assert len(result) >= 1  # At least the default flavor
            # First flavor should be default, then user flavors
            assert any(flavor.title == "Default" for flavor in result)

    @pytest.mark.asyncio
    async def test_get_enabled_flavors(self, flavor_service, mock_flavor_row):
        """Test getting enabled flavors for a pipeline"""
        with patch("llm.flavor_service.get_pipeline_session") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.fetchall.return_value = [mock_flavor_row]

            result = await flavor_service.get_enabled_flavors(
                PipelineType.SUGGEST_TERM_DEFINITION
            )

            # Verify result (includes default flavor + enabled user flavors)
            assert isinstance(result, list)
            assert len(result) >= 1  # At least the default flavor
            # All returned flavors should be enabled
            assert all(flavor.enabled for flavor in result)

    @pytest.mark.asyncio
    async def test_get_default_flavor_exists(self, flavor_service, mock_flavor_row):
        """Test getting default flavor when it exists"""
        # This method doesn't use database - it uses DefaultFlavorProvider
        result = await flavor_service.get_default_flavor(
            PipelineType.SUGGEST_TERM_DEFINITION
        )

        # Verify result
        assert result is not None
        assert result.title == "Default"
        assert result.pipeline == PipelineType.SUGGEST_TERM_DEFINITION

    @pytest.mark.asyncio
    async def test_row_to_flavor_conversion(self, flavor_service, mock_flavor_row):
        """Test database row to PipelineFlavor model conversion"""
        result = flavor_service._row_to_flavor(mock_flavor_row)

        # Verify conversion
        assert isinstance(result, PipelineFlavor)
        assert result.id == "test-flavor-id"
        assert result.pipeline == PipelineType.SUGGEST_TERM_DEFINITION
        assert result.title == "Test Flavor"
        assert result.llm_provider == "openai"
        assert result.llm_model == "gpt-4"
        assert result.llm_config.temperature == 0.7
        assert result.llm_config.max_tokens == 1000
        assert result.enabled is True

    def test_validation_create_request_invalid_title(self):
        """Test validation of create request with invalid title"""
        with pytest.raises(ValueError) as exc_info:
            CreatePipelineFlavorRequest(
                pipeline=PipelineType.SUGGEST_TERM_DEFINITION,
                title="default",  # Reserved name
                llm_provider="openai",
                llm_model="gpt-4",
                llm_config=LLMConfig(temperature=0.7),
                system_prompt="Test system prompt",
                user_prompt="Test user prompt",
            )

        assert "reserved name" in str(exc_info.value)

    def test_validation_update_request_invalid_title(self):
        """Test validation of update request with invalid title"""
        with pytest.raises(ValueError) as exc_info:
            UpdatePipelineFlavorRequest(title="default")  # Reserved name

        assert "reserved name" in str(exc_info.value)

    def test_llm_config_validation(self):
        """Test LLM configuration validation"""
        # Valid config
        config = LLMConfig(temperature=0.7, max_tokens=1000, top_p=0.9)
        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.top_p == 0.9

        # Invalid temperature (too high)
        with pytest.raises(ValueError):
            LLMConfig(temperature=3.0)

        # Invalid temperature (negative)
        with pytest.raises(ValueError):
            LLMConfig(temperature=-1.0)

        # Invalid top_p (too high)
        with pytest.raises(ValueError):
            LLMConfig(top_p=1.5)


class TestPipelineFlavorValidation:
    """Test cases for pipeline flavor validation"""

    def test_pipeline_type_enum(self):
        """Test pipeline type enumeration"""
        assert PipelineType.SUGGEST_TERM_DEFINITION == "suggest_term_definition"
        assert PipelineType.SUGGEST_LAYER_DEFINITION == "suggest_layer_definition"
        assert PipelineType.SUGGEST_DOMAIN_DEFINITION == "suggest_domain_definition"

    def test_create_request_field_validation(self):
        """Test field validation in create request"""
        # Test minimum length validation
        with pytest.raises(ValueError):
            CreatePipelineFlavorRequest(
                pipeline=PipelineType.SUGGEST_TERM_DEFINITION,
                title="",  # Too short
                llm_provider="openai",
                llm_model="gpt-4",
                llm_config=LLMConfig(),
                system_prompt="Test",
                user_prompt="Test",
            )

        # Test maximum length validation
        with pytest.raises(ValueError):
            CreatePipelineFlavorRequest(
                pipeline=PipelineType.SUGGEST_TERM_DEFINITION,
                title="x" * 201,  # Too long
                llm_provider="openai",
                llm_model="gpt-4",
                llm_config=LLMConfig(),
                system_prompt="Test",
                user_prompt="Test",
            )

    def test_llm_config_defaults(self):
        """Test LLM configuration defaults"""
        config = LLMConfig()
        assert config.temperature == 0.0
        assert config.top_p is None
        assert config.top_k is None
        assert config.max_tokens is None
        assert config.frequency_penalty is None
        assert config.presence_penalty is None
