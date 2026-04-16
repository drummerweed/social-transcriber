import json
import os
import time
from datetime import datetime
import uuid

HISTORY_FILE = "history.json"

class HistoryManager:
    def __init__(self):
        self.history = self._load_history()
        self.cancelled_tasks = set()

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading history: {e}")
                return []
        return []

    def _save_history(self):
        try:
            # Keep only last 100 requests to avoid unlimited growth
            if len(self.history) > 100:
                self.history = self.history[:100]
            
            with open(HISTORY_FILE, 'w') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Error saving history: {e}")

    def add_request(self, url: str, source: str) -> str:
        """
        Adds a new request to history. Returns the request ID.
        """
        req_id = str(uuid.uuid4())
        entry = {
            "id": req_id,
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "source": source,
            "status": "Processing",
            "title": None,
            "notion_url": None,
            "error": None,
            "transcription": None
        }
        self.history.insert(0, entry) # Add to top
        self._save_history()
        return req_id

    def update_request(self, req_id: str, status: str, title: str = None, notion_url: str = None, error: str = None, transcription: str = None):
        """
        Updates an existing request.
        """
        for entry in self.history:
            if entry["id"] == req_id:
                entry["status"] = status
                if title:
                    entry["title"] = title
                if notion_url:
                    entry["notion_url"] = notion_url
                if error:
                    entry["error"] = error
                if transcription:
                    entry["transcription"] = transcription
                self._save_history()
                break

    def get_history(self):
        return self.history

    def remove_request(self, req_id: str):
        """Removes a request from history and cancels it if it's ongoing."""
        self.history = [entry for entry in self.history if entry["id"] != req_id]
        self.cancelled_tasks.add(req_id)
        self._save_history()

history_manager = HistoryManager()
