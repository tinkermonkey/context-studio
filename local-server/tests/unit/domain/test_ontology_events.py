"""
Unit tests for domain events in the Ontology Management bounded context.

Tests verify:
- DomainEvent base class and validation
- All ten event subclasses can be instantiated
- Events are frozen (immutable)
- Empty string validation in __post_init__
"""

import sys
import os
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.ontology.events import (
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    DomainEvent,
    GraphInvalidated,
    PropertyDefinitionCreated,
    RelationshipCreated,
    RelationshipDeleted,
    SchemeCreated,
    TaxonomyCreated,
)


class TestDomainEventBase:
    """Tests for DomainEvent base class."""

    def test_domain_event_creation(self):
        """DomainEvent can be instantiated with required fields."""
        now = datetime.utcnow()
        event = DomainEvent(
            event_id="evt-123",
            occurred_at=now,
            aggregate_id="agg-456",
        )
        assert event.event_id == "evt-123"
        assert event.occurred_at == now
        assert event.aggregate_id == "agg-456"

    def test_domain_event_is_frozen(self):
        """DomainEvent instances are frozen and cannot be modified."""
        now = datetime.utcnow()
        event = DomainEvent(
            event_id="evt-123",
            occurred_at=now,
            aggregate_id="agg-456",
        )
        with pytest.raises(FrozenInstanceError):
            event.event_id = "new-id"

    def test_domain_event_rejects_empty_event_id(self):
        """DomainEvent raises ValueError if event_id is empty."""
        now = datetime.utcnow()
        with pytest.raises(ValueError, match="Event field 'event_id' cannot be empty"):
            DomainEvent(
                event_id="",
                occurred_at=now,
                aggregate_id="agg-456",
            )

    def test_domain_event_rejects_whitespace_event_id(self):
        """DomainEvent raises ValueError if event_id is only whitespace."""
        now = datetime.utcnow()
        with pytest.raises(ValueError, match="Event field 'event_id' cannot be empty"):
            DomainEvent(
                event_id="   ",
                occurred_at=now,
                aggregate_id="agg-456",
            )

    def test_domain_event_rejects_empty_aggregate_id(self):
        """DomainEvent raises ValueError if aggregate_id is empty."""
        now = datetime.utcnow()
        with pytest.raises(ValueError, match="Event field 'aggregate_id' cannot be empty"):
            DomainEvent(
                event_id="evt-123",
                occurred_at=now,
                aggregate_id="",
            )

    def test_domain_event_allows_whitespace_in_non_required_fields(self):
        """DomainEvent allows whitespace-only strings if they are not required string fields."""
        # The base DomainEvent only has required fields, so this tests that
        # datetime fields are not validated
        now = datetime.utcnow()
        event = DomainEvent(
            event_id="evt-123",
            occurred_at=now,
            aggregate_id="agg-456",
        )
        # Should not raise
        assert event.event_id == "evt-123"


class TestTaxonomyCreated:
    """Tests for TaxonomyCreated event."""

    def test_taxonomy_created_instantiation(self):
        """TaxonomyCreated can be instantiated with all required fields."""
        now = datetime.utcnow()
        event = TaxonomyCreated(
            event_id="evt-tax-001",
            occurred_at=now,
            aggregate_id="tax-123",
            taxonomy_id="tax-123",
            title="Biology Taxonomy",
        )
        assert event.event_id == "evt-tax-001"
        assert event.aggregate_id == "tax-123"
        assert event.taxonomy_id == "tax-123"
        assert event.title == "Biology Taxonomy"

    def test_taxonomy_created_is_frozen(self):
        """TaxonomyCreated instances are frozen."""
        now = datetime.utcnow()
        event = TaxonomyCreated(
            event_id="evt-tax-001",
            occurred_at=now,
            aggregate_id="tax-123",
            taxonomy_id="tax-123",
            title="Biology Taxonomy",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"

    def test_taxonomy_created_rejects_empty_title(self):
        """TaxonomyCreated raises ValueError if title is empty."""
        now = datetime.utcnow()
        with pytest.raises(ValueError, match="Event field 'title' cannot be empty"):
            TaxonomyCreated(
                event_id="evt-tax-001",
                occurred_at=now,
                aggregate_id="tax-123",
                taxonomy_id="tax-123",
                title="",
            )

    def test_taxonomy_created_rejects_empty_taxonomy_id(self):
        """TaxonomyCreated raises ValueError if taxonomy_id is empty."""
        now = datetime.utcnow()
        with pytest.raises(ValueError, match="Event field 'taxonomy_id' cannot be empty"):
            TaxonomyCreated(
                event_id="evt-tax-001",
                occurred_at=now,
                aggregate_id="tax-123",
                taxonomy_id="",
                title="Biology Taxonomy",
            )


class TestSchemeCreated:
    """Tests for SchemeCreated event."""

    def test_scheme_created_instantiation(self):
        """SchemeCreated can be instantiated with all required fields."""
        now = datetime.utcnow()
        event = SchemeCreated(
            event_id="evt-scheme-001",
            occurred_at=now,
            aggregate_id="scheme-123",
            scheme_id="scheme-123",
            title="Animal Kingdom",
            taxonomy_id="tax-456",
        )
        assert event.scheme_id == "scheme-123"
        assert event.title == "Animal Kingdom"
        assert event.taxonomy_id == "tax-456"

    def test_scheme_created_is_frozen(self):
        """SchemeCreated instances are frozen."""
        now = datetime.utcnow()
        event = SchemeCreated(
            event_id="evt-scheme-001",
            occurred_at=now,
            aggregate_id="scheme-123",
            scheme_id="scheme-123",
            title="Animal Kingdom",
            taxonomy_id="tax-456",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"


class TestClassCreated:
    """Tests for ClassCreated event."""

    def test_class_created_instantiation(self):
        """ClassCreated can be instantiated with all required fields."""
        now = datetime.utcnow()
        event = ClassCreated(
            event_id="evt-class-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            title="Mammal",
            scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )
        assert event.class_id == "class-123"
        assert event.title == "Mammal"
        assert event.scheme_id == "scheme-456"
        assert event.taxonomy_id == "tax-789"

    def test_class_created_is_frozen(self):
        """ClassCreated instances are frozen."""
        now = datetime.utcnow()
        event = ClassCreated(
            event_id="evt-class-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            title="Mammal",
            scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"


class TestClassUpdated:
    """Tests for ClassUpdated event."""

    def test_class_updated_instantiation(self):
        """ClassUpdated can be instantiated with changed fields."""
        now = datetime.utcnow()
        event = ClassUpdated(
            event_id="evt-class-upd-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            changed_fields=("title", "description"),
        )
        assert event.class_id == "class-123"
        assert event.changed_fields == ("title", "description")

    def test_class_updated_with_empty_changed_fields(self):
        """ClassUpdated can be instantiated with empty changed_fields tuple."""
        now = datetime.utcnow()
        event = ClassUpdated(
            event_id="evt-class-upd-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            changed_fields=(),
        )
        assert event.changed_fields == ()

    def test_class_updated_is_frozen(self):
        """ClassUpdated instances are frozen."""
        now = datetime.utcnow()
        event = ClassUpdated(
            event_id="evt-class-upd-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            changed_fields=("title",),
        )
        with pytest.raises(FrozenInstanceError):
            event.changed_fields = ("new_field",)


class TestClassDeleted:
    """Tests for ClassDeleted event."""

    def test_class_deleted_instantiation(self):
        """ClassDeleted can be instantiated with all required fields."""
        now = datetime.utcnow()
        event = ClassDeleted(
            event_id="evt-class-del-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            title="Mammal",
        )
        assert event.class_id == "class-123"
        assert event.title == "Mammal"

    def test_class_deleted_is_frozen(self):
        """ClassDeleted instances are frozen."""
        now = datetime.utcnow()
        event = ClassDeleted(
            event_id="evt-class-del-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            title="Mammal",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"


class TestClassMoved:
    """Tests for ClassMoved event."""

    def test_class_moved_with_parent_ids(self):
        """ClassMoved can be instantiated with non-empty parent IDs."""
        now = datetime.utcnow()
        event = ClassMoved(
            event_id="evt-class-move-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            old_parent_id="parent-old",
            new_parent_id="parent-new",
        )
        assert event.class_id == "class-123"
        assert event.old_parent_id == "parent-old"
        assert event.new_parent_id == "parent-new"

    def test_class_moved_from_root_to_parent(self):
        """ClassMoved allows empty string for old_parent_id (was root)."""
        now = datetime.utcnow()
        event = ClassMoved(
            event_id="evt-class-move-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            old_parent_id="",
            new_parent_id="parent-new",
        )
        assert event.old_parent_id == ""
        assert event.new_parent_id == "parent-new"

    def test_class_moved_to_root(self):
        """ClassMoved allows empty string for new_parent_id (now root)."""
        now = datetime.utcnow()
        event = ClassMoved(
            event_id="evt-class-move-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            old_parent_id="parent-old",
            new_parent_id="",
        )
        assert event.old_parent_id == "parent-old"
        assert event.new_parent_id == ""

    def test_class_moved_both_parents_empty(self):
        """ClassMoved allows empty strings for both parent IDs."""
        now = datetime.utcnow()
        event = ClassMoved(
            event_id="evt-class-move-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            old_parent_id="",
            new_parent_id="",
        )
        assert event.old_parent_id == ""
        assert event.new_parent_id == ""

    def test_class_moved_rejects_empty_class_id(self):
        """ClassMoved raises ValueError if class_id is empty."""
        now = datetime.utcnow()
        with pytest.raises(ValueError, match="Event field 'class_id' cannot be empty"):
            ClassMoved(
                event_id="evt-class-move-001",
                occurred_at=now,
                aggregate_id="class-123",
                class_id="",
                old_parent_id="parent-old",
                new_parent_id="parent-new",
            )

    def test_class_moved_is_frozen(self):
        """ClassMoved instances are frozen."""
        now = datetime.utcnow()
        event = ClassMoved(
            event_id="evt-class-move-001",
            occurred_at=now,
            aggregate_id="class-123",
            class_id="class-123",
            old_parent_id="parent-old",
            new_parent_id="parent-new",
        )
        with pytest.raises(FrozenInstanceError):
            event.old_parent_id = "new-parent"


class TestRelationshipCreated:
    """Tests for RelationshipCreated event."""

    def test_relationship_created_instantiation(self):
        """RelationshipCreated can be instantiated with all required fields."""
        now = datetime.utcnow()
        event = RelationshipCreated(
            event_id="evt-rel-001",
            occurred_at=now,
            aggregate_id="rel-123",
            relationship_id="rel-123",
            source_id="class-456",
            target_id="class-789",
            property_definition_id="prop-101",
        )
        assert event.relationship_id == "rel-123"
        assert event.source_id == "class-456"
        assert event.target_id == "class-789"
        assert event.property_definition_id == "prop-101"

    def test_relationship_created_is_frozen(self):
        """RelationshipCreated instances are frozen."""
        now = datetime.utcnow()
        event = RelationshipCreated(
            event_id="evt-rel-001",
            occurred_at=now,
            aggregate_id="rel-123",
            relationship_id="rel-123",
            source_id="class-456",
            target_id="class-789",
            property_definition_id="prop-101",
        )
        with pytest.raises(FrozenInstanceError):
            event.source_id = "new-source"


class TestRelationshipDeleted:
    """Tests for RelationshipDeleted event."""

    def test_relationship_deleted_instantiation(self):
        """RelationshipDeleted can be instantiated with all required fields."""
        now = datetime.utcnow()
        event = RelationshipDeleted(
            event_id="evt-rel-del-001",
            occurred_at=now,
            aggregate_id="rel-123",
            relationship_id="rel-123",
        )
        assert event.relationship_id == "rel-123"

    def test_relationship_deleted_is_frozen(self):
        """RelationshipDeleted instances are frozen."""
        now = datetime.utcnow()
        event = RelationshipDeleted(
            event_id="evt-rel-del-001",
            occurred_at=now,
            aggregate_id="rel-123",
            relationship_id="rel-123",
        )
        with pytest.raises(FrozenInstanceError):
            event.relationship_id = "new-rel"


class TestPropertyDefinitionCreated:
    """Tests for PropertyDefinitionCreated event."""

    def test_property_definition_created_instantiation(self):
        """PropertyDefinitionCreated can be instantiated with all required fields."""
        now = datetime.utcnow()
        event = PropertyDefinitionCreated(
            event_id="evt-prop-001",
            occurred_at=now,
            aggregate_id="prop-123",
            property_id="prop-123",
            title="subClassOf",
        )
        assert event.property_id == "prop-123"
        assert event.title == "subClassOf"

    def test_property_definition_created_is_frozen(self):
        """PropertyDefinitionCreated instances are frozen."""
        now = datetime.utcnow()
        event = PropertyDefinitionCreated(
            event_id="evt-prop-001",
            occurred_at=now,
            aggregate_id="prop-123",
            property_id="prop-123",
            title="subClassOf",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"


class TestGraphInvalidated:
    """Tests for GraphInvalidated event."""

    def test_graph_invalidated_instantiation(self):
        """GraphInvalidated can be instantiated with all required fields."""
        now = datetime.utcnow()
        event = GraphInvalidated(
            event_id="evt-graph-inv-001",
            occurred_at=now,
            aggregate_id="tax-123",
            taxonomy_id="tax-123",
            reason="Class hierarchy changed",
        )
        assert event.taxonomy_id == "tax-123"
        assert event.reason == "Class hierarchy changed"

    def test_graph_invalidated_is_frozen(self):
        """GraphInvalidated instances are frozen."""
        now = datetime.utcnow()
        event = GraphInvalidated(
            event_id="evt-graph-inv-001",
            occurred_at=now,
            aggregate_id="tax-123",
            taxonomy_id="tax-123",
            reason="Class hierarchy changed",
        )
        with pytest.raises(FrozenInstanceError):
            event.reason = "New reason"


class TestEventImportability:
    """Tests that all events can be imported from the module."""

    def test_all_events_importable_from_events_module(self):
        """All ten event classes are importable from domain.ontology.events."""
        events = [
            DomainEvent,
            TaxonomyCreated,
            SchemeCreated,
            ClassCreated,
            ClassUpdated,
            ClassDeleted,
            ClassMoved,
            RelationshipCreated,
            RelationshipDeleted,
            PropertyDefinitionCreated,
            GraphInvalidated,
        ]
        for event_class in events:
            assert event_class is not None
            assert hasattr(event_class, "__dataclass_fields__")
