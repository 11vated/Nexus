import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("[WARN] ChromaDB not installed. Run: pip install chromadb")


class VectorMemory:
    def __init__(self, persist_dir: str = "memory_db", collection_name: str = "agent_memory"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        
        if CHROMADB_AVAILABLE:
            self._init_client()
        else:
            print("[WARN] Vector memory disabled - ChromaDB not installed")
    
    def _init_client(self):
        try:
            self.client = chromadb.Client(Settings(
                persist_directory=self.persist_dir,
                anonymized_telemetry=False
            ))
            
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Agent long-term memory"}
            )
            print(f"[MEMORY] Initialized vector store at {self.persist_dir}")
        except Exception as e:
            print(f"[ERROR] Failed to init ChromaDB: {e}")
            self.client = None
    
    def add(self, text: str, metadata: Optional[Dict] = None):
        if not self.collection:
            return "[ERROR] ChromaDB not initialized"
        
        try:
            doc_id = f"doc_{datetime.now().timestamp()}"
            
            meta = metadata or {}
            meta["timestamp"] = datetime.now().isoformat()
            
            self.collection.add(
                documents=[text],
                ids=[doc_id],
                metadatas=[meta]
            )
            return f"[OK] Stored: {doc_id}"
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def query(self, query_text: str, n_results: int = 3) -> List[Dict]:
        if not self.collection:
            return [{"error": "ChromaDB not initialized"}]
        
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            formatted = []
            if results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    formatted.append({
                        "text": doc,
                        "id": results["ids"][0][i] if results.get("ids") else None,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else None,
                        "distance": results["distances"][0][i] if results.get("distances") else None
                    })
            
            return formatted
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_all(self, limit: int = 10) -> List[Dict]:
        if not self.collection:
            return []
        
        try:
            results = self.collection.get()
            
            formatted = []
            for i, doc_id in enumerate(results["ids"]):
                formatted.append({
                    "id": doc_id,
                    "text": results["documents"][i] if i < len(results["documents"]) else "",
                    "metadata": results["metadatas"][i] if i < len(results["metadatas"]) else {}
                })
            
            return formatted[-limit:]
        except Exception as e:
            return [{"error": str(e)}]
    
    def delete(self, doc_id: str) -> str:
        if not self.collection:
            return "[ERROR] ChromaDB not initialized"
        
        try:
            self.collection.delete(ids=[doc_id])
            return f"[OK] Deleted {doc_id}"
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def clear(self) -> str:
        if not self.collection:
            return "[ERROR] ChromaDB not initialized"
        
        try:
            self.client.delete_collection(self.collection_name)
            self._init_client()
            return "[OK] Memory cleared"
        except Exception as e:
            return f"[ERROR] {str(e)}"


class HybridMemory:
    def __init__(self, vector_memory: VectorMemory):
        self.vector = vector_memory
        self.conversation_history = []
    
    def store_interaction(self, role: str, content: str, context: Optional[Dict] = None):
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "context": context or {}
        }
        
        self.conversation_history.append(entry)
        
        if self.vector.collection:
            self.vector.add(
                text=f"{role}: {content}",
                metadata={
                    "role": role,
                    "has_context": bool(context)
                }
            )
    
    def recall_similar(self, query: str, n: int = 3) -> List[Dict]:
        return self.vector.query(query, n_results=n)
    
    def get_conversation_context(self, n_turns: int = 5) -> str:
        recent = self.conversation_history[-n_turns:]
        return "\n".join([f"{e['role']}: {e['content'][:100]}" for e in recent])


def get_embedding(text: str, model: str = "ollama/all-MiniLM-L6-v2") -> List[float]:
    try:
        import subprocess
        result = subprocess.run(
            ["ollama", "embed", model, text],
            capture_output=True,
            text=True,
            timeout=30
        )
        return [float(x) for x in result.stdout.strip().split(",")]
    except Exception as e:
        print(f"[WARN] Embedding failed: {e}")
        return [0.0] * 384