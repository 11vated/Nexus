import json
import os
from datetime import datetime
from pathlib import Path


class Memory:
    def __init__(self, path="memory.json", short_term_window=10):
        self.path = path
        self.short_term_window = short_term_window
        self.short_term = []
        
        self._ensure_file()
    
    def _ensure_file(self):
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump({
                    "interactions": [],
                    "created": datetime.now().isoformat()
                }, f, indent=2)
    
    def add_interaction(self, prompt, role, content):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt if role == "task_received" else None,
            "role": role,
            "content": content
        }
        
        self.short_term.append(entry)
        
        if len(self.short_term) > self.short_term_window:
            self.short_term.pop(0)
        
        self._save_to_disk(entry)
    
    def _save_to_disk(self, entry):
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {"interactions": []}
        
        data.setdefault("interactions", []).append(entry)
        
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_recent(self, n=5):
        return self.short_term[-n:] if len(self.short_term) <= n else self.short_term
    
    def search(self, query):
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            
            results = []
            for entry in data.get("interactions", []):
                if query.lower() in str(entry.get("content", "")).lower():
                    results.append(entry)
            
            return results[-5:]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def get_context(self):
        recent = self.get_recent(3)
        context_parts = []
        for entry in recent:
            if entry.get("role") == "step_completed":
                context_parts.append(f"Last: {entry.get('content', '')[:100]}")
        
        return "\n".join(context_parts)