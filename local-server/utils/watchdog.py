import threading
from utils.logger import get_logger

logger = get_logger("watchdog")

def start_watchdog(stop_event, search_details, route="/api/layers/find"):
    """Starts a watchdog thread that logs a warning if a search takes too long."""
    def watchdog():
        waited = 0
        while not stop_event.wait(1 if waited == 0 else 5):
            waited += 1 if waited == 0 else 5
            logger.warning(
                f"[WATCHDOG] {route} running > {waited} seconds. Search details: {search_details}"
            )
    t = threading.Thread(target=watchdog, daemon=True)
    t.start()
    return t
