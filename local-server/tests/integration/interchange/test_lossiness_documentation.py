"""
Tests to ensure interchange-lossiness.md documentation is well-formed and complete.

Validates:
- All required sections exist
- All three formats (SKOS, OWL, GraphML) are documented
- Critical-not-lossy section exists and is correct
- Section structure is consistent
"""

import sys
import os
import re

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest

LOSSINESS_DOC_PATH = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
    "documentation",
    "interchange-lossiness.md",
)


@pytest.fixture
def lossiness_doc_content():
    """Load the lossiness documentation."""
    with open(LOSSINESS_DOC_PATH, "r") as f:
        return f.read()


class TestLossinessDocumentation:
    """Validate the structure of interchange-lossiness.md."""

    def test_document_exists(self):
        """Test that the lossiness documentation file exists."""
        assert os.path.exists(
            LOSSINESS_DOC_PATH
        ), f"Documentation not found at {LOSSINESS_DOC_PATH}"

    def test_document_has_critical_not_lossy_section(self, lossiness_doc_content):
        """Test that Critical, Not Lossy section exists."""
        assert (
            "## Critical, Not Lossy" in lossiness_doc_content
        ), "Missing 'Critical, Not Lossy' section"

    def test_all_three_formats_documented(self, lossiness_doc_content):
        """Test that all three formats have top-level sections."""
        required_formats = [
            ("## SKOS", "SKOS"),
            ("## OWL", "OWL"),
            ("## GraphML", "GraphML"),
        ]

        for fmt_header, fmt_name in required_formats:
            # Use regex to allow optional parenthetical descriptions
            pattern = rf"{fmt_header}(\s|\()"
            assert re.search(
                pattern, lossiness_doc_content
            ), f"Missing top-level section for {fmt_name}"

    def test_skos_has_required_subsections(self, lossiness_doc_content):
        """Test that SKOS section has all required subsections."""
        # Extract SKOS section (with optional parenthetical description)
        skos_match = re.search(
            r"## SKOS.*?\n(.*?)(?=^## [A-Z]|\Z)",
            lossiness_doc_content,
            re.DOTALL | re.MULTILINE,
        )
        assert skos_match, "Could not extract SKOS section"

        skos_section = skos_match.group(1)

        required_subsections = [
            "### Survives Exactly",
            "### Survives But Lossy",
            "### Entirely Unsupported",
        ]

        for subsection in required_subsections:
            assert subsection in skos_section, f"SKOS section missing '{subsection}'"

    def test_owl_has_required_subsections(self, lossiness_doc_content):
        """Test that OWL section has all required subsections."""
        owl_match = re.search(
            r"## OWL.*?\n(.*?)(?=^## [A-Z]|\Z)",
            lossiness_doc_content,
            re.DOTALL | re.MULTILINE,
        )
        assert owl_match, "Could not extract OWL section"

        owl_section = owl_match.group(1)

        required_subsections = [
            "### Survives Exactly",
            "### Survives But Lossy",
            "### Entirely Unsupported",
        ]

        for subsection in required_subsections:
            assert subsection in owl_section, f"OWL section missing '{subsection}'"

    def test_graphml_has_required_subsections(self, lossiness_doc_content):
        """Test that GraphML section has all required subsections."""
        graphml_match = re.search(
            r"## GraphML.*?\n(.*?)(?=^## [A-Z]|\Z)",
            lossiness_doc_content,
            re.DOTALL | re.MULTILINE,
        )
        assert graphml_match, "Could not extract GraphML section"

        graphml_section = graphml_match.group(1)

        required_subsections = [
            "### Survives Exactly",
            "### Survives But Lossy",
            "### Entirely Unsupported",
        ]

        for subsection in required_subsections:
            assert (
                subsection in graphml_section
            ), f"GraphML section missing '{subsection}'"

    def test_external_references_in_critical_section(self, lossiness_doc_content):
        """Test that external_references is mentioned in Critical section."""
        critical_match = re.search(
            r"## Critical, Not Lossy\n(.*?)(?=---|\Z)", lossiness_doc_content, re.DOTALL
        )
        assert critical_match, "Could not extract Critical section"

        critical_section = critical_match.group(1)
        assert (
            "external_references" in critical_section.lower()
        ), "external_references not mentioned in Critical section"

    def test_document_mentions_round_trip_summary(self, lossiness_doc_content):
        """Test that document includes round-trip summary section."""
        assert (
            "## Round-Trip Summary" in lossiness_doc_content
        ), "Missing Round-Trip Summary section"

    def test_round_trip_summary_covers_all_legs(self, lossiness_doc_content):
        """Test that Round-Trip Summary documents all three legs."""
        round_trip_match = re.search(
            r"## Round-Trip Summary\n(.*?)(?=---|\Z)", lossiness_doc_content, re.DOTALL
        )
        assert round_trip_match, "Could not extract Round-Trip Summary section"

        summary = round_trip_match.group(1)

        required_legs = [
            "SKOS → SKOS",
            "OWL → OWL",
            "GraphML → GraphML",
            "SKOS → OWL",
            "OWL → GraphML",
            "GraphML → OWL",
        ]

        for leg in required_legs:
            assert leg in summary, f"Round-Trip Summary missing '{leg}'"

    def test_round_trip_summary_covers_three_format_chain(self, lossiness_doc_content):
        """Test that Round-Trip Summary documents the 3-format chain."""
        summary_match = re.search(
            r"## Round-Trip Summary\n(.*?)(?=---|\Z)", lossiness_doc_content, re.DOTALL
        )
        assert summary_match, "Could not extract Round-Trip Summary"

        summary = summary_match.group(1)
        assert (
            "Three-Format Chain" in summary or "three-format" in summary.lower()
        ), "Round-Trip Summary missing three-format chain documentation"

    def test_no_placeholder_text(self, lossiness_doc_content):
        """Test that documentation doesn't contain placeholder text."""
        placeholders = [
            "TODO",
            "FIXME",
            "XXX",
            "TBD",
            "INSERT HERE",
        ]

        for placeholder in placeholders:
            assert (
                placeholder not in lossiness_doc_content.upper()
            ), f"Documentation contains placeholder '{placeholder}'"

    def test_consistent_entity_types_mentioned(self, lossiness_doc_content):
        """Test that documentation mentions the main entity types."""
        entity_types = [
            "Taxonomy",
            "ConceptScheme",
            "Class",
            "Individual",
            "PropertyDefinition",
            "Relationship",
        ]

        for entity_type in entity_types:
            assert (
                entity_type in lossiness_doc_content
            ), f"Documentation missing entity type '{entity_type}'"

    def test_critical_fields_consistency(self, lossiness_doc_content):
        """Test that critical fields are mentioned consistently."""
        # Both external_references and hierarchical structure should be marked as critical
        critical_match = re.search(
            r"## Critical, Not Lossy\n(.*?)(?=---|\Z)", lossiness_doc_content, re.DOTALL
        )
        assert critical_match, "Could not extract Critical section"

        critical_section = critical_match.group(1)

        # Check that critical fields are actually mentioned
        assert (
            "external_references" in critical_section.lower()
        ), "external_references not marked as critical"

        assert (
            "identity" in critical_section.lower()
            or "hierarchy" in critical_section.lower()
        ), "Structural relationships not marked as critical"

    def test_document_is_not_empty(self, lossiness_doc_content):
        """Test that documentation has substantial content."""
        assert (
            len(lossiness_doc_content) > 1000
        ), "Documentation is too short (likely incomplete)"

    def test_all_formats_have_content(self, lossiness_doc_content):
        """Test that each format section has substantive content."""
        formats = ["SKOS", "OWL", "GraphML"]

        for fmt in formats:
            fmt_match = re.search(
                rf"## {fmt}.*?\n(.*?)(?=^## [A-Z]|\Z)",
                lossiness_doc_content,
                re.DOTALL | re.MULTILINE,
            )
            assert fmt_match, f"Could not extract {fmt} section"

            fmt_section = fmt_match.group(1)
            assert (
                len(fmt_section) > 200
            ), f"{fmt} section is too short (likely incomplete)"
