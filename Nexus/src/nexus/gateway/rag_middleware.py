"""RAG Middleware for unified gateway."""
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime


logger = logging.getLogger(__name__)

# Lazy import — chromadb is optional
chromadb = None  # type: ignore[assignment]

try:
    import chromadb  # type: ignore[no-redef]
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


@dataclass
class RetrievedContext:
    """Retrieved context from RAG."""
    file_path: str
    content: str
    similarity: float
    line_start: int
    line_end: int
    doc_type: str = "code"


class RAGMiddleware:
    """RAG middleware for context injection."""
    
    def __init__(
        self,
        workspace_path: str,
        embed_model: str = "all-MiniLM-L6-v2"
    ):
        self.workspace = Path(workspace_path)
        self.embed_model = embed_model
        self.client = None
        self.collection = None
        
        if CHROMADB_AVAILABLE:
            self._init_chroma()
    
    def _init_chroma(self):
        """Initialize ChromaDB."""
        try:
            chroma_path = self.workspace / ".nexus" / "chroma"
            chroma_path.mkdir(parents=True, exist_ok=True)
            
            self.client = chromadb.PersistentClient(path=str(chroma_path))
            
            embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embed_model
            )
            
            self.collection = self.client.get_or_create_collection(
                name="codebase",
                embedding_function=embed_fn,
                metadata={"description": "Nexus codebase context"}
            )
            
            logger.info(f"ChromaDB initialized at {chroma_path}")
        except Exception as e:
            logger.warning(f"Failed to init ChromaDB: {e}")
            self.client = None
    
    def index_workspace(self, extensions: List[str] = None) -> int:
        """Index all files in workspace."""
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".tsx", ".rs", ".go", ".java", ".json", ".yaml", ".yml"]
        
        exclude_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".nexus"}
        
        files = []
        for ext in extensions:
            for f in self.workspace.rglob(f"*{ext}"):
                if not any(ex in str(f) for ex in exclude_dirs):
                    files.append(f)
        
        indexed = 0
        
        for file_path in files:
            try:
                content = file_path.read_text(errors="ignore")
                
                if len(content) > 100 and len(content) < 50000:
                    doc_id = str(file_path.relative_to(self.workspace))
                    
                    if self.collection:
                        self.collection.upsert(
                            ids=[doc_id],
                            documents=[content[:5000]],
                            metadatas=[{
                                "file": doc_id,
                                "size": len(content),
                                "last_modified": file_path.stat().st_mtime,
                                "extension": file_path.suffix
                            }]
                        )
                        indexed += 1
            except Exception as e:
                logger.debug(f"Skipping {file_path}: {e}")
        
        logger.info(f"Indexed {indexed} files")
        return indexed
    
    def index_codebase_batch(self, paths: list, batch_size: int = 50) -> int:
        """Index files in batches for better performance."""
        total_indexed = 0
        
        for i in range(0, len(paths), batch_size):
            batch = paths[i:i+batch_size]
            docs, metas, ids = [], [], []
            
            for file_path in batch:
                try:
                    content = file_path.read_text(errors="ignore")
                    if len(content) > 100 and len(content) < 50000:
                        docs.append(content[:5000])
                        doc_id = str(file_path.relative_to(self.workspace))
                        ids.append(doc_id)
                        metas.append({
                            "file": str(file_path),
                            "size": len(content),
                            "last_modified": file_path.stat().st_mtime,
                            "extension": file_path.suffix
                        })
                except Exception:
                    continue
            
            if docs and self.collection:
                self.collection.upsert(
                    documents=docs,
                    metadatas=metas,
                    ids=ids
                )
                total_indexed += len(docs)
            
            if i % 200 == 0:
                logger.info(f"Indexed {i + len(batch)} files...")
        
        logger.info(f"Batch indexed {total_indexed} files")
        return total_indexed
    
    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedContext]:
        """Retrieve top-k relevant context."""
        if not self.collection:
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            contexts = []
            
            for i, doc_id in enumerate(results["ids"][0]):
                if results["documents"] and i < len(results["documents"][0]):
                    content = results["documents"][0][i]
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    
                    # Estimate similarity (1 - normalized distance)
                    distance = results["distances"][0][i] if results["distances"] else 0
                    similarity = 1.0 / (1.0 + distance)
                    
                    contexts.append(RetrievedContext(
                        file_path=doc_id,
                        content=content[:2000],
                        similarity=similarity,
                        line_start=1,
                        line_end=len(content.splitlines()),
                        doc_type=metadata.get("extension", "unknown")
                    ))
            
            return contexts
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return []
    
    def inject_context(self, query: str, system_message: str = None) -> Dict[str, Any]:
        """Inject context into model request."""
        contexts = self.retrieve(query, top_k=5)
        
        if not contexts:
            return {"system": system_message or "", "context": []}
        
        context_text = "\n\n".join([
            f"// File: {ctx.file_path}\n{ctx.content[:1500]}"
            for ctx in contexts
        ])
        
        enhanced_system = f"""Relevant code from the codebase:

{context_text}

---
{system_message or 'You are an expert AI coding assistant.'}

When writing code, consider the retrieved context above."""

        return {
            "system": enhanced_system,
            "context": [
                {
                    "file": ctx.file_path,
                    "similarity": ctx.similarity,
                    "type": ctx.doc_type
                }
                for ctx in contexts
            ]
        }
    
    def get_code_graph(self, file_path: str) -> Dict[str, Any]:
        """Extract code structure."""
        try:
            import ast
            
            full_path = self.workspace / file_path
            content = full_path.read_text(errors="ignore")
            
            tree = ast.parse(content)
            
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [a.arg for a in node.args.args]
                    })
                elif isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": methods
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            
            return {
                "functions": functions,
                "classes": classes,
                "imports": imports[:20],  # Limit to first 20
                "file": file_path
            }
        except Exception as e:
            logger.warning(f"Code graph extraction failed: {e}")
            return {"functions": [], "classes": [], "imports": []}
    
    def get_git_history(self, file_path: str, days: int = 30) -> List[Dict]:
        """Get recent git history for a file."""
        rel_path = str(Path(file_path).relative_to(self.workspace))
        
        try:
            result = subprocess.run(
                ["git", "log", f"--since={days}.days.ago", 
                 "--oneline", "--format=%h %s", "-20", "--", rel_path],
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=10
            )
            
            if result.returncode == 0:
                commits = []
                for line in result.stdout.strip().split("\n"):
                    if " " in line:
                        commit_hash, message = line.split(" ", 1)
                        commits.append({
                            "hash": commit_hash,
                            "message": message
                        })
                return commits
        except Exception as e:
            logger.warning(f"Git history retrieval failed: {e}")
        
        return []


class DynamicRAG:
    """Dynamic RAG that adjusts context based on task type."""
    
    def __init__(self, workspace: str):
        self.rag = RAGMiddleware(workspace)
        self.workspace = Path(workspace)
    
    def get_context_for_task(self, task: str, files: List[str] = None) -> Dict[str, Any]:
        """Get appropriate context based on task type."""
        task_lower = task.lower()
        
        # Determine retrieval strategy
        if "bug" in task_lower or "fix" in task_lower:
            return self._get_fix_context(task, files)
        elif "refactor" in task_lower:
            return self._get_refactor_context(task, files)
        elif "test" in task_lower:
            return self._get_test_context(task, files)
        else:
            return self.rag.inject_context(task)
    
    def _get_fix_context(self, task: str, files: List[str] = None) -> Dict[str, Any]:
        """Context optimized for bug fixing."""
        # Get general context first
        base = self.rag.inject_context(task)
        
        # Add git history for relevant files
        if files:
            git_context = []
            for f in files:
                history = self.rag.get_git_history(f, days=60)
                if history:
                    git_context.append({
                        "file": f,
                        "recent_commits": history[:5]
                    })
            
            base["git_history"] = git_context
            base["context"].append({
                "type": "git_history",
                "note": "Recent commits for bug hunting"
            })
        
        return base
    
    def _get_refactor_context(self, task: str, files: List[str] = None) -> Dict[str, Any]:
        """Context optimized for refactoring."""
        context_data = self.rag.inject_context(task)
        
        # Add code graph for all relevant files
        if files:
            code_graphs = {}
            for f in files:
                graph = self.rag.get_code_graph(f)
                if graph["functions"] or graph["classes"]:
                    code_graphs[f] = graph
            
            context_data["code_graphs"] = code_graphs
        
        return context_data
    
    def _get_test_context(self, task: str, files: List[str] = None) -> Dict[str, Any]:
        """Context optimized for test writing."""
        injected = self.rag.inject_context(task)
        
        # Find related source files for test context
        if files:
            related_sources = []
            for f in files:
                if not f.endswith("_test.py") and not f.endswith(".test.py"):
                    source_file = str(Path(f).with_suffix("_test.py"))
                    if (self.workspace / source_file).exists():
                        related_sources.append(source_file)
            
            if related_sources:
                injected["related_tests"] = related_sources
        
        return injected


# Global instance
rag_middleware = None


def get_rag_middleware(workspace: str = None) -> Optional[RAGMiddleware]:
    """Get or create RAG middleware."""
    global rag_middleware
    
    if workspace is None:
        from pathlib import Path
        workspace = str(Path.cwd())
    
    if rag_middleware is None:
        rag_middleware = DynamicRAG(workspace)
    
    return rag_middleware