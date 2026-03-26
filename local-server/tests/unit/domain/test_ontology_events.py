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
    SchemeUpdated,
    SchemeDeleted,
    TaxonomyCreated,
    TaxonomyUpdated,
    TaxonomyDeleted,
)


class TestDomainEventBase:
    """Tests for DomainEvent base class."""

    def test_domain_event_creation_with_defaults(self):
        """DomainEvent can be instantiated with default event_id and occurred_at."""
        event = DomainEvent()
        assert event.event_id is not None
        assert isinstance(event.event_id, str)
        assert event.occurred_at is not None
        assert isinstance(event.occurred_at, datetime)

    def test_domain_event_creation_with_explicit_values(self):
        """DomainEvent can be instantiated with explicit event_id and occurred_at."""
        now = datetime.utcnow()
        event = DomainEvent(
            event_id="evt-123",
            occurred_at=now,
        )
        assert event.event_id == "evt-123"
        assert event.occurred_at == now

    def test_domain_event_is_frozen(self):
        """DomainEvent instances are frozen and cannot be modified."""
        event = DomainEvent()
        with pytest.raises(FrozenInstanceError):
            event.event_id = "new-id"

    def test_domain_event_rejects_empty_event_id(self):
        """DomainEvent raises ValueError if event_id is empty."""
        now = datetime.utcnow()
        with pytest.raises(ValueError, match="Event field 'event_id' cannot be empty"):
            DomainEvent(
                event_id="",
                occurred_at=now,
            )

    def test_domain_event_rejects_whitespace_event_id(self):
        """DomainEvent raises ValueError if event_id is only whitespace."""
        now = datetime.utcnow()
        with pytest.raises(ValueError, match="Event field 'event_id' cannot be empty"):
            DomainEvent(
                event_id="   ",
                occurred_at=now,
            )


class TestTaxonomyCreated:
    """Tests for TaxonomyCreated event."""

    def test_taxonomy_created_instantiation(self):
        """TaxonomyCreated can be instantiated with required fields."""
        event = TaxonomyCreated(
            taxonomy_id="tax-123",
            title="Biology Taxonomy",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.taxonomy_id == "tax-123"
        assert event.title == "Biology Taxonomy"

    def test_taxonomy_created_is_frozen(self):
        """TaxonomyCreated instances are frozen."""
        event = TaxonomyCreated(
            taxonomy_id="tax-123",
            title="Biology Taxonomy",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"

    def test_taxonomy_created_rejects_empty_title(self):
        """TaxonomyCreated raises ValueError if title is empty."""
        with pytest.raises(ValueError, match="Event field 'title' cannot be empty"):
            TaxonomyCreated(
                taxonomy_id="tax-123",
                title="",
            )

    def test_taxonomy_created_rejects_empty_taxonomy_id(self):
        """TaxonomyCreated raises ValueError if taxonomy_id is empty."""
        with pytest.raises(ValueError, match="Event field 'taxonomy_id' cannot be empty"):
            TaxonomyCreated(
                taxonomy_id="",
                title="Biology Taxonomy",
            )


class TestSchemeCreated:
    """Tests for SchemeCreated event."""

    def test_scheme_created_instantiation(self):
        """SchemeCreated can be instantiated with all required fields."""
        event = SchemeCreated(
            concept_scheme_id="scheme-123",
            title="Animal Kingdom",
            taxonomy_id="tax-456",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.concept_scheme_id == "scheme-123"
        assert event.title == "Animal Kingdom"
        assert event.taxonomy_id == "tax-456"

    def test_scheme_created_is_frozen(self):
        """SchemeCreated instances are frozen."""
        event = SchemeCreated(
            concept_scheme_id="scheme-123",
            title="Animal Kingdom",
            taxonomy_id="tax-456",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"


class TestTaxonomyUpdated:
    """Tests for TaxonomyUpdated event."""

    def test_taxonomy_updated_instantiation(self):
        """TaxonomyUpdated can be instantiated with changed fields and old/new values."""
        event = TaxonomyUpdated(
            taxonomy_id="tax-123",
            changed_fields=("title",),
            old_values={"title": "Old Title"},
            new_values={"title": "New Title"},
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.taxonomy_id == "tax-123"
        assert event.changed_fields == ("title",)
        assert event.old_values == {"title": "Old Title"}
        assert event.new_values == {"title": "New Title"}

    def test_taxonomy_updated_with_multiple_changed_fields(self):
        """TaxonomyUpdated can have multiple changed fields."""
        event = TaxonomyUpdated(
            taxonomy_id="tax-123",
            changed_fields=("title", "description"),
            old_values={"title": "Old Title", "description": "Old Desc"},
            new_values={"title": "New Title", "description": "New Desc"},
        )
        assert event.changed_fields == ("title", "description")
        assert event.old_values == {"title": "Old Title", "description": "Old Desc"}
        assert event.new_values == {"title": "New Title", "description": "New Desc"}

    def test_taxonomy_updated_is_frozen(self):
        """TaxonomyUpdated instances are frozen."""
        event = TaxonomyUpdated(
            taxonomy_id="tax-123",
            changed_fields=("title",),
            old_values={"title": "Old Title"},
            new_values={"title": "New Title"},
        )
        with pytest.raises(FrozenInstanceError):
            event.changed_fields = ("description",)


class TestTaxonomyDeleted:
    """Tests for TaxonomyDeleted event."""

    def test_taxonomy_deleted_instantiation(self):
        """TaxonomyDeleted can be instantiated with all required fields."""
        event = TaxonomyDeleted(
            taxonomy_id="tax-123",
            title="Biology",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.taxonomy_id == "tax-123"
        assert event.title == "Biology"

    def test_taxonomy_deleted_is_frozen(self):
        """TaxonomyDeleted instances are frozen."""
        event = TaxonomyDeleted(
            taxonomy_id="tax-123",
            title="Biology",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"

    def test_taxonomy_deleted_rejects_empty_title(self):
        """TaxonomyDeleted raises ValueError if title is empty."""
        with pytest.raises(ValueError, match="Event field 'title' cannot be empty"):
            TaxonomyDeleted(
                taxonomy_id="tax-123",
                title="",
            )


class TestSchemeUpdated:
    """Tests for SchemeUpdated event."""

    def test_scheme_updated_instantiation(self):
        """SchemeUpdated can be instantiated with changed fields and old/new values."""
        event = SchemeUpdated(
            concept_scheme_id="scheme-123",
            taxonomy_id="tax-456",
            changed_fields=("title",),
            old_values={"title": "Old Title"},
            new_values={"title": "New Title"},
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.concept_scheme_id == "scheme-123"
        assert event.taxonomy_id == "tax-456"
        assert event.changed_fields == ("title",)
        assert event.old_values == {"title": "Old Title"}
        assert event.new_values == {"title": "New Title"}

    def test_scheme_updated_with_multiple_changed_fields(self):
        """SchemeUpdated can have multiple changed fields."""
        event = SchemeUpdated(
            concept_scheme_id="scheme-123",
            taxonomy_id="tax-456",
            changed_fields=("title", "description"),
            old_values={"title": "Old Title", "description": "Old Desc"},
            new_values={"title": "New Title", "description": "New Desc"},
        )
        assert event.changed_fields == ("title", "description")
        assert event.old_values == {"title": "Old Title", "description": "Old Desc"}
        assert event.new_values == {"title": "New Title", "description": "New Desc"}

    def test_scheme_updated_is_frozen(self):
        """SchemeUpdated instances are frozen."""
        event = SchemeUpdated(
            concept_scheme_id="scheme-123",
            taxonomy_id="tax-456",
            changed_fields=("title",),
            old_values={"title": "Old Title"},
            new_values={"title": "New Title"},
        )
        with pytest.raises(FrozenInstanceError):
            event.changed_fields = ("description",)


class TestSchemeDeleted:
    """Tests for SchemeDeleted event."""

    def test_scheme_deleted_instantiation(self):
        """SchemeDeleted can be instantiated with all required fields."""
        event = SchemeDeleted(
            concept_scheme_id="scheme-123",
            taxonomy_id="tax-456",
            title="Animal Kingdom",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.concept_scheme_id == "scheme-123"
        assert event.taxonomy_id == "tax-456"
        assert event.title == "Animal Kingdom"

    def test_scheme_deleted_is_frozen(self):
        """SchemeDeleted instances are frozen."""
        event = SchemeDeleted(
            concept_scheme_id="scheme-123",
            taxonomy_id="tax-456",
            title="Animal Kingdom",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"

    def test_scheme_deleted_rejects_empty_title(self):
        """SchemeDeleted raises ValueError if title is empty."""
        with pytest.raises(ValueError, match="Event field 'title' cannot be empty"):
            SchemeDeleted(
                concept_scheme_id="scheme-123",
                taxonomy_id="tax-456",
                title="",
            )


class TestClassCreated:
    """Tests for ClassCreated event."""

    def test_class_created_instantiation(self):
        """ClassCreated can be instantiated with all required fields."""
        event = ClassCreated(
            class_id="class-123",
            title="Mammal",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.class_id == "class-123"
        assert event.title == "Mammal"
        assert event.concept_scheme_id == "scheme-456"
        assert event.taxonomy_id == "tax-789"

    def test_class_created_is_frozen(self):
        """ClassCreated instances are frozen."""
        event = ClassCreated(
            class_id="class-123",
            title="Mammal",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"


class TestClassUpdated:
    """Tests for ClassUpdated event."""

    def test_class_updated_instantiation(self):
        """ClassUpdated can be instantiated with changed fields and old/new values."""
        event = ClassUpdated(
            class_id="class-123",
            changed_fields=("title", "description"),
            old_values={"title": "Old Title", "description": "Old Desc"},
            new_values={"title": "New Title", "description": "New Desc"},
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.class_id == "class-123"
        assert event.changed_fields == ("title", "description")
        assert event.old_values == {"title": "Old Title", "description": "Old Desc"}
        assert event.new_values == {"title": "New Title", "description": "New Desc"}

    def test_class_updated_with_empty_changed_fields(self):
        """ClassUpdated can be instantiated with empty changed_fields tuple."""
        event = ClassUpdated(
            class_id="class-123",
            changed_fields=(),
            old_values={},
            new_values={},
        )
        assert event.changed_fields == ()
        assert event.old_values == {}
        assert event.new_values == {}

    def test_class_updated_is_frozen(self):
        """ClassUpdated instances are frozen."""
        event = ClassUpdated(
            class_id="class-123",
            changed_fields=("title",),
            old_values={"title": "Old Title"},
            new_values={"title": "New Title"},
        )
        with pytest.raises(FrozenInstanceError):
            event.changed_fields = ("new_field",)


class TestClassDeleted:
    """Tests for ClassDeleted event."""

    def test_class_deleted_instantiation(self):
        """ClassDeleted can be instantiated with all required fields."""
        event = ClassDeleted(
            class_id="class-123",
            title="Mammal",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.class_id == "class-123"
        assert event.title == "Mammal"

    def test_class_deleted_is_frozen(self):
        """ClassDeleted instances are frozen."""
        event = ClassDeleted(
            class_id="class-123",
            title="Mammal",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"


class TestClassMoved:
    """Tests for ClassMoved event."""

    def test_class_moved_with_parent_ids(self):
        """ClassMoved can be instantiated with non-empty parent IDs."""
        event = ClassMoved(
            class_id="class-123",
            old_parent_id="parent-old",
            new_parent_id="parent-new",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.class_id == "class-123"
        assert event.old_parent_id == "parent-old"
        assert event.new_parent_id == "parent-new"

    def test_class_moved_from_root_to_parent(self):
        """ClassMoved allows None for old_parent_id (was root)."""
        event = ClassMoved(
            class_id="class-123",
            old_parent_id=None,
            new_parent_id="parent-new",
        )
        assert event.old_parent_id is None
        assert event.new_parent_id == "parent-new"

    def test_class_moved_to_root(self):
        """ClassMoved allows None for new_parent_id (now root)."""
        event = ClassMoved(
            class_id="class-123",
            old_parent_id="parent-old",
            new_parent_id=None,
        )
        assert event.old_parent_id == "parent-old"
        assert event.new_parent_id is None

    def test_class_moved_both_parents_none(self):
        """ClassMoved allows None for both parent IDs."""
        event = ClassMoved(
            class_id="class-123",
            old_parent_id=None,
            new_parent_id=None,
        )
        assert event.old_parent_id is None
        assert event.new_parent_id is None

    def test_class_moved_rejects_empty_class_id(self):
        """ClassMoved raises ValueError if class_id is empty."""
        with pytest.raises(ValueError, match="Event field 'class_id' cannot be empty"):
            ClassMoved(
                class_id="",
                old_parent_id="parent-old",
                new_parent_id="parent-new",
            )

    def test_class_moved_is_frozen(self):
        """ClassMoved instances are frozen."""
        event = ClassMoved(
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
        event = RelationshipCreated(
            relationship_id="rel-123",
            source_id="class-456",
            target_id="class-789",
            property_definition_id="prop-101",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.relationship_id == "rel-123"
        assert event.source_id == "class-456"
        assert event.target_id == "class-789"
        assert event.property_definition_id == "prop-101"

    def test_relationship_created_is_frozen(self):
        """RelationshipCreated instances are frozen."""
        event = RelationshipCreated(
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
        event = RelationshipDeleted(
            relationship_id="rel-123",
            source_id="class-456",
            target_id="class-789",
            property_definition_id="prop-101",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.relationship_id == "rel-123"
        assert event.source_id == "class-456"
        assert event.target_id == "class-789"
        assert event.property_definition_id == "prop-101"

    def test_relationship_deleted_is_frozen(self):
        """RelationshipDeleted instances are frozen."""
        event = RelationshipDeleted(
            relationship_id="rel-123",
            source_id="class-456",
            target_id="class-789",
            property_definition_id="prop-101",
        )
        with pytest.raises(FrozenInstanceError):
            event.relationship_id = "new-rel"


class TestPropertyDefinitionCreated:
    """Tests for PropertyDefinitionCreated event."""

    def test_property_definition_created_instantiation(self):
        """PropertyDefinitionCreated can be instantiated with all required fields."""
        event = PropertyDefinitionCreated(
            property_id="prop-123",
            title="subClassOf",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.property_id == "prop-123"
        assert event.title == "subClassOf"

    def test_property_definition_created_is_frozen(self):
        """PropertyDefinitionCreated instances are frozen."""
        event = PropertyDefinitionCreated(
            property_id="prop-123",
            title="subClassOf",
        )
        with pytest.raises(FrozenInstanceError):
            event.title = "New Title"


class TestGraphInvalidated:
    """Tests for GraphInvalidated event."""

    def test_graph_invalidated_instantiation(self):
        """GraphInvalidated can be instantiated with all required fields."""
        event = GraphInvalidated(
            taxonomy_id="tax-123",
            reason="Class hierarchy changed",
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.taxonomy_id == "tax-123"
        assert event.reason == "Class hierarchy changed"

    def test_graph_invalidated_is_frozen(self):
        """GraphInvalidated instances are frozen."""
        event = GraphInvalidated(
            taxonomy_id="tax-123",
            reason="Class hierarchy changed",
        )
        with pytest.raises(FrozenInstanceError):
            event.reason = "New reason"


class TestEventImportability:
    """Tests that all events can be imported from the module."""

    def test_all_events_importable_from_events_module(self):
        """All fifteen event classes are importable from domain.ontology.events."""
        events = [
            DomainEvent,
            TaxonomyCreated,
            TaxonomyUpdated,
            TaxonomyDeleted,
            SchemeCreated,
            SchemeUpdated,
            SchemeDeleted,
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
