import os
from pathlib import Path


def write_file(path, content):
    try:
        file_path = Path(path)
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return f"[SUCCESS] Wrote {len(content)} chars to {path}"
    
    except Exception as e:
        return f"[ERROR] {str(e)}"


def write_file_from_llm(instruction, workspace="workspace"):
    return "[ERROR] Direct file write requires more context. Use Aider instead."


def read_file(path):
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            return f"[ERROR] File not found: {path}"
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return content
    
    except Exception as e:
        return f"[ERROR] {str(e)}"


def list_files(directory=".", pattern="*"):
    try:
        path = Path(directory)
        files = list(path.glob(pattern))
        return "\n".join([f.name for f in files])
    
    except Exception as e:
        return f"[ERROR] {str(e)}"