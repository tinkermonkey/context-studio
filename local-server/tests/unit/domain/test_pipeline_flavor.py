"""
Unit tests for the PipelineService flavor operations.

These tests verify flavor CRUD operations using fake ports.
"""

import os
import sys
import pytest
from domain.pipeline.exceptions import PipelineNotFoundError
from domain.pipeline.services import PipelineService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_pipeline_repository import FakePipelineRepository

class TestPipelineFlavorCRUD:
    """Tests for flavor template lifecycle (create, read, update, delete)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo = FakePipelineRepository()
        self.llm = FakeLLMProvider()
        self.event_pub = FakeEventPublisher()
        self.service = PipelineService(
            pipeline_repo=self.repo,
            flavor_repo=self.repo,
            llm=self.llm,
            event_publisher=self.event_pub,
        )

    def test_create_flavor(self):
        """Create a new pipeline flavor."""
        flavor = self.service.create_flavor(
            name="Extract PDF",
            description="Template for extracting data from PDFs",
            steps=[
                {"type": "parse", "target": "pdf"},
                {"type": "extract", "selector": "table"},
            ],
        )

        assert flavor.id is not None
        assert flavor.name == "Extract PDF"
        assert flavor.description == "Template for extracting data from PDFs"
        assert flavor.steps == [
            {"type": "parse", "target": "pdf"},
            {"type": "extract", "selector": "table"},
        ]
        assert flavor.step_count == 2
        assert flavor.created_at is not None
        assert flavor.last_updated is not None

    def test_create_flavor_with_empty_steps(self):
        """Create a flavor with empty steps list."""
        flavor = self.service.create_flavor(
            name="Empty Template",
            description="A template with no steps",
            steps=[],
        )

        assert flavor.name == "Empty Template"
        assert flavor.step_count == 0
        assert flavor.steps == []

    def test_get_flavor_returns_all_fields(self):
        """Saved flavor retrieved by ID returns all fields unchanged."""
        created = self.service.create_flavor(
            name="Test Flavor",
            description="A test flavor template",
            steps=[{"type": "step1"}],
        )

        retrieved = self.service.get_flavor(created.id)

        assert retrieved.id == created.id
        assert retrieved.name == created.name
        assert retrieved.description == created.description
        assert retrieved.steps == created.steps
        assert retrieved.step_count == created.step_count
        assert retrieved.created_at == created.created_at
        assert retrieved.last_updated == created.last_updated

    def test_get_flavor_raises_if_not_found(self):
        """Getting non-existent flavor raises PipelineNotFoundError."""
        with pytest.raises(PipelineNotFoundError, match="not found"):
            self.service.get_flavor("nonexistent-id")

    def test_list_flavors(self):
        """List all pipeline flavors."""
        flavor1 = self.service.create_flavor(
            name="Flavor 1",
            description="First flavor",
            steps=[],
        )
        flavor2 = self.service.create_flavor(
            name="Flavor 2",
            description="Second flavor",
            steps=[{"type": "step"}],
        )

        flavors = self.service.list_flavors()

        assert len(flavors) == 2
        assert any(f.id == flavor1.id for f in flavors)
        assert any(f.id == flavor2.id for f in flavors)

    def test_list_flavors_empty(self):
        """List flavors when none exist."""
        flavors = self.service.list_flavors()
        assert flavors == []

    def test_update_flavor(self):
        """Update a flavor's properties."""
        original = self.service.create_flavor(
            name="Original Name",
            description="Original description",
            steps=[{"type": "old"}],
        )

        updated = self.service.update_flavor(
            flavor_id=original.id,
            name="Updated Name",
            description="Updated description",
            steps=[{"type": "new"}, {"type": "new2"}],
        )

        assert updated.id == original.id
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.steps == [{"type": "new"}, {"type": "new2"}]
        assert updated.step_count == 2
        assert updated.last_updated > original.last_updated

    def test_update_flavor_partial_fields(self):
        """Update only some flavor fields."""
        original = self.service.create_flavor(
            name="Original",
            description="Original desc",
            steps=[],
        )

        updated = self.service.update_flavor(
            flavor_id=original.id,
            name="Updated",
        )

        assert updated.name == "Updated"
        assert updated.description == "Original desc"
        assert updated.steps == []

    def test_update_flavor_not_found(self):
        """Updating non-existent flavor raises error."""
        with pytest.raises(PipelineNotFoundError):
            self.service.update_flavor(
                flavor_id="nonexistent",
                name="New Name",
            )

    def test_delete_flavor(self):
        """Delete a flavor."""
        flavor = self.service.create_flavor(
            name="To Delete",
            description="This will be deleted",
            steps=[],
        )

        self.service.delete_flavor(flavor.id)

        with pytest.raises(PipelineNotFoundError):
            self.service.get_flavor(flavor.id)

    def test_delete_flavor_not_found(self):
        """Deleting non-existent flavor raises error."""
        with pytest.raises(PipelineNotFoundError):
            self.service.delete_flavor("nonexistent-id")

    def test_flavor_step_count_calculated_correctly(self):
        """Flavor step_count is calculated from steps list."""
        flavor = self.service.create_flavor(
            name="Multi-step",
            description="Multiple steps",
            steps=[
                {"type": "parse"},
                {"type": "extract"},
                {"type": "validate"},
                {"type": "export"},
            ],
        )

        assert flavor.step_count == 4
