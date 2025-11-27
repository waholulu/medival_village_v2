import json
import os
import time
from typing import Any, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.utils.logger import Logger, LogCategory

class ConfigHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith("balance.json"):
            # Give file system a moment to flush
            time.sleep(0.1)
            self.callback()

class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.observer = Observer()
        
        # Initial load
        self.load_config()
        
        # Setup watcher
        directory = os.path.dirname(os.path.abspath(config_path))
        handler = ConfigHandler(self.load_config)
        self.observer.schedule(handler, directory, recursive=False)
        self.observer.start()
        
        Logger.info(f"ConfigManager watching: {config_path}")

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            Logger.log(LogCategory.SYSTEM, "Config loaded successfully")
        except Exception as e:
            Logger.error(f"Failed to load config: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value using dot notation (e.g. "entities.villager.speed")
        """
        keys = key_path.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def stop(self):
        self.observer.stop()
        self.observer.join()

