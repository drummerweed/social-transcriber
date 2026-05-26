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
            "COOKIES_FILE": "cookies_file",
            "STORAGE_DIR": "storage_dir"
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

    def get_storage_dir(self):
        storage_dir = self.get("storage_dir")
        if not storage_dir:
            # Check if the 5TB external drive or pool is mounted
            if os.path.exists("/mnt/nas_drive2"):
                storage_dir = "/mnt/nas_drive2/SocialTranscription_Storage"
            elif os.path.exists("/mnt/nas_pool"):
                storage_dir = "/mnt/nas_pool/SocialTranscription_Storage"
            else:
                # Fallback to local project downloads directory
                storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "downloads"))
        
        os.makedirs(storage_dir, exist_ok=True)
        try:
            os.chmod(storage_dir, 0o777)
        except Exception as e:
            print(f"Error setting permissions on storage directory {storage_dir}: {e}")
        return os.path.abspath(storage_dir)

config_manager = ConfigManager()

