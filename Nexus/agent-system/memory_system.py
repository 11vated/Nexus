#!/usr/bin/env python3
"""
CONTEXT & MEMORY SYSTEM
Like Claude Code's Memory, Copilot's context
Stores project context, preferences, and conversation history
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

MEMORY_DIR = Path("workspace/memory")
CONTEXT_FILE = MEMORY_DIR / "context.json"
PREFERENCES_FILE = MEMORY_DIR / "preferences.json"
HISTORY_FILE = MEMORY_DIR / "history.json"

@dataclass
class ContextEntry:
    key: str
    value: str
    source: str  # "user", "agent", "system"
    timestamp: str

class MemorySystem:
    """
    Context and memory system like Claude Code / Copilot
    Stores preferences, context, and conversation history
    """
    
    def __init__(self):
        self.memory_dir = MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize
        self.context = self._load_json(CONTEXT_FILE, {})
        self.preferences = self._load_json(PREFERENCES_FILE, {
            "preferred_language": "typescript",
            "preferred_style": "clean",
            "testing_framework": "vitest",
            "fmt_on_save": True,
            "lint_on_save": True,
        })
        self.history = self._load_json(HISTORY_FILE, [])
    
    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except:
                return default
        return default
    
    def _save_json(self, path: Path, data: Any):
        path.write_text(json.dumps(data, indent=2))
    
    def add_context(self, key: str, value: str, source: str = "agent"):
        """Add context entry"""
        self.context[key] = {
            "value": value,
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        self._save_json(CONTEXT_FILE, self.context)
    
    def get_context(self, key: str) -> Optional[str]:
        """Get context value"""
        entry = self.context.get(key)
        return entry["value"] if entry else None
    
    def set_preference(self, key: str, value: Any):
        """Set user preference"""
        self.preferences[key] = value
        self._save_json(PREFERENCES_FILE, self.preferences)
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get user preference"""
        return self.preferences.get(key, default)
    
    def add_to_history(self, role: str, content: str):
        """Add message to history"""
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # Keep last 100 messages
        self.history = self.history[-100:]
        self._save_json(HISTORY_FILE, self.history)
    
    def get_recent_context(self, limit: int = 10) -> List[Dict]:
        """Get recent context entries"""
        return [
            {"key": k, **v} 
            for k, v in list(self.context.items())[-limit:]
        ]
    
    def get_conversation_history(self, limit: int = 20) -> List[Dict]:
        """Get recent conversation"""
        return self.history[-limit:]
    
    def clear_memory(self):
        """Clear all memory"""
        self.context = {}
        self.history = []
        self._save_json(CONTEXT_FILE, {})
        self._save_json(HISTORY_FILE, [])
    
    def summarize_for_context(self) -> str:
        """Get a summary string for context window"""
        prefs = ", ".join([
            f"{k}={v}" for k, v in self.preferences.items()
            if k in ["preferred_language", "preferred_style"]
        ])
        
        recent = self.get_recent_context(5)
        context_str = ", ".join([f"{e['key']}" for e in recent])
        
        return f"""User Preferences: {prefs}
Recent Context: {context_str}
Conversation History: {len(self.history)} messages"""


# Example: How agents use memory
"""
Example usage in prompts:

FROM MEMORY SYSTEM:
- User prefers: {get_preference('preferred_language')}
- Recent work: {get_recent_context(3)}
- Conversation: {get_conversation_history(5)}

This provides agents with memory like Claude Code / Copilot!
"""

def main():
    """Demo"""
    memory = MemorySystem()
    
    # Add some context
    memory.add_context("current_project", "todo-api", "user")
    memory.add_context("last_task", "created user auth", "agent")
    
    # Set preferences
    memory.set_preference("preferred_language", "typescript")
    memory.set_preference("fmt_on_save", True)
    
    # Add to conversation
    memory.add_to_history("user", "Build me an API")
    memory.add_to_history("assistant", "I'll create a REST API for you")
    
    print("=" * 50)
    print("MEMORY SYSTEM")
    print("=" * 50)
    print("\nContext:")
    for key, entry in memory.context.items():
        print(f"  {key}: {entry['value']}")
    
    print(f"\nPreferences:")
    for key, value in memory.preferences.items():
        print(f"  {key}: {value}")
    
    print(f"\nHistory ({len(memory.history)} messages):")
    for msg in memory.history:
        print(f"  {msg['role']}: {msg['content'][:30]}...")
    
    print(f"\nContext Summary:")
    print(memory.summarize_for_context())


if __name__ == "__main__":
    main()