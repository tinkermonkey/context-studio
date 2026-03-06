"""
Unit tests for Reference Filter Service

Tests the filtering of reference links based on predicate relevance.
"""

import os
import sys
import pytest
import json
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.reference_filter_service import ReferenceFilterService  # noqa: E402, E501
from reference_db.models import ReferenceLink, ExternalPredicate  # noqa: E402
from database.models import Predicate  # noqa: E402


class TestReferenceFilterService:
    """Unit tests for ReferenceFilterService"""

    @pytest.fixture
    def mock_local_session(self):
        """Create mock local database session"""
        return Mock()

    @pytest.fixture
    def mock_ref_manager(self):
        """Create mock reference manager"""
        return Mock()

    @pytest.fixture
    def filter_service(self, mock_local_session, mock_ref_manager):
        """Create filter service instance"""
        return ReferenceFilterService(mock_local_session, mock_ref_manager)

    def test_get_predicate_mappings_empty(self, filter_service, mock_local_session):  # noqa: E501
        """Test getting mappings when no predicates exist"""
        mock_local_session.query.return_value.all.return_value = []

        mappings = filter_service._get_all_predicate_mappings_with_relevance()

        assert mappings == {}

    def test_get_predicate_mappings_with_valid_json(self, filter_service, mock_local_session):  # noqa: E501
        """Test getting mappings with valid JSON mapping"""
        mock_pred = Mock(spec=Predicate)
        mock_pred.id = "pred1"
        mock_pred.is_relevant = True
        mock_pred.mapping = json.dumps([
            {"source": "schema.org", "external_id": "subClassOf"},
            {"source": "wikidata", "external_id": "P279"}
        ])

        mock_local_session.query.return_value.all.return_value = [mock_pred]

        mappings = filter_service._get_all_predicate_mappings_with_relevance()

        assert "pred1" in mappings
        assert mappings["pred1"]["is_relevant"] is True
        assert len(mappings["pred1"]["external_predicates"]) == 2
        assert mappings["pred1"]["external_predicates"][0]["source"] == "schema.org"  # noqa: E501

    def test_get_predicate_mappings_with_dict_format(self, filter_service, mock_local_session):  # noqa: E501
        """Test getting mappings with dict-formatted JSON"""
        mock_pred = Mock(spec=Predicate)
        mock_pred.id = "pred1"
        mock_pred.is_relevant = False
        mock_pred.mapping = json.dumps({
            "external_predicates": [
                {"source": "schema.org", "external_id": "property"}
            ]
        })

        mock_local_session.query.return_value.all.return_value = [mock_pred]

        mappings = filter_service._get_all_predicate_mappings_with_relevance()

        assert mappings["pred1"]["is_relevant"] is False
        assert len(mappings["pred1"]["external_predicates"]) == 1

    def test_get_predicate_mappings_with_invalid_json(self, filter_service, mock_local_session):  # noqa: E501
        """Test handling of invalid JSON in mapping"""
        mock_pred = Mock(spec=Predicate)
        mock_pred.id = "pred1"
        mock_pred.is_relevant = True
        mock_pred.mapping = "invalid json {{"

        mock_local_session.query.return_value.all.return_value = [mock_pred]

        mappings = filter_service._get_all_predicate_mappings_with_relevance()

        # Should handle gracefully with empty external_predicates list
        assert mappings["pred1"]["external_predicates"] == []

    def test_get_predicate_mappings_with_whitespace_only_mapping(self, filter_service, mock_local_session):  # noqa: E501
        """Test handling of whitespace-only mapping"""
        mock_pred = Mock(spec=Predicate)
        mock_pred.id = "pred1"
        mock_pred.is_relevant = True
        mock_pred.mapping = "   "  # Only whitespace

        mock_local_session.query.return_value.all.return_value = [mock_pred]

        mappings = filter_service._get_all_predicate_mappings_with_relevance()

        # Should handle gracefully - whitespace-only mappings are treated as empty  # noqa: E501
        assert mappings["pred1"]["external_predicates"] == []

    def test_get_predicate_mappings_with_empty_string_mapping(self, filter_service, mock_local_session):  # noqa: E501
        """Test handling of empty string mapping"""
        mock_pred = Mock(spec=Predicate)
        mock_pred.id = "pred1"
        mock_pred.is_relevant = True
        mock_pred.mapping = ""  # Empty string

        mock_local_session.query.return_value.all.return_value = [mock_pred]

        mappings = filter_service._get_all_predicate_mappings_with_relevance()

        # Should handle gracefully - empty string mappings are treated as no mapping  # noqa: E501
        assert mappings["pred1"]["external_predicates"] == []

    def test_build_relevance_sets(self, filter_service):
        """Test building relevance sets from mappings"""
        mock_mappings = {
            "pred1": {
                "is_relevant": True,
                "external_predicates": [
                    {"source": "schema.org", "external_id": "subClassOf"},
                    {"source": "wikidata", "external_id": "P279"}
                ]
            },
            "pred2": {
                "is_relevant": False,
                "external_predicates": [
                    {"source": "schema.org", "external_id": "property"}
                ]
            },
            "pred3": {
                "is_relevant": None,  # Not evaluated - should be skipped
                "external_predicates": [
                    {"source": "schema.org", "external_id": "rangeIncludes"}
                ]
            }
        }

        with patch.object(filter_service, '_get_all_predicate_mappings_with_relevance', return_value=mock_mappings):  # noqa: E501
            relevant, irrelevant = filter_service._build_relevance_sets()

        assert "schema.org:subClassOf" in relevant
        assert "wikidata:P279" in relevant
        assert "schema.org:property" in irrelevant
        assert "schema.org:rangeIncludes" not in relevant
        assert "schema.org:rangeIncludes" not in irrelevant

    def test_get_relevant_predicates_caching(self, filter_service):
        """Test that relevant predicates are cached"""
        mock_mappings = {
            "pred1": {
                "is_relevant": True,
                "external_predicates": [{"source": "schema.org", "external_id": "test"}]  # noqa: E501
            }
        }

        with patch.object(filter_service, '_get_all_predicate_mappings_with_relevance', return_value=mock_mappings) as mock_get:  # noqa: E501
            # First call should build cache
            result1 = filter_service.get_relevant_predicates()
            # Second call should use cache
            result2 = filter_service.get_relevant_predicates()

            # _get_all_predicate_mappings_with_relevance should only be called once  # noqa: E501
            assert mock_get.call_count == 1
            assert result1 == result2

    def test_get_relevant_predicates_force_refresh(self, filter_service):
        """Test force refresh bypasses cache"""
        mock_mappings = {
            "pred1": {
                "is_relevant": True,
                "external_predicates": [{"source": "schema.org", "external_id": "test"}]  # noqa: E501
            }
        }

        with patch.object(filter_service, '_get_all_predicate_mappings_with_relevance', return_value=mock_mappings) as mock_get:  # noqa: E501
            filter_service.get_relevant_predicates()
            filter_service.get_relevant_predicates(force_refresh=True)

            # Should be called twice
            assert mock_get.call_count == 2

    def test_invalidate_cache(self, filter_service):
        """Test cache invalidation"""
        filter_service._relevant_cache = {"test"}
        filter_service._irrelevant_cache = {"test2"}

        filter_service.invalidate_cache()

        assert filter_service._relevant_cache is None
        assert filter_service._irrelevant_cache is None

    def test_filter_links_no_predicates_marked(self, filter_service, mock_ref_manager):  # noqa: E501
        """Test filtering when no predicates are marked relevant/irrelevant"""
        mock_links = [Mock(spec=ReferenceLink) for _ in range(5)]

        with patch.object(filter_service, 'get_relevant_predicates', return_value=set()):  # noqa: E501
            with patch.object(filter_service, 'get_irrelevant_predicates', return_value=set()):  # noqa: E501
                filtered, stats = filter_service.filter_links(mock_links)

        # Should return all links when no filtering configured
        assert len(filtered) == 5
        assert stats["total_before"] == 5
        assert stats["total_after"] == 5
        assert stats["filtered_count"] == 0
        assert stats["filtering_active"] is False

    def test_filter_links_include_relevant(self, filter_service, mock_ref_manager):  # noqa: E501
        """Test filtering to include only relevant predicates"""
        # Create mock links
        link1 = Mock(spec=ReferenceLink)
        link1.predicate = "subClassOf"
        link1.source = "schema.org"

        link2 = Mock(spec=ReferenceLink)
        link2.predicate = "property"
        link2.source = "schema.org"

        link3 = Mock(spec=ReferenceLink)
        link3.predicate = "P279"
        link3.source = "wikidata"

        mock_links = [link1, link2, link3]

        # Setup external predicate responses
        ext_pred1 = Mock(spec=ExternalPredicate)
        ext_pred1.source = "schema.org"
        ext_pred1.external_id = "subClassOf"

        ext_pred2 = Mock(spec=ExternalPredicate)
        ext_pred2.source = "schema.org"
        ext_pred2.external_id = "property"

        ext_pred3 = Mock(spec=ExternalPredicate)
        ext_pred3.source = "wikidata"
        ext_pred3.external_id = "P279"

        # Mock list_external_predicates to return all external predicates
        mock_ref_manager.list_external_predicates.return_value = [ext_pred1, ext_pred2, ext_pred3]  # noqa: E501

        # Mark subClassOf and P279 as relevant
        with patch.object(filter_service, 'get_relevant_predicates', return_value={"schema.org:subClassOf", "wikidata:P279"}):  # noqa: E501
            with patch.object(filter_service, 'get_irrelevant_predicates', return_value=set()):  # noqa: E501
                filtered, stats = filter_service.filter_links(mock_links)

        # Should only include relevant predicates
        assert len(filtered) == 2
        assert link1 in filtered
        assert link3 in filtered
        assert link2 not in filtered
        assert stats["filtered_count"] == 1
        assert stats["filtering_active"] is True

    def test_filter_links_exclude_irrelevant(self, filter_service, mock_ref_manager):  # noqa: E501
        """Test filtering to exclude irrelevant predicates"""
        link1 = Mock(spec=ReferenceLink)
        link1.predicate = "subClassOf"
        link1.source = "schema.org"

        link2 = Mock(spec=ReferenceLink)
        link2.predicate = "property"
        link2.source = "schema.org"

        mock_links = [link1, link2]

        ext_pred1 = Mock(spec=ExternalPredicate)
        ext_pred1.source = "schema.org"
        ext_pred1.external_id = "subClassOf"

        ext_pred2 = Mock(spec=ExternalPredicate)
        ext_pred2.source = "schema.org"
        ext_pred2.external_id = "property"

        # Mock list_external_predicates to return all external predicates
        mock_ref_manager.list_external_predicates.return_value = [ext_pred1, ext_pred2]  # noqa: E501

        # Mark property as irrelevant
        with patch.object(filter_service, 'get_relevant_predicates', return_value=set()):  # noqa: E501
            with patch.object(filter_service, 'get_irrelevant_predicates', return_value={"schema.org:property"}):  # noqa: E501
                filtered, stats = filter_service.filter_links(mock_links, exclude_irrelevant=True)  # noqa: E501

        # Should exclude irrelevant
        assert len(filtered) == 1
        assert link1 in filtered
        assert link2 not in filtered

    def test_filter_links_unmapped_predicate(self, filter_service, mock_ref_manager):  # noqa: E501
        """Test handling of links with unmapped predicates in whitelist mode"""
        link = Mock(spec=ReferenceLink)
        link.predicate = "unknown"
        link.source = "schema.org"

        mock_links = [link]

        # Return None for unknown predicate
        mock_ref_manager.get_external_predicate_by_source.return_value = None

        # In whitelist mode (relevant predicates exist), unmapped predicates should be excluded  # noqa: E501
        with patch.object(filter_service, 'get_relevant_predicates', return_value={"schema.org:subClassOf"}):  # noqa: E501
            with patch.object(filter_service, 'get_irrelevant_predicates', return_value=set()):  # noqa: E501
                filtered, stats = filter_service.filter_links(mock_links)

        # Should exclude unmapped predicates in whitelist mode
        assert len(filtered) == 0
        assert link not in filtered

    def test_filter_links_unmapped_predicate_blacklist_mode(self, filter_service, mock_ref_manager):  # noqa: E501
        """Test handling of links with unmapped predicates in blacklist mode"""
        link = Mock(spec=ReferenceLink)
        link.predicate = "unknown"
        link.source = "schema.org"

        mock_links = [link]

        # Return None for unknown predicate
        mock_ref_manager.get_external_predicate_by_source.return_value = None

        # In blacklist mode (only irrelevant predicates exist), unmapped predicates should be included  # noqa: E501
        with patch.object(filter_service, 'get_relevant_predicates', return_value=set()):  # noqa: E501
            with patch.object(filter_service, 'get_irrelevant_predicates', return_value={"schema.org:deprecated"}):  # noqa: E501
                filtered, stats = filter_service.filter_links(mock_links)

        # Should include unmapped predicates in blacklist mode
        assert len(filtered) == 1
        assert link in filtered

    def test_get_filter_statistics(self, filter_service):
        """Test getting filter statistics"""
        mock_mappings = {
            "pred1": {
                "is_relevant": True,
                "external_predicates": [{"source": "schema.org", "external_id": "subClassOf"}]  # noqa: E501
            },
            "pred2": {
                "is_relevant": False,
                "external_predicates": [{"source": "schema.org", "external_id": "property"}]  # noqa: E501
            },
            "pred3": {
                "is_relevant": None,
                "external_predicates": []
            }
        }

        with patch.object(filter_service, '_get_all_predicate_mappings_with_relevance', return_value=mock_mappings):  # noqa: E501
            stats = filter_service.get_filter_statistics()

        assert stats["total_predicates"] == 3
        assert stats["relevant_count"] == 1
        assert stats["irrelevant_count"] == 1
        assert stats["unmapped_count"] == 1
        assert "schema.org:subClassOf" in stats["relevant_external_predicates"]
        assert "schema.org:property" in stats["irrelevant_external_predicates"]

    def test_filter_links_statistics_calculation(self, filter_service, mock_ref_manager):  # noqa: E501
        """Test that statistics are correctly calculated"""
        mock_links = [Mock(spec=ReferenceLink) for _ in range(10)]
        for i, link in enumerate(mock_links):
            link.predicate = f"pred{i}"
            link.source = "test"

        # Make first 3 relevant
        relevant_preds = {f"test:pred{i}" for i in range(3)}

        # Mock external predicates - create all 10
        all_ext_preds = []
        for i in range(10):
            ext_pred = Mock(spec=ExternalPredicate)
            ext_pred.source = "test"
            ext_pred.external_id = f"pred{i}"
            all_ext_preds.append(ext_pred)

        mock_ref_manager.list_external_predicates.return_value = all_ext_preds

        with patch.object(filter_service, 'get_relevant_predicates', return_value=relevant_preds):  # noqa: E501
            with patch.object(filter_service, 'get_irrelevant_predicates', return_value=set()):  # noqa: E501
                filtered, stats = filter_service.filter_links(mock_links)

        assert stats["total_before"] == 10
        assert stats["total_after"] == 3
        assert stats["filtered_count"] == 7
        assert len(stats["predicates_used"]) == 3
        assert stats["filtering_active"] is True
