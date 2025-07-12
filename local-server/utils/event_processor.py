class GraphEvent:
    def __init__(self, id, entity_type, entity_id, event_type, data, timestamp, processed):
        self.id = id
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.event_type = event_type
        # Convert JSON string to dict if not None
        if data is not None and isinstance(data, str):
            try:
                self.data = json.loads(data)
            except Exception:
                self.data = data  # fallback to raw string if not valid JSON
        else:
            self.data = data
        # Parse timestamp to datetime if string
        if isinstance(timestamp, str):
            try:
                self.timestamp = datetime.fromisoformat(timestamp)
            except Exception:
                self.timestamp = timestamp
        else:
            self.timestamp = timestamp
        self.processed = bool(processed)

import threading
import time
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from utils.logger import get_logger

class EventProcessor:
    def __init__(self, db_path, poll_interval=1.0, max_events=100, faiss_manager=None):
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.max_events = max_events
        self._stop_event = threading.Event()
        self._thread = None
        self._cleanup_thread = None
        self.faiss_manager = faiss_manager
        # Ensure logger is always set, even if __init__ is called multiple times
        if not hasattr(self, 'logger') or self.logger is None:
            self.logger = get_logger(__name__)

    def start(self):
        self.logger.info("[EventProcessor] start() called")
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self.logger.info("[EventProcessor] main thread started")
            self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self._cleanup_thread.start()
            self.logger.info("[EventProcessor] cleanup thread started")

    def stop(self):
        self.logger.info("[EventProcessor] stop() called")
        self._stop_event.set()
        if self._thread:
            self.logger.info("[EventProcessor] joining main thread...")
            self._thread.join(timeout=5)
            self.logger.info("[EventProcessor] main thread joined")
        if self._cleanup_thread:
            self.logger.info("[EventProcessor] joining cleanup thread...")
            self._cleanup_thread.join(timeout=5)
            self.logger.info("[EventProcessor] cleanup thread joined")

    def _run(self):
        self.logger.info("[EventProcessor] _run() loop starting")
        while not self._stop_event.is_set():
            try:
                self.logger.debug("[EventProcessor] processing events...")
                self.process_events()
            except Exception as e:
                self.logger.error(f"[EventProcessor] Error: {e}")
            time.sleep(self.poll_interval)
        self.logger.info("[EventProcessor] _run() loop exiting")

    def process_events(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM graph_events WHERE processed=0 ORDER BY timestamp LIMIT ?", (self.max_events,))
        rows = cur.fetchall()
        for row in rows:
            event = GraphEvent(
                id=row['id'],
                entity_type=row['entity_type'],
                entity_id=row['entity_id'],
                event_type=row['event_type'],
                data=row['data'],
                timestamp=row['timestamp'],
                processed=row['processed']
            )
            entity_type = event.entity_type
            handler = getattr(self, f"process_{entity_type}_event", None)
            if handler:
                handler(event)
            else:
                self.logger.warning(f"[EventProcessor] No handler for entity_type: {entity_type}")
            cur.execute("UPDATE graph_events SET processed=1 WHERE id=?", (event.id,))
        conn.commit()
        conn.close()

    def process_layer_event(self, event):
        self.logger.info(f"[EventProcessor] Processing layer event: {event.event_type} id={event.id}")
        if not self.faiss_manager:
            return
        index = self.faiss_manager.get_index('layer')
        if not index:
            return
        # Only handle title_embedding for now
        if event.event_type == 'create':
            emb = self._extract_embedding(event, 'title_embedding')
            if emb is not None:
                index.add(event.entity_id, emb)
        elif event.event_type == 'update':
            emb = self._extract_embedding(event, 'title_embedding')
            if emb is not None:
                index.update(event.entity_id, emb)
        elif event.event_type == 'delete':
            index.remove(event.entity_id)

    def process_domain_event(self, event):
        self.logger.info(f"[EventProcessor] Processing domain event: {event.event_type} id={event.id}")
        if not self.faiss_manager:
            return
        index = self.faiss_manager.get_index('domain')
        if not index:
            return
        if event.event_type == 'create':
            emb = self._extract_embedding(event, 'title_embedding')
            if emb is not None:
                index.add(event.entity_id, emb)
        elif event.event_type == 'update':
            emb = self._extract_embedding(event, 'title_embedding')
            if emb is not None:
                index.update(event.entity_id, emb)
        elif event.event_type == 'delete':
            index.remove(event.entity_id)

    def process_term_event(self, event):
        self.logger.info(f"[EventProcessor] Processing term event: {event.event_type} id={event.id}")
        if not self.faiss_manager:
            return
        index = self.faiss_manager.get_index('term')
        if not index:
            return
        if event.event_type == 'create':
            emb = self._extract_embedding(event, 'title_embedding')
            if emb is not None:
                index.add(event.entity_id, emb)
        elif event.event_type == 'update':
            emb = self._extract_embedding(event, 'title_embedding')
            if emb is not None:
                index.update(event.entity_id, emb)
        elif event.event_type == 'delete':
            index.remove(event.entity_id)
    def _extract_embedding(self, event, field):
        # Try new_data, fallback to old_data for deletes
        import numpy as np
        data = event.data or {}
        if event.event_type == 'delete':
            # For deletes, embedding may be in old_data
            data = event.data.get('old_data', {}) if event.data else {}
        emb_bytes = data.get(field)
        if emb_bytes is None:
            return None
        # If already a numpy array, return as is
        if isinstance(emb_bytes, np.ndarray):
            return emb_bytes
        # If bytes, decode
        if isinstance(emb_bytes, bytes):
            return np.frombuffer(emb_bytes, dtype=np.float32)
        # If base64 or list, try to convert
        if isinstance(emb_bytes, list):
            return np.array(emb_bytes, dtype=np.float32)
        return None

    def process_term_relationship_event(self, event):
        self.logger.info(f"[EventProcessor] Processing term_relationship event: {event.event_type} id={event.id}")
        # Add your custom logic here

    def _cleanup_loop(self):
        self.logger.info("[EventProcessor] _cleanup_loop() starting")
        while not self._stop_event.is_set():
            try:
                self.logger.debug("[EventProcessor] cleanup_old_events() running...")
                self.cleanup_old_events()
            except Exception as e:
                self.logger.error(f"[EventProcessor] Cleanup error: {e}")
            # Run once per day
            time.sleep(24 * 60 * 60)
        self.logger.info("[EventProcessor] _cleanup_loop() exiting")

    def cleanup_old_events(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM graph_events WHERE processed=1 AND timestamp < ?", (cutoff.isoformat(),))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        if deleted:
            self.logger.info(f"[EventProcessor] Deleted {deleted} old processed events.")
    # Remove duplicate __init__ definition (if present)

    def start(self):
        self.logger.info("[EventProcessor] start() called")
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self.logger.info("[EventProcessor] main thread started")
            self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self._cleanup_thread.start()
            self.logger.info("[EventProcessor] cleanup thread started")

    def stop(self):
        self.logger.info("[EventProcessor] stop() called")
        self._stop_event.set()
        if self._thread:
            self.logger.info("[EventProcessor] joining main thread...")
            self._thread.join(timeout=5)
            self.logger.info("[EventProcessor] main thread joined")
        if self._cleanup_thread:
            self.logger.info("[EventProcessor] joining cleanup thread...")
            self._cleanup_thread.join(timeout=5)
            self.logger.info("[EventProcessor] cleanup thread joined")

    def _run(self):
        self.logger.info("[EventProcessor] _run() loop starting")
        while not self._stop_event.is_set():
            try:
                self.logger.debug("[EventProcessor] processing events...")
                self.process_events()
            except Exception as e:
                self.logger.error(f"[EventProcessor] Error: {e}")
            time.sleep(self.poll_interval)
        self.logger.info("[EventProcessor] _run() loop exiting")

    def process_events(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM graph_events WHERE processed=0 ORDER BY timestamp LIMIT ?", (self.max_events,))
        events = cur.fetchall()
        for event in events:
            entity_type = event['entity_type']
            handler = getattr(self, f"process_{entity_type}_event", None)
            if handler:
                handler(event)
            else:
                self.logger.warning(f"[EventProcessor] No handler for entity_type: {entity_type}")
            cur.execute("UPDATE graph_events SET processed=1 WHERE id=?", (event['id'],))
        conn.commit()
        conn.close()

    def process_layer_event(self, event):
        self.logger.info(f"[EventProcessor] Processing layer event: {event['event_type']} id={event['id']}")
        # Add your custom logic here

    def process_domain_event(self, event):
        self.logger.info(f"[EventProcessor] Processing domain event: {event['event_type']} id={event['id']}")
        # Add your custom logic here

    def process_term_event(self, event):
        self.logger.info(f"[EventProcessor] Processing term event: {event['event_type']} id={event['id']}")
        # Add your custom logic here

    def process_term_relationship_event(self, event):
        self.logger.info(f"[EventProcessor] Processing term_relationship event: {event['event_type']} id={event['id']}")
        # Add your custom logic here

    def _cleanup_loop(self):
        self.logger.info("[EventProcessor] _cleanup_loop() starting")
        while not self._stop_event.is_set():
            try:
                self.logger.debug("[EventProcessor] cleanup_old_events() running...")
                self.cleanup_old_events()
            except Exception as e:
                self.logger.error(f"[EventProcessor] Cleanup error: {e}")
            # Run once per day
            time.sleep(24 * 60 * 60)
        self.logger.info("[EventProcessor] _cleanup_loop() exiting")

    def cleanup_old_events(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM graph_events WHERE processed=1 AND timestamp < ?", (cutoff.isoformat(),))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        if deleted:
            self.logger.info(f"[EventProcessor] Deleted {deleted} old processed events.")
