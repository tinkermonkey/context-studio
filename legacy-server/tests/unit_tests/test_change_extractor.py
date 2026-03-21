from unittest.mock import Mock
from datetime import datetime
from services.change_extractor import ChangeExtractor, ChangeRecord


class TestChangeExtractor:

    def test_extract_pending_changes(self):
        """Test extracting pending changes."""
        mock_session = Mock()
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        # Mock change event
        mock_event = Mock()
        mock_event.id = 1
        mock_event.event_type = "create"
        mock_event.record_type = "structure_node"
        mock_event.record_id = "test-id"
        mock_event.old_data = None
        mock_event.new_data = {"title": "Test Node"}
        mock_event.timestamp = datetime.now()

        mock_query.all.return_value = [mock_event]

        extractor = ChangeExtractor(mock_session)
        changes = extractor.extract_pending_changes()

        assert len(changes) == 1
        assert changes[0].event_type == "create"
        assert changes[0].record_type == "structure_node"

    def test_create_change_dataframe(self):
        """Test DataFrame creation from changes."""
        extractor = ChangeExtractor(Mock())

        changes = [
            ChangeRecord(
                change_id="1",
                event_type="create",
                record_type="structure_node",
                record_id="test-id",
                old_data=None,
                new_data={"title": "Test"},
                timestamp=datetime.now().isoformat(),
                batch_id="batch-1",
            )
        ]

        df = extractor.create_change_dataframe(changes)

        assert len(df) == 1
        assert df.iloc[0]["event_type"] == "create"
        assert df.iloc[0]["record_type"] == "structure_node"
