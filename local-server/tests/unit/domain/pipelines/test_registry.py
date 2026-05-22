"""
Unit tests for domain.pipelines.registry

Tests registry invariants: no duplicate registration, immutable configurations,
type enumeration.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import pytest
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
    PipelineTypeRegistry,
)
from domain.pipelines.entities import PipelineType


class TestPipelineTypeRegistry:
    """Tests for PipelineTypeRegistry."""

    def test_list_all_types(self):
        """Test listing all pipeline types."""
        types = PipelineTypeRegistry.list_types()
        assert len(types) == 5
        type_names = [t.pipeline_type for t in types]
        assert PipelineType.INDIVIDUAL_EXTRACTION in type_names
        assert PipelineType.SCHEMA_EXTRACTION in type_names

    def test_get_type_definition(self):
        """Test getting a specific type definition."""
        defn = PipelineTypeRegistry.get_type(PipelineType.INDIVIDUAL_EXTRACTION)
        assert defn is not None
        assert defn.pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION
        assert "text" in defn.input_contract
        assert "triples" in defn.output_contract

    def test_is_valid_type(self):
        """Test validation of pipeline types."""
        assert PipelineTypeRegistry.is_valid_type(PipelineType.INDIVIDUAL_EXTRACTION)
        assert PipelineTypeRegistry.is_valid_type(PipelineType.SCHEMA_EXTRACTION)

    def test_type_has_contracts(self):
        """Test that all types have input and output contracts."""
        for type_def in PipelineTypeRegistry.list_types():
            assert type_def.input_contract is not None
            assert type_def.output_contract is not None
            assert isinstance(type_def.input_contract, dict)
            assert isinstance(type_def.output_contract, dict)


class TestPipelineImplementationRegistry:
    """Tests for PipelineImplementationRegistry."""

    def test_register_implementation(self):
        """Test registering an implementation."""
        registry = PipelineImplementationRegistry()

        class DummyImpl:
            pass

        registry.register_impl(PipelineType.INDIVIDUAL_EXTRACTION, "dummy", DummyImpl)
        retrieved = registry.get(PipelineType.INDIVIDUAL_EXTRACTION, "dummy")
        assert retrieved is DummyImpl

    def test_register_duplicate_raises_error(self):
        """Test that registering a duplicate raises ValueError."""
        registry = PipelineImplementationRegistry()

        class Impl1:
            pass

        class Impl2:
            pass

        registry.register_impl(PipelineType.INDIVIDUAL_EXTRACTION, "impl", Impl1)
        with pytest.raises(ValueError):
            registry.register_impl(PipelineType.INDIVIDUAL_EXTRACTION, "impl", Impl2)

    def test_decorator_registration(self):
        """Test decorator-based implementation registration."""
        registry = PipelineImplementationRegistry()

        @registry.register(PipelineType.INDIVIDUAL_EXTRACTION, "decorated")
        class DecoratedImpl:
            pass

        retrieved = registry.get(PipelineType.INDIVIDUAL_EXTRACTION, "decorated")
        assert retrieved is DecoratedImpl

    def test_list_by_type(self):
        """Test listing implementations by pipeline type."""
        registry = PipelineImplementationRegistry()

        class Impl1:
            pass

        class Impl2:
            pass

        class Impl3:
            pass

        registry.register_impl(PipelineType.INDIVIDUAL_EXTRACTION, "impl1", Impl1)
        registry.register_impl(PipelineType.INDIVIDUAL_EXTRACTION, "impl2", Impl2)
        registry.register_impl(PipelineType.SCHEMA_EXTRACTION, "impl3", Impl3)

        impls = registry.list_by_type(PipelineType.INDIVIDUAL_EXTRACTION)
        assert len(impls) == 2
        assert "impl1" in impls
        assert "impl2" in impls
        assert impls["impl1"] is Impl1
        assert impls["impl2"] is Impl2


class TestPipelineConfigurationRegistry:
    """Tests for PipelineConfigurationRegistry."""

    def test_register_configuration(self):
        """Test registering a configuration."""
        registry = PipelineConfigurationRegistry()

        config = {"model": "gpt-4", "temperature": 0.7}
        version = registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "impl-default",
            "extraction-default",
            config,
        )

        assert version.version == 1
        assert version.config == config

    def test_get_latest_version(self):
        """Test retrieving the latest version of a configuration."""
        registry = PipelineConfigurationRegistry()

        config1 = {"model": "gpt-4", "temperature": 0.7}
        config2 = {"model": "gpt-4-turbo", "temperature": 0.5}

        registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "impl-default",
            "extraction-default",
            config1,
        )
        v2 = registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "impl-default",
            "extraction-default",
            config2,
        )

        latest = registry.get_latest(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "impl-default",
            "extraction-default",
        )

        assert latest is not None
        assert latest.version == 2
        assert latest.config == config2

    def test_get_specific_version(self):
        """Test retrieving a specific version of a configuration."""
        registry = PipelineConfigurationRegistry()

        config1 = {"model": "gpt-4"}
        registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "impl-default",
            "extraction-default",
            config1,
        )

        v1 = registry.get_version(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "impl-default",
            "extraction-default",
            1,
        )

        assert v1 is not None
        assert v1.version == 1
        assert v1.config == config1

    def test_list_all_versions(self):
        """Test listing all versions of a configuration."""
        registry = PipelineConfigurationRegistry()

        for i in range(3):
            registry.register(
                PipelineType.INDIVIDUAL_EXTRACTION,
                "impl-default",
                "extraction-default",
                {"model": f"model-{i}"},
            )

        versions = registry.list_all_versions(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "impl-default",
            "extraction-default",
        )

        assert len(versions) == 3
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[2].version == 3

    def test_configuration_defensively_copied(self):
        """Test that configuration values are defensively copied on registration."""
        registry = PipelineConfigurationRegistry()

        config = {"model": "gpt-4"}
        version = registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "impl-default",
            "extraction-default",
            config,
        )

        # Modify the original dict
        config["model"] = "gpt-4-turbo"

        # Version's config should still be gpt-4
        assert version.config["model"] == "gpt-4"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
