"""Dataset manager for handling multiple SQLite databases."""

import json
import os
import platform
import uuid
import shutil
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from sqlalchemy import create_engine, text

from database.utils import init_db, get_session_local
from dataset.models import DatasetInfo, DatasetMetrics
from utils.logger import get_logger
from database.migrations.migration_manager import MigrationManager

logger = get_logger(__name__)


class DatasetManager:
    """Manages multiple datasets and database switching."""
    
    def __init__(self,
                 datasets_config_path: str = "./datasets.json",
                 datasets_directory: str = None):
        self.config_path = datasets_config_path
        # If datasets_directory is provided, use it. Otherwise try to get from config.
        # If config doesn't have it or it doesn't exist, use default.
        if datasets_directory:
            self.datasets_directory = datasets_directory
        else:
            self.datasets_directory = self._get_datasets_directory_from_config()

        self.active_dataset_id = None
        self.active_engine = None
        self.active_session_local = None
        self.datasets_config = self._load_datasets_config()
        self._ensure_datasets_directory()
        
        # Initialize action log in logs directory
        logs_dir = os.path.join(os.path.dirname(self.config_path), "logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
        self.action_log_path = os.path.join(logs_dir, "dataset_action_log.json")
        self._cleanup_old_log_entries()
        
        # Initialize with most recent dataset by default
        existing_datasets = []
        for dataset_id, dataset_data in self.datasets_config.get("datasets", {}).items():
            dataset_path = self.get_dataset_file_path(dataset_data["filename"])
            if os.path.exists(dataset_path):
                existing_datasets.append((dataset_id, dataset_data))
        
        if existing_datasets:
            # Find most recently accessed dataset
            most_recent_id = max(existing_datasets, 
                               key=lambda x: datetime.fromisoformat(x[1]["last_accessed"]))[0]
            success = self._load_dataset(most_recent_id)
            if not success:
                logger.warning(f"Failed to load most recent dataset: {most_recent_id}")
        else:
            logger.info("No existing datasets found during initialization")
        
        logger.info(f"DatasetManager initialized with datasets directory: {self.datasets_directory}")
    
    def _get_datasets_directory_from_config(self) -> str:
        """Get datasets directory from configuration, with fallback to defaults."""
        try:
            from config import get_settings
            settings = get_settings()

            if settings.database.datasets_directory:
                # Expand ~ to home directory if present
                expanded_path = os.path.expanduser(settings.database.datasets_directory)
                logger.info(f"Using datasets directory from config: {expanded_path}")
                return expanded_path
        except Exception as e:
            logger.warning(f"Could not read datasets_directory from config: {e}")

        # Fall back to default
        return self._get_default_datasets_directory()

    def _get_default_datasets_directory(self) -> str:
        """Get platform-specific default datasets directory."""
        # Check environment variable first
        env_dir = os.getenv('DATASETS_DIRECTORY')
        if env_dir:
            return env_dir

        # Use platform-specific defaults for desktop deployment
        home = os.path.expanduser("~")

        if platform.system() == "Windows":
            return os.path.join(home, "Documents", "ContextStudio", "datasets")
        else:  # macOS and Linux
            return os.path.join(home, "Documents", "ContextStudio", "datasets")
    
    def _load_datasets_config(self) -> Dict:
        """Load datasets configuration from JSON file."""
        if not os.path.exists(self.config_path):
            logger.info(f"No datasets config found at {self.config_path}, creating new one")
            return {
                "active_dataset_id": None,
                "datasets_directory": self.datasets_directory,
                "datasets": {}
            }
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
            # Update datasets_directory if provided in constructor
            if self.datasets_directory != config.get("datasets_directory"):
                config["datasets_directory"] = self.datasets_directory
                self._save_datasets_config(config)
                
            return config
        except Exception as e:
            logger.error(f"Failed to load datasets config: {e}")
            return {
                "active_dataset_id": None,
                "datasets_directory": self.datasets_directory,
                "datasets": {}
            }
    
    def _save_datasets_config(self, config: Dict = None) -> None:
        """Save datasets configuration to JSON file."""
        config = config or self.datasets_config
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save datasets config: {e}")
    
    def _ensure_datasets_directory(self) -> None:
        """Ensure the datasets directory exists."""
        if not os.path.exists(self.datasets_directory):
            try:
                os.makedirs(self.datasets_directory, exist_ok=True)
                logger.info(f"Created datasets directory: {self.datasets_directory}")
            except Exception as e:
                logger.error(f"Failed to create datasets directory {self.datasets_directory}: {e}")
                raise
    
    def _log_action(self, action: str, dataset_id: str, dataset_title: str = None, details: Dict = None) -> None:
        """Log a dataset action to the action log file."""
        try:
            # Load existing log
            action_log = self._load_action_log()
            
            # Create new log entry
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "dataset_id": dataset_id,
                "dataset_title": dataset_title,
                "details": details or {}
            }
            
            # Add to log
            action_log.append(log_entry)
            
            # Save log
            with open(self.action_log_path, 'w') as f:
                json.dump(action_log, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to log action {action} for dataset {dataset_id}: {e}")
    
    def _load_action_log(self) -> List[Dict]:
        """Load the action log from file."""
        if not os.path.exists(self.action_log_path):
            return []
        
        try:
            with open(self.action_log_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load action log: {e}")
            return []
    
    def _cleanup_old_log_entries(self) -> None:
        """Remove log entries older than 30 days."""
        try:
            action_log = self._load_action_log()
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            # Filter out old entries
            filtered_log = [
                entry for entry in action_log
                if datetime.fromisoformat(entry["timestamp"]) > cutoff_date
            ]
            
            # Save filtered log if any entries were removed
            if len(filtered_log) != len(action_log):
                with open(self.action_log_path, 'w') as f:
                    json.dump(filtered_log, f, indent=2, default=str)
                logger.info(f"Cleaned up {len(action_log) - len(filtered_log)} old log entries")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old log entries: {e}")
    
    def get_action_log(self, days: int = 30) -> List[Dict]:
        """Get action log entries for the specified number of days."""
        try:
            action_log = self._load_action_log()
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Filter entries within the specified timeframe
            filtered_log = [
                entry for entry in action_log
                if datetime.fromisoformat(entry["timestamp"]) > cutoff_date
            ]
            
            # Sort by timestamp (most recent first)
            filtered_log.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return filtered_log
            
        except Exception as e:
            logger.error(f"Failed to get action log: {e}")
            return []
    
    def get_dataset_file_path(self, filename: str) -> str:
        """Get the full path to a dataset file."""
        return os.path.join(self.datasets_directory, filename)
    
    def list_datasets(self) -> List[DatasetInfo]:
        """List all known datasets with metrics."""
        datasets = []
        for dataset_id, dataset_data in self.datasets_config.get("datasets", {}).items():
            try:
                # Get current metrics and schema version from database
                metrics = self.get_dataset_metrics(dataset_id)
                schema_version = self.get_dataset_schema_version(dataset_id)
                
                datasets.append(DatasetInfo(
                    id=dataset_id,
                    title=dataset_data["title"],
                    filename=dataset_data["filename"],
                    created_at=datetime.fromisoformat(dataset_data["created_at"]),
                    last_accessed=datetime.fromisoformat(dataset_data["last_accessed"]),
                    schema_version=schema_version,
                    metrics=metrics
                ))
            except Exception as e:
                logger.warning(f"Failed to load dataset {dataset_id}: {e}")
                continue
                
        return datasets
    
    def create_dataset(self, title: str, filename: str) -> DatasetInfo:
        """Create a new dataset."""
        logger.info(f"Creating new dataset with title '{title}' and filename '{filename}'")

        # Ensure filename ends with .db
        if not filename.endswith('.db'):
            filename = f"{filename}.db"
        
        # Check if dataset with this title or filename already exists
        for dataset_data in self.datasets_config.get("datasets", {}).values():
            if dataset_data["title"] == title:
                raise ValueError(f"Dataset with title '{title}' already exists")
            if dataset_data["filename"] == filename:
                raise ValueError(f"Dataset with filename '{filename}' already exists")
        
        dataset_id = str(uuid.uuid4())
        dataset_path = self.get_dataset_file_path(filename)
        
        # Create the database file and initialize schema
        database_url = f"sqlite:///{dataset_path}"
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
        
        try:
            init_db(engine=engine)
            # Run migrations to ensure schema is up to date
            MigrationManager(dataset_path).migrate_to_latest()
            logger.info(f"Created new dataset database: {dataset_path}")
        except Exception as e:
            logger.error(f"Failed to initialize dataset database: {e}")
            raise
        
        # Add to configuration
        now = datetime.now(timezone.utc)
        dataset_info = {
            "id": dataset_id,
            "title": title,
            "filename": filename,
            "created_at": now.isoformat(),
            "last_accessed": now.isoformat(),
            "schema_version": 1  # Starting version
        }
        
        self.datasets_config["datasets"][dataset_id] = dataset_info
        
        # Set as active if no active dataset exists
        if not self.datasets_config.get("active_dataset_id"):
            self.datasets_config["active_dataset_id"] = dataset_id
            self.active_dataset_id = dataset_id
            self.active_engine = engine
            self.active_session_local = get_session_local(engine)
        
        self._save_datasets_config()
        
        # Log the creation action
        self._log_action("create", dataset_id, title, {"filename": filename})
        
        return DatasetInfo(
            id=dataset_id,
            title=title,
            filename=filename,
            created_at=now,
            last_accessed=now,
            schema_version=self.get_dataset_schema_version(dataset_id),
            metrics=DatasetMetrics(
                layers_count=0,
                domains_count=0,
                terms_count=0,
                relationships_count=0
            )
        )
    
    def _load_dataset(self, dataset_id: str) -> bool:
        """Load a dataset without logging it as a switch (used during initialization)."""
        if dataset_id not in self.datasets_config.get("datasets", {}):
            logger.error(f"Dataset {dataset_id} not found")
            return False
        
        dataset_data = self.datasets_config["datasets"][dataset_id]
        dataset_path = self.get_dataset_file_path(dataset_data["filename"])
        
        if not os.path.exists(dataset_path):
            logger.error(f"Dataset file not found: {dataset_path}")
            return False
        
        try:
            # Close existing connections gracefully
            if self.active_engine:
                self.active_engine.dispose()
            
            # Create new connection with proper sqlite-vec extension setup
            database_url = f"sqlite:///{dataset_path}"
            engine = init_db(database_url=database_url)
            
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            # Run migrations to ensure schema is up to date
            MigrationManager(dataset_path).migrate_to_latest()
            # Update active dataset
            self.active_dataset_id = dataset_id
            self.active_engine = engine
            self.active_session_local = get_session_local(engine)
            
            # Update configuration
            self.datasets_config["active_dataset_id"] = dataset_id
            dataset_data["last_accessed"] = datetime.now(timezone.utc).isoformat()
            self._save_datasets_config()
            
            logger.info(f"Loaded dataset: {dataset_data['title']} ({dataset_id}) from {dataset_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load dataset {dataset_id}: {e}")
            return False
    
    def switch_dataset(self, dataset_id: str) -> bool:
        """Switch to the specified dataset."""
        logger.info(f"Switching to dataset {dataset_id}...")
        if dataset_id not in self.datasets_config.get("datasets", {}):
            logger.error(f"Dataset {dataset_id} not found")
            return False
        
        dataset_data = self.datasets_config["datasets"][dataset_id]
        dataset_path = self.get_dataset_file_path(dataset_data["filename"])
        
        if not os.path.exists(dataset_path):
            logger.error(f"Dataset file not found: {dataset_path}")
            return False
        
        # Check if this is actually a switch (different from current active dataset)
        is_actual_switch = self.active_dataset_id != dataset_id
        
        try:
            # Close existing connections gracefully
            if self.active_engine:
                self.active_engine.dispose()
            
            # Create new connection with proper sqlite-vec extension setup
            database_url = f"sqlite:///{dataset_path}"
            engine = init_db(database_url=database_url)
            
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            # Run migrations to ensure schema is up to date
            MigrationManager(dataset_path).migrate_to_latest()
            # Update active dataset
            self.active_dataset_id = dataset_id
            self.active_engine = engine
            self.active_session_local = get_session_local(engine)
            
            # Update configuration
            self.datasets_config["active_dataset_id"] = dataset_id
            dataset_data["last_accessed"] = datetime.now(timezone.utc).isoformat()
            self._save_datasets_config()
            
            # Only log the switch action if this is an actual switch to a different dataset
            if is_actual_switch:
                self._log_action("switch", dataset_id, dataset_data['title'])
            
            logger.info(f"Switched to dataset: {dataset_data['title']} ({dataset_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch to dataset {dataset_id}: {e}")
            return False
    
    def get_active_dataset(self) -> Optional[DatasetInfo]:
        """Get currently active dataset information."""
        if not self.active_dataset_id or self.active_dataset_id not in self.datasets_config.get("datasets", {}):
            return None
        
        dataset_data = self.datasets_config["datasets"][self.active_dataset_id]
        metrics = self.get_dataset_metrics(self.active_dataset_id)
        schema_version = self.get_dataset_schema_version(self.active_dataset_id)
        
        return DatasetInfo(
            id=self.active_dataset_id,
            title=dataset_data["title"],
            filename=dataset_data["filename"],
            created_at=datetime.fromisoformat(dataset_data["created_at"]),
            last_accessed=datetime.fromisoformat(dataset_data["last_accessed"]),
            schema_version=schema_version,
            metrics=metrics
        )
    
    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset."""
        logger.info(f"Deleting dataset {dataset_id}...")
        if dataset_id not in self.datasets_config.get("datasets", {}):
            logger.error(f"Dataset {dataset_id} not found")
            return False
        
        dataset_data = self.datasets_config["datasets"][dataset_id]
        dataset_path = self.get_dataset_file_path(dataset_data["filename"])
        
        try:
            # If this is the active dataset, close connections
            if dataset_id == self.active_dataset_id:
                if self.active_engine:
                    self.active_engine.dispose()
                self.active_dataset_id = None
                self.active_engine = None
                self.active_session_local = None
                self.datasets_config["active_dataset_id"] = None
            
            # Delete the database file
            if os.path.exists(dataset_path):
                os.remove(dataset_path)
                logger.info(f"Deleted dataset file: {dataset_path}")
            
            # Remove from configuration
            del self.datasets_config["datasets"][dataset_id]
            self._save_datasets_config()
            
            # Log the deletion action
            self._log_action("delete", dataset_id, dataset_data['title'], {"filename": dataset_data['filename']})
            
            logger.info(f"Deleted dataset: {dataset_data['title']} ({dataset_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete dataset {dataset_id}: {e}")
            return False
    
    def add_existing_dataset(self, title: str, file_path: str) -> DatasetInfo:
        """Add an existing dataset file to the inventory."""
        logger.info(f"Adding existing dataset with title '{title}' from file '{file_path}'")
        # Validate file exists
        if not os.path.exists(file_path):
            raise ValueError(f"Dataset file does not exist: {file_path}")
        
        # Get just the filename
        filename = os.path.basename(file_path)
        
        # Check for duplicate title
        for dataset in self.datasets_config.get("datasets", {}).values():
            if dataset["title"] == title:
                raise ValueError(f"Dataset with title '{title}' already exists")
        
        # Check for duplicate filename
        for dataset in self.datasets_config.get("datasets", {}).values():
            if dataset["filename"] == filename:
                raise ValueError(f"Dataset with filename '{filename}' already exists")
        
        # If the file is not in our datasets directory, copy it
        expected_path = self.get_dataset_file_path(filename)
        if os.path.abspath(file_path) != os.path.abspath(expected_path):
            shutil.copy2(file_path, expected_path)
            logger.info(f"Copied dataset file from {file_path} to {expected_path}")
            file_path = expected_path
        
        # Validate it's a valid SQLite database
        try:
            database_url = f"sqlite:///{file_path}"
            engine = create_engine(database_url, connect_args={"check_same_thread": False})
            
            # Test connection and basic validation
            with engine.connect() as conn:
                try:
                    # Check if this looks like our schema (either old or new format)
                    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND (name='layers' OR name='structure_nodes')"))
                    if not result.fetchone():
                        raise ValueError("File does not appear to be a valid Context Studio dataset")
                        
                except Exception as e:
                    raise ValueError(f"Invalid dataset file: {e}")
            
            engine.dispose()
            
        except Exception as e:
            # Clean up copied file if validation fails
            if os.path.abspath(file_path) == os.path.abspath(expected_path) and file_path != file_path:
                try:
                    os.remove(expected_path)
                except Exception:
                    pass
            raise ValueError(f"Failed to validate dataset file: {e}")
        
        # Add to configuration
        dataset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        dataset_info = {
            "id": dataset_id,
            "title": title,
            "filename": filename,
            "created_at": now.isoformat(),
            "last_accessed": now.isoformat(),
            "schema_version": 1  # Will be read from database when needed
        }
        
        self.datasets_config["datasets"][dataset_id] = dataset_info
        
        # Set as active if no active dataset exists
        if not self.datasets_config.get("active_dataset_id"):
            self.datasets_config["active_dataset_id"] = dataset_id
            self.active_dataset_id = dataset_id
        
        self._save_datasets_config()
        
        # Log the add action
        self._log_action("add", dataset_id, title, {"filename": filename, "source_path": file_path})
        
        logger.info(f"Added existing dataset: {title} ({dataset_id}) from {file_path}")
        return DatasetInfo(
            id=dataset_id,
            title=title,
            filename=filename,
            created_at=now,
            last_accessed=now,
            schema_version=self.get_dataset_schema_version(dataset_id),
            metrics=self.get_dataset_metrics(dataset_id)
        )
    
    def forget_dataset(self, dataset_id: str) -> bool:
        """Remove a dataset from inventory but leave the file intact."""
        logger.info(f"Forgetting dataset {dataset_id} (file will be preserved)...")
        if dataset_id not in self.datasets_config.get("datasets", {}):
            logger.error(f"Dataset {dataset_id} not found")
            return False
        
        dataset_data = self.datasets_config["datasets"][dataset_id]
        
        try:
            # If this is the active dataset, close connections
            if dataset_id == self.active_dataset_id:
                if self.active_engine:
                    self.active_engine.dispose()
                self.active_dataset_id = None
                self.active_engine = None
                self.active_session_local = None
                self.datasets_config["active_dataset_id"] = None
            
            # Remove from configuration (but leave file intact)
            del self.datasets_config["datasets"][dataset_id]
            self._save_datasets_config()
            
            # Log the forget action
            self._log_action("forget", dataset_id, dataset_data['title'], {"filename": dataset_data['filename']})
            
            logger.info(f"Forgot dataset: {dataset_data['title']} ({dataset_id}) - file preserved")
            return True
            
        except Exception as e:
            logger.error(f"Failed to forget dataset {dataset_id}: {e}")
            return False
    
    def get_startup_behavior_info(self) -> Dict[str, any]:
        """Get information about what dataset will be loaded on startup."""
        datasets = self.list_datasets()
        
        if not datasets:
            return {
                "behavior": "create_default",
                "description": "No datasets exist - will create 'Default Dataset'",
                "dataset": None
            }
        else:
            # Default behavior: load most recent dataset
            most_recent = max(datasets, key=lambda d: d.last_accessed)
            return {
                "behavior": "load_most_recent",
                "description": f"Will load most recent dataset: {most_recent.title}",
                "dataset": most_recent
            }
    
    def get_dataset_schema_version(self, dataset_id: str) -> int:
        """Get the current schema version for a dataset from the database."""
        if dataset_id not in self.datasets_config.get("datasets", {}):
            raise ValueError(f"Dataset {dataset_id} not found")
        
        dataset_data = self.datasets_config["datasets"][dataset_id]
        dataset_path = self.get_dataset_file_path(dataset_data["filename"])
        
        if not os.path.exists(dataset_path):
            logger.warning(f"Dataset file not found: {dataset_path}")
            return 1  # Default schema version
        
        try:
            # Create temporary connection to get schema version from database
            database_url = f"sqlite:///{dataset_path}"
            temp_engine = create_engine(database_url, connect_args={"check_same_thread": False})
            
            with temp_engine.connect() as conn:
                # Check if schema_history table exists
                result = conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_history'"
                )).fetchone()
                
                if result:
                    # Get the latest version from schema_history
                    version_result = conn.execute(text(
                        "SELECT MAX(version) FROM schema_history"
                    )).scalar()
                    schema_version = version_result or 1
                else:
                    # No schema_history table, assume version 1
                    schema_version = 1
            
            temp_engine.dispose()
            return schema_version
            
        except Exception as e:
            logger.error(f"Failed to get schema version for dataset {dataset_id}: {e}")
            return 1  # Default schema version
    
    def get_dataset_metrics(self, dataset_id: str) -> DatasetMetrics:
        if dataset_id not in self.datasets_config.get("datasets", {}):
            raise ValueError(f"Dataset {dataset_id} not found")
        
        dataset_data = self.datasets_config["datasets"][dataset_id]
        dataset_path = self.get_dataset_file_path(dataset_data["filename"])
        
        if not os.path.exists(dataset_path):
            logger.warning(f"Dataset file not found: {dataset_path}")
            return DatasetMetrics(
                layers_count=0,
                domains_count=0,
                terms_count=0,
                relationships_count=0
            )
        
        try:
            # Create temporary connection to get metrics
            database_url = f"sqlite:///{dataset_path}"
            temp_engine = create_engine(database_url, connect_args={"check_same_thread": False})
            
            with temp_engine.connect() as conn:
                # Check if we're using the new unified structure_nodes table (post-migration)
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='structure_nodes'"))
                has_nodes_table = result.fetchone() is not None
                
                # Also check if old tables exist for fallback
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='layers'"))
                has_layers_table = result.fetchone() is not None
                
                if has_nodes_table:
                    # Use unified structure_nodes table (post-Great Normalization)
                    layers_count = conn.execute(text("SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'layer'")).scalar() or 0
                    domains_count = conn.execute(text("SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'domain'")).scalar() or 0
                    terms_count = conn.execute(text("SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'term'")).scalar() or 0
                    relationships_count = conn.execute(text("SELECT COUNT(*) FROM structure_node_links")).scalar() or 0
                elif has_layers_table:
                    # Fall back to old tables (pre-migration)
                    layers_count = conn.execute(text("SELECT COUNT(*) FROM layers")).scalar() or 0
                    domains_count = conn.execute(text("SELECT COUNT(*) FROM domains")).scalar() or 0
                    terms_count = conn.execute(text("SELECT COUNT(*) FROM terms")).scalar() or 0
                    relationships_count = conn.execute(text("SELECT COUNT(*) FROM term_relationships")).scalar() or 0
                else:
                    # No tables found - database might be empty or in transition
                    layers_count = domains_count = terms_count = relationships_count = 0
            
            temp_engine.dispose()
            
            return DatasetMetrics(
                layers_count=layers_count,
                domains_count=domains_count,
                terms_count=terms_count,
                relationships_count=relationships_count
            )
            
        except Exception as e:
            logger.error(f"Failed to get metrics for dataset {dataset_id}: {e}")
            return DatasetMetrics(
                layers_count=0,
                domains_count=0,
                terms_count=0,
                relationships_count=0
            )
    
    def update_datasets_directory(self, new_directory: str) -> bool:
        """Update the datasets directory path."""
        logger.info(f"Updating datasets directory to {new_directory}...")
        try:
            # Ensure new directory exists
            if not os.path.exists(new_directory):
                os.makedirs(new_directory, exist_ok=True)
            
            old_directory = self.datasets_directory
            self.datasets_directory = new_directory
            
            # Update configuration
            self.datasets_config["datasets_directory"] = new_directory
            self._save_datasets_config()
            
            # Log the directory update action
            self._log_action("update_directory", "system", "System", {
                "old_directory": old_directory, 
                "new_directory": new_directory
            })
            
            logger.info(f"Updated datasets directory from {old_directory} to {new_directory}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update datasets directory: {e}")
            return False
