import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, we'll just skip loading it.
    pass

CONFIG_FILE = "config.json"

class ConfigManager:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        config = {}
        # 1. Load from config.json if it exists (local Pi storage)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Error loading config.json: {e}")
        
        # 2. Override with environment variables (for GitHub/Docker compatibility)
        env_mapping = {
            "NOTION_TOKEN": "notion_token",
            "NOTION_DATABASE_ID": "default_database_id",
            "WEBHOOK_TOKEN": "webhook_token",
            "COOKIES_FILE": "cookies_file"
        }
        
        for env_key, config_key in env_mapping.items():
            value = os.getenv(env_key)
            if value:
                config[config_key] = value
                
        return config

    def save_config(self, new_config: dict):
        self.config.update(new_config)
        # Only save to JSON if it's used locally
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Could not save config to {CONFIG_FILE}: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

config_manager = ConfigManager()
