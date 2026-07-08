"""
Unit tests for the DR spec -> ontology transform (scripts/dr_ontology_loader.py).

Uses tiny synthetic spec directories (not the real documentation_robotics
checkout, which is an external dependency not available in CI) to exercise
manifest parsing, schema iteration, and relationship identifier compression.
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from scripts.dr_ontology_loader import (
    NodeSchemaRecord,
    RelationshipSchemaRecord,
    compress_relationship_identifiers,
    iter_node_schemas,
    iter_relationship_schemas,
    read_manifest,
    slugify_spec_node_id,
)


def _write_node_schema(spec_dir, layer, type_name, title, description):
    layer_dir = spec_dir / "schemas" / "nodes" / layer
    layer_dir.mkdir(parents=True, exist_ok=True)
    path = layer_dir / f"{type_name}.node.schema.json"
    path.write_text(
        json.dumps(
            {
                "title": title,
                "description": description,
                "properties": {
                    "spec_node_id": {"const": f"{layer}.{type_name}"},
                    "layer_id": {"const": layer},
                    "type": {"const": type_name},
                },
            }
        )
    )


def _write_relationship_schema(
    spec_dir, source_layer, source_type, predicate, dest_layer, dest_type, title, description
):
    rel_dir = spec_dir / "schemas" / "relationships" / source_layer
    rel_dir.mkdir(parents=True, exist_ok=True)
    file_predicate = predicate.replace(" ", "-")
    path = rel_dir / f"{source_type}.{file_predicate}.{dest_type}.relationship.schema.json"
    path.write_text(
        json.dumps(
            {
                "title": title,
                "description": description,
                "properties": {
                    "source_spec_node_id": {"const": f"{source_layer}.{source_type}"},
                    "source_layer": {"const": source_layer},
                    "destination_spec_node_id": {"const": f"{dest_layer}.{dest_type}"},
                    "destination_layer": {"const": dest_layer},
                    "predicate": {"const": predicate},
                },
            }
        )
    )


def _write_manifest(spec_dir, spec_version="0.8.4"):
    dist_dir = spec_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "specVersion": spec_version,
        "layers": [
            {
                "id": "motivation",
                "number": 1,
                "name": "Motivation Layer",
                "nodeTypeCount": 2,
                "relationshipCount": 1,
            },
            {
                "id": "business",
                "number": 2,
                "name": "Business Layer",
                "nodeTypeCount": 1,
                "relationshipCount": 1,
            },
        ],
    }
    (dist_dir / "manifest.json").write_text(json.dumps(manifest))


class TestSlugifySpecNodeId:
    def test_replaces_dots_and_hyphens(self):
        assert slugify_spec_node_id("motivation.goal") == "motivation_goal"
        assert slugify_spec_node_id("data-model.entity") == "data_model_entity"


class TestReadManifest:
    def test_reads_spec_version_and_layers(self, tmp_path):
        _write_manifest(tmp_path, spec_version="0.9.0")
        spec_version, layers = read_manifest(tmp_path)
        assert spec_version == "0.9.0"
        assert [layer["id"] for layer in layers] == ["motivation", "business"]


class TestIterNodeSchemas:
    def test_yields_one_record_per_node_schema(self, tmp_path):
        _write_node_schema(tmp_path, "motivation", "goal", "Goal", "A goal description")
        _write_node_schema(tmp_path, "motivation", "requirement", "Requirement", "A requirement")

        records = list(iter_node_schemas(tmp_path))

        assert len(records) == 2
        assert records[0] == NodeSchemaRecord(
            spec_node_id="motivation.goal",
            layer_id="motivation",
            title="Goal",
            description="A goal description",
        )

    def test_ignores_files_outside_nodes_dir(self, tmp_path):
        _write_node_schema(tmp_path, "motivation", "goal", "Goal", "desc")
        base_dir = tmp_path / "schemas" / "base"
        base_dir.mkdir(parents=True)
        (base_dir / "spec-node.schema.json").write_text("{}")

        records = list(iter_node_schemas(tmp_path))

        assert len(records) == 1

    def test_missing_nodes_dir_raises_instead_of_yielding_nothing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="schemas/nodes"):
            list(iter_node_schemas(tmp_path))


class TestIterRelationshipSchemas:
    def test_yields_one_record_per_relationship_schema(self, tmp_path):
        _write_relationship_schema(
            tmp_path,
            "motivation",
            "stakeholder",
            "associated-with",
            "motivation",
            "requirement",
            "Stakeholder associated-with Requirement",
            "Defines relationship",
        )

        records = list(iter_relationship_schemas(tmp_path))

        assert len(records) == 1
        record = records[0]
        assert record.source_spec_node_id == "motivation.stakeholder"
        assert record.destination_spec_node_id == "motivation.requirement"
        assert record.predicate == "associated-with"
        assert (
            record.full_identifier
            == "motivation.stakeholder.associated-with.motivation.requirement"
        )

    def test_missing_relationships_dir_raises_instead_of_yielding_nothing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="schemas/relationships"):
            list(iter_relationship_schemas(tmp_path))


class TestCompressRelationshipIdentifiers:
    def _record(self, source_layer, source_type, predicate, dest_layer, dest_type):
        return RelationshipSchemaRecord(
            source_spec_node_id=f"{source_layer}.{source_type}",
            source_layer=source_layer,
            destination_spec_node_id=f"{dest_layer}.{dest_type}",
            destination_layer=dest_layer,
            predicate=predicate,
            title="Title",
            description="Description",
        )

    def test_short_identifier_is_layer_stripped_only(self):
        record = self._record(
            "motivation", "stakeholder", "associated-with", "motivation", "requirement"
        )

        compressed = compress_relationship_identifiers([record])

        assert compressed[record.full_identifier] == "stakeholder_associated_with_requirement"

    def test_long_identifier_falls_back_to_hash_suffix(self):
        record = self._record(
            "application",
            "applicationcollaboration",
            "delivers-value",
            "application",
            "applicationinteraction",
        )
        # Layer-stripped form here is 61 chars — construct one that still overflows
        # by using longer synthetic type names.
        record = self._record(
            "application",
            "applicationcollaborationextendedtype",
            "delivers-extended-business-value",
            "application",
            "applicationinteractionextendedtype",
        )

        compressed = compress_relationship_identifiers([record])
        result = compressed[record.full_identifier]

        assert len(result) <= 64
        # 4-hex-char suffix after an underscore, per ADR-8 step 2.
        suffix = result.rsplit("_", 1)[1]
        assert len(suffix) == 4
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_colliding_short_forms_are_disambiguated(self):
        # 'ux.view' and 'data-store.view' both strip to the same 'view' type name.
        record_a = self._record("ux", "view", "serves", "business", "businessservice")
        record_b = self._record("data-store", "view", "serves", "business", "businessservice")

        compressed = compress_relationship_identifiers([record_a, record_b])

        id_a = compressed[record_a.full_identifier]
        id_b = compressed[record_b.full_identifier]
        assert id_a != id_b
        assert len(id_a) <= 64
        assert len(id_b) <= 64

    def test_all_identifiers_are_unique_and_within_length_cap(self):
        records = [
            self._record(
                "motivation", "stakeholder", "associated-with", "motivation", "requirement"
            ),
            self._record("ux", "view", "serves", "business", "businessservice"),
            self._record("data-store", "view", "serves", "business", "businessservice"),
            self._record("ux", "view", "serves", "application", "applicationservice"),
            self._record("data-store", "view", "serves", "application", "applicationservice"),
        ]

        compressed = compress_relationship_identifiers(records)

        values = list(compressed.values())
        assert len(values) == len(set(values))
        assert all(len(v) <= 64 for v in values)

    def test_predicate_hyphens_become_underscores(self):
        record = self._record("motivation", "stakeholder", "associated-with", "motivation", "goal")

        compressed = compress_relationship_identifiers([record])

        assert "-" not in compressed[record.full_identifier]
