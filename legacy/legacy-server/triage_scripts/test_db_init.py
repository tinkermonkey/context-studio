# Ensure project root is on sys.path for imports
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.utils import init_db
from utils.logger import get_logger

logger = get_logger(__name__)

logger.info("Initializing database...")
init_db()
logger.info("Database initialized.")
