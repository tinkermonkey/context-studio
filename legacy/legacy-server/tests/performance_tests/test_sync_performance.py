import time
from datetime import datetime
from unittest.mock import Mock

from services.change_extractor import ChangeExtractor


class TestSyncPerformance:

    def test_large_change_extraction_performance(self):
        """Test performance with large number of changes."""
        mock_session = Mock()

        # Create 1000 mock change events
        mock_events = []
        for i in range(1000):
            mock_event = Mock()
            mock_event.id = i
            mock_event.event_type = "create"
            mock_event.record_type = "structure_node"
            mock_event.record_id = f"test-id-{i}"
            mock_event.old_data = None
            mock_event.new_data = {"title": f"Test Node {i}"}
            mock_event.timestamp = datetime.now()
            mock_events.append(mock_event)

        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_events

        extractor = ChangeExtractor(mock_session)

        start_time = time.time()
        changes = extractor.extract_pending_changes()
        extraction_time = time.time() - start_time

        assert len(changes) == 1000
        assert extraction_time < 1.0  # Should complete within 1 second

        # Test DataFrame creation performance
        start_time = time.time()
        df = extractor.create_change_dataframe(changes)
        dataframe_time = time.time() - start_time

        assert len(df) == 1000
        assert dataframe_time < 2.0  # Should complete within 2 seconds
