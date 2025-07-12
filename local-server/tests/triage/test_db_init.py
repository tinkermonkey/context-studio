# Ensure project root is on sys.path for imports
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from database.utils import init_db
from utils.logger import get_logger
logger = get_logger(__name__)

logger.info("Initializing database...")
init_db()
logger.info("Database initialized.")
