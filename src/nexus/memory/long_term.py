"""Long-term memory — persistent vector store for semantic retrieval.

Wraps ChromaDB (when available) or falls back to keyword search.
Builds on the existing rag_middleware.py infrastructure.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MemoryDocument:
    """A document stored in long-term memory."""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    timestamp: float = field(default_factory=time.time)


class LongTermMemory:
    """Persistent memory with semantic search.

    Uses ChromaDB for vector storage when available, falls back to
    keyword-based search otherwise. Stores task results, code snippets,
    and learned patterns for future retrieval.
    """

    def __init__(self, persist_dir: str = ".nexus_memory"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._collection = None
        self._fallback_docs: List[MemoryDocument] = []
        self._use_chroma = False

        self._init_backend()

    def _init_backend(self) -> None:
        """Try to initialize ChromaDB, fall back to JSON."""
        try:
            import chromadb  # noqa: F401
            client = chromadb.PersistentClient(path=str(self.persist_dir / "chroma"))
            self._collection = client.get_or_create_collection(
                name="nexus_memory",
                metadata={"hnsw:space": "cosine"},
            )
            self._use_chroma = True
            logger.info("Long-term memory: ChromaDB initialized")
        except ImportError:
            logger.info("Long-term memory: ChromaDB not available, using JSON fallback")
            self._load_fallback()
        except Exception as exc:
            logger.warning("ChromaDB init failed, using fallback: %s", exc)
            self._load_fallback()

    def _load_fallback(self) -> None:
        """Load fallback JSON store."""
        path = self.persist_dir / "memory.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._fallback_docs = [
                    MemoryDocument(**doc) for doc in data
                ]
            except (json.JSONDecodeError, TypeError):
                self._fallback_docs = []

    def _save_fallback(self) -> None:
        """Save fallback JSON store."""
        path = self.persist_dir / "memory.json"
        data = [
            {
                "id": doc.id,
                "content": doc.content,
                "metadata": doc.metadata,
                "timestamp": doc.timestamp,
            }
            for doc in self._fallback_docs
        ]
        path.write_text(json.dumps(data, indent=2))

    def store(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """Store a document in long-term memory.

        Args:
            content: The text content to store.
            metadata: Optional metadata (tags, source, etc).
            doc_id: Optional explicit ID (auto-generated if not provided).

        Returns:
            The document ID.
        """
        if not doc_id:
            doc_id = hashlib.sha256(content.encode()).hexdigest()[:16]

        metadata = metadata or {}
        metadata["stored_at"] = time.time()

        if self._use_chroma and self._collection:
            self._collection.upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata],
            )
        else:
            # Fallback: append to JSON list
            doc = MemoryDocument(
                id=doc_id,
                content=content,
                metadata=metadata,
            )
            # Update if exists, else append
            existing = [i for i, d in enumerate(self._fallback_docs) if d.id == doc_id]
            if existing:
                self._fallback_docs[existing[0]] = doc
            else:
                self._fallback_docs.append(doc)
            self._save_fallback()

        logger.debug("Stored document: %s (%d chars)", doc_id, len(content))
        return doc_id

    def search(
        self,
        query: str,
        n_results: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, str, float]]:
        """Search for relevant documents.

        Args:
            query: Search query.
            n_results: Maximum number of results.
            metadata_filter: Optional metadata filter.

        Returns:
            List of (doc_id, content, relevance_score) tuples.
        """
        if self._use_chroma and self._collection:
            try:
                kwargs: Dict[str, Any] = {
                    "query_texts": [query],
                    "n_results": min(n_results, self._collection.count() or 1),
                }
                if metadata_filter:
                    kwargs["where"] = metadata_filter

                results = self._collection.query(**kwargs)

                output = []
                if results and results.get("ids"):
                    for i, doc_id in enumerate(results["ids"][0]):
                        content = results["documents"][0][i] if results.get("documents") else ""
                        distance = results["distances"][0][i] if results.get("distances") else 0.0
                        score = 1.0 - distance  # Convert distance to similarity
                        output.append((doc_id, content, score))
                return output
            except Exception as exc:
                logger.warning("ChromaDB search failed: %s", exc)

        # Fallback: keyword search
        return self._keyword_search(query, n_results)

    def _keyword_search(
        self, query: str, n_results: int
    ) -> List[Tuple[str, str, float]]:
        """Simple keyword-based search fallback."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for doc in self._fallback_docs:
            content_lower = doc.content.lower()
            # Score: fraction of query words found in document
            matches = sum(1 for w in query_words if w in content_lower)
            if matches > 0:
                score = matches / len(query_words) if query_words else 0
                scored.append((doc.id, doc.content, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:n_results]

    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        if self._use_chroma and self._collection:
            try:
                self._collection.delete(ids=[doc_id])
                return True
            except Exception:
                return False

        before = len(self._fallback_docs)
        self._fallback_docs = [d for d in self._fallback_docs if d.id != doc_id]
        if len(self._fallback_docs) < before:
            self._save_fallback()
            return True
        return False

    @property
    def count(self) -> int:
        """Number of stored documents."""
        if self._use_chroma and self._collection:
            return self._collection.count()
        return len(self._fallback_docs)
