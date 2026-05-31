"""
Tests for PipelineConfigurationRegistry restart safety.

These tests document the contract: after a server restart, a pipeline run
can safely resolve its (slug, version) reference because configurations
are deterministically re-registered from code.
"""


from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import PipelineConfigurationRegistry


class TestRegistryRestartSafety:
    """Tests documenting restart safety of configuration registry."""

    def test_deterministic_registration_order(self):
        """
        Configurations registered in the same order always produce the same version numbers.

        This simulates two sequential server startups: each creates a fresh registry
        and registers the same configs in the same order. Version numbers remain stable.
        """
        # Startup 1: initial server start
        registry_startup_1 = PipelineConfigurationRegistry()
        registry_startup_1.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            {"model": "claude-opus-4"},
        )
        registry_startup_1.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            {"model": "claude-opus-4-20250101"},
        )
        v3_startup_1 = registry_startup_1.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            {"model": "claude-opus-4-20250115"},
        )

        # Simulate a run created during startup 1, referencing v3
        registry_startup_1.mark_version_referenced(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            3,
        )

        # Startup 2: server restarts, registry repopulated from code
        registry_startup_2 = PipelineConfigurationRegistry()
        registry_startup_2.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            {"model": "claude-opus-4"},
        )
        registry_startup_2.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            {"model": "claude-opus-4-20250101"},
        )
        v3_startup_2 = registry_startup_2.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            {"model": "claude-opus-4-20250115"},
        )

        # The run from startup 1 can now resolve v3 in startup 2
        assert v3_startup_1.version == v3_startup_2.version == 3
        assert v3_startup_1.config == v3_startup_2.config

        # Verify the registry can still locate v3
        resolved = registry_startup_2.get_version(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            3,
        )
        assert resolved is not None
        assert resolved.version == 3

    def test_configuration_always_resolvable_after_restart(self):
        """
        A PipelineRun created with (slug, version=N) can always be re-executed
        or queried after a server restart because version N is regenerated.
        """
        # Simulate initial run creation
        registry = PipelineConfigurationRegistry()
        for i in range(5):
            registry.register(
                PipelineType.SCHEMA_EXTRACTION,
                "default",
                "schema-default",
                {"iteration": i},
            )

        # Run created during initial startup references version 3
        config_at_run_time = registry.get_version(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "schema-default",
            3,
        )
        assert config_at_run_time is not None

        # Simulate server restart: fresh registry
        restarted_registry = PipelineConfigurationRegistry()
        for i in range(5):
            restarted_registry.register(
                PipelineType.SCHEMA_EXTRACTION,
                "default",
                "schema-default",
                {"iteration": i},
            )

        # The same run can still resolve its config after restart
        config_after_restart = restarted_registry.get_version(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "schema-default",
            3,
        )
        assert config_after_restart is not None
        assert config_after_restart.config == config_at_run_time.config

    def test_new_versions_can_be_registered_when_old_version_referenced(self):
        """
        Creating a new version is always allowed, even if an older version is referenced.
        This is the normal flow: v1 is used by a run, then v2 is registered for new runs.
        """
        registry = PipelineConfigurationRegistry()

        # Create v1
        v1 = registry.register(
            PipelineType.SCHEMA_NODE_GROUNDING,
            "default",
            "grounding-default",
            {"top_n": 10},
        )
        assert v1.version == 1

        # Mark v1 as referenced by a run
        registry.mark_version_referenced(
            PipelineType.SCHEMA_NODE_GROUNDING,
            "default",
            "grounding-default",
            1,
        )

        # Creating v2 is allowed (normal flow)
        v2 = registry.register(
            PipelineType.SCHEMA_NODE_GROUNDING,
            "default",
            "grounding-default",
            {"top_n": 20},
        )
        assert v2.version == 2

        # Both v1 and v2 are now available
        retrieved_v1 = registry.get_version(
            PipelineType.SCHEMA_NODE_GROUNDING,
            "default",
            "grounding-default",
            1,
        )
        retrieved_v2 = registry.get_version(
            PipelineType.SCHEMA_NODE_GROUNDING,
            "default",
            "grounding-default",
            2,
        )
        assert retrieved_v1 is not None
        assert retrieved_v2 is not None
        assert retrieved_v1.config != retrieved_v2.config

    def test_configuration_immutability_by_architecture(self):
        """
        Immutability is enforced by architecture: each register() call creates
        a new version. You can never get back the same version object and mutate it.
        """
        registry = PipelineConfigurationRegistry()

        # Register v1
        registry.register(
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            "default",
            "refinement-default",
            {"param": "value1"},
        )

        # Mark it as referenced
        registry.mark_version_referenced(
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            "default",
            "refinement-default",
            1,
        )

        # Register "another update" with same slug
        v2 = registry.register(
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            "default",
            "refinement-default",
            {"param": "value2"},
        )

        # Verify v1 was never mutated - it got a new version number (v2)
        assert v2.version == 2
        assert v2.config["param"] == "value2"

        # Original v1 is still there and unchanged
        v1_again = registry.get_version(
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            "default",
            "refinement-default",
            1,
        )
        assert v1_again is not None
        assert v1_again.config["param"] == "value1"

        # v1 and v2 are distinct versions
        assert v1_again.version == 1
        assert v1_again.config != v2.config
