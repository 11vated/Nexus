"""Context retrieval with vector index for SWE-bench issues."""
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


@dataclass
class RetrievedContext:
    """Retrieved context from the codebase."""
    file_path: Path
    content: str
    similarity_score: float
    line_start: int
    line_end: int


class ContextRetriever:
    """Retrieve relevant codebase context for issues."""
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.cwd()
        self._index_inited = False
    
    def init_index(self) -> bool:
        """Initialize the vector index."""
        CHROMADB_AVAILABLE = False
        
        try:
            import chromadb
            from chromadb.config import Settings
            CHROMADB_AVAILABLE = True
        except ImportError:
            pass
        
        if not CHROMADB_AVAILABLE:
            logger.warning("chromadb not available, using fallback retrieval")
            self._index_inited = False
            return False
        
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.workspace / ".nexus" / "vector_index")
            )
            self.collection = self.client.get_or_create_collection(
                name="codebase",
                metadata={"description": "Nexus codebase context"}
            )
            self._index_inited = True
            return True
        except Exception as e:
            logger.warning(f"Failed to init vector index: {e}")
            return False
    
    def index_codebase(self, extensions: List[str] = None) -> int:
        """Index all files in workspace."""
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".tsx", ".rs", ".go", ".java"]
        
        files = []
        exclude_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
        
        for ext in extensions:
            for f in self.workspace.rglob(f"*{ext}"):
                if not any(ex in f.parts for ex in exclude_dirs):
                    files.append(f)
        
        indexed = 0
        
        for file_path in files:
            try:
                content = file_path.read_text(errors="ignore")
                if len(content) > 100:  # Skip tiny files
                    doc_id = str(file_path.relative_to(self.workspace))
                    
                    if self._index_inited and hasattr(self, 'collection'):
                        self.collection.upsert(
                            ids=[doc_id],
                            documents=[content[:5000]],  # Truncate for embedding
                            metadatas=[{
                                "file": doc_id,
                                "size": len(content)
                            }]
                        )
                        indexed += 1
            except Exception as e:
                logger.debug(f"Skipping {file_path}: {e}")
        
        logger.info(f"Indexed {indexed} files")
        return indexed
    
    def retrieve_for_issue(
        self,
        issue_description: str,
        top_k: int = 5
    ) -> List[RetrievedContext]:
        """Retrieve most relevant files for an issue."""
        if self._index_inited and hasattr(self, 'collection'):
            return self._retrieve_from_index(issue_description, top_k)
        else:
            return self._retrieve_fallback(issue_description, top_k)
    
    def _retrieve_from_index(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievedContext]:
        """Retrieve from vector index."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            contexts = []
            for i, doc_id in enumerate(results["ids"][0]):
                file_path = self.workspace / doc_id
                if file_path.exists():
                    content = file_path.read_text(errors="ignore")
                    contexts.append(RetrievedContext(
                        file_path=file_path,
                        content=content[:2000],
                        similarity_score=1.0 - (i * 0.1),
                        line_start=1,
                        line_end=len(content.splitlines())
                    ))
            
            return contexts
        except Exception as e:
            logger.warning(f"Vector retrieval failed: {e}")
            return []
    
    def _retrieve_fallback(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievedContext]:
        """Fallback retrieval using keyword matching."""
        query_words = set(query.lower().split())
        scores = []
        
        exclude_dirs = {".git", "node_modules", "__pycache__", ".venv"}
        
        for py_file in self.workspace.rglob("*.py"):
            if any(ex in py_file.parts for ex in exclude_dirs):
                continue
            
            try:
                content = py_file.read_text(errors="ignore")
                content_lower = content.lower()
                
                # Score by keyword matches
                score = sum(1 for word in query_words if word in content_lower)
                
                if score > 0:
                    scores.append((score, py_file, content))
            except Exception:
                continue
        
        # Sort by score and return top_k
        scores.sort(reverse=True, key=lambda x: x[0])
        
        results = []
        for score, file_path, content in scores[:top_k]:
            lines = content.splitlines()
            results.append(RetrievedContext(
                file_path=file_path,
                content=content[:2000],
                similarity_score=score / len(query_words),
                line_start=1,
                line_end=len(lines)
            ))
        
        return results
    
    def get_git_history(self, file_path: Path, recent: int = 5) -> List[Dict]:
        """Get git history for a file (useful for bug hunting)."""
        file_path = Path(file_path)
        rel_path = file_path.relative_to(self.workspace) if file_path.is_relative_to(self.workspace) else file_path
        
        try:
            result = subprocess.run(
                ["git", "log", f"-{recent}", "--oneline", "--", str(rel_path)],
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=10
            )
            
            if result.returncode == 0:
                commits = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        commits.append({"message": line})
                return commits
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return []
    
    def get_file_around_line(self, file_path: Path, line: int, 
                            context: int = 10) -> str:
        """Get content around a specific line."""
        try:
            content = file_path.read_text(errors="ignore")
            lines = content.splitlines()
            
            start = max(0, line - context - 1)
            end = min(len(lines), line + context)
            
            return "\n".join(f"{i+1}: {lines[i]}" for i in range(start, end))
        except Exception as e:
            return f"Error reading file: {e}"
    
    def search_by_pattern(self, pattern: str, file_type: str = "*.py") -> List[Tuple[Path, int]]:
        """Search for a pattern in files."""
        matches = []
        
        try:
            import re
            regex = re.compile(pattern)
            
            for f in self.workspace.rglob(file_type):
                try:
                    lines = f.read_text(errors="ignore").splitlines()
                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            matches.append((f, i))
                except Exception:
                    continue
        except re.error:
            # Fall back to simple string search
            for f in self.workspace.rglob(file_type):
                try:
                    lines = f.read_text(errors="ignore").splitlines()
                    for i, line in enumerate(lines, 1):
                        if pattern in line:
                            matches.append((f, i))
                except Exception:
                    continue
        
        return matches


# Global instance
context_retriever = ContextRetriever()