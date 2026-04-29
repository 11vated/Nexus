"""Project Intelligence — deep understanding of the codebase.

Before the user even asks a question, Nexus builds a mental model of
the project: what files exist, how they connect, what's important,
and what kind of project this is.

This means when the user says "fix the API", Nexus already knows:
- Which files are the API (not just guessing from filenames)
- What the API depends on
- Where the tests for it live
- What framework it uses

No other local AI tool does this. Cloud tools have some of it via
indexing, but Nexus does it entirely on-device with zero upload.

Usage:
    pmap = ProjectMap("/path/to/project")
    pmap.scan()

    # What kind of project is this?
    pmap.project_type          # "fastapi_app"
    pmap.frameworks            # ["fastapi", "sqlalchemy", "pytest"]

    # What files matter most?
    pmap.hot_files()           # [("src/api/routes.py", 0.95), ...]

    # What does this file depend on?
    pmap.dependencies("src/api/routes.py")  # ["src/models.py", "src/db.py"]

    # Smart context: when user mentions "the API"
    pmap.resolve_concept("API")  # ["src/api/routes.py", "src/api/middleware.py"]
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Project type detection
# ---------------------------------------------------------------------------

@dataclass
class ProjectSignature:
    """Signals that identify a project type."""
    project_type: str
    display_name: str
    indicators: List[str]       # Files/patterns that indicate this type
    frameworks: List[str]       # Associated frameworks
    entry_points: List[str]     # Likely entry point patterns


_PROJECT_SIGNATURES = [
    ProjectSignature(
        project_type="fastapi_app",
        display_name="FastAPI Application",
        indicators=["fastapi", "uvicorn", "@app.get", "@app.post", "@router."],
        frameworks=["fastapi", "uvicorn", "pydantic"],
        entry_points=["main.py", "app.py", "server.py", "api.py"],
    ),
    ProjectSignature(
        project_type="flask_app",
        display_name="Flask Application",
        indicators=["flask", "@app.route", "Flask(__name__)"],
        frameworks=["flask"],
        entry_points=["app.py", "main.py", "wsgi.py"],
    ),
    ProjectSignature(
        project_type="django_app",
        display_name="Django Application",
        indicators=["django", "INSTALLED_APPS", "urlpatterns", "models.Model"],
        frameworks=["django"],
        entry_points=["manage.py", "wsgi.py", "asgi.py"],
    ),
    ProjectSignature(
        project_type="cli_tool",
        display_name="CLI Tool",
        indicators=["click", "argparse", "typer", "@cli.command", "ArgumentParser"],
        frameworks=["click", "typer", "argparse"],
        entry_points=["cli.py", "main.py", "__main__.py"],
    ),
    ProjectSignature(
        project_type="library",
        display_name="Python Library",
        indicators=["setup.py", "pyproject.toml", "__init__.py"],
        frameworks=[],
        entry_points=["__init__.py"],
    ),
    ProjectSignature(
        project_type="nextjs_app",
        display_name="Next.js Application",
        indicators=["next.config", "pages/", "app/", "getServerSideProps", "useRouter"],
        frameworks=["next", "react"],
        entry_points=["pages/index", "app/page", "src/app/page"],
    ),
    ProjectSignature(
        project_type="react_app",
        display_name="React Application",
        indicators=["react", "jsx", "tsx", "useState", "useEffect", "ReactDOM"],
        frameworks=["react"],
        entry_points=["src/App", "src/index", "src/main"],
    ),
    ProjectSignature(
        project_type="node_api",
        display_name="Node.js API",
        indicators=["express", "koa", "fastify", "app.listen", "router.get"],
        frameworks=["express", "node"],
        entry_points=["index.js", "server.js", "app.js", "src/index.js"],
    ),
]


# ---------------------------------------------------------------------------
# File importance scoring
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    """Metadata about a single file in the project."""
    path: str
    size_bytes: int = 0
    line_count: int = 0
    language: str = ""
    imports: List[str] = field(default_factory=list)
    imported_by: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)  # Detected concepts
    importance: float = 0.0  # 0-1 importance score


# ---------------------------------------------------------------------------
# ProjectMap
# ---------------------------------------------------------------------------

class ProjectMap:
    """Deep project understanding engine.

    Scans a project directory and builds a rich model of:
    - File structure and languages
    - Import/dependency graph
    - Project type and frameworks
    - File importance rankings
    - Concept-to-file mapping (so "the API" resolves to actual files)

    All analysis is local — no data leaves the machine.
    """

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()
        self.files: Dict[str, FileInfo] = {}
        self.project_type: str = "unknown"
        self.project_name: str = self.workspace.name
        self.frameworks: List[str] = []
        self.languages: Dict[str, int] = {}  # lang → file count
        self._concept_index: Dict[str, List[str]] = {}  # concept → [file paths]
        self._import_graph: Dict[str, Set[str]] = defaultdict(set)  # file → {imported files}
        self._scanned: bool = False

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    # File extensions to language mapping
    _EXT_MAP = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "react", ".tsx": "react-ts", ".rs": "rust",
        ".go": "go", ".java": "java", ".rb": "ruby",
        ".cpp": "cpp", ".c": "c", ".h": "c-header",
        ".css": "css", ".html": "html", ".md": "markdown",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".toml": "toml", ".sql": "sql", ".sh": "shell",
        ".dockerfile": "docker", ".tf": "terraform",
    }

    # Directories to skip
    _SKIP_DIRS = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "dist", "build", "egg-info", ".nexus_memory", ".eggs",
    }

    def scan(self, max_files: int = 2000) -> "ProjectMap":
        """Scan the project and build the map.

        This is fast — it reads file metadata and does lightweight
        content analysis, not full parsing.

        Returns self for chaining.
        """
        self.files.clear()
        self.languages.clear()
        self._concept_index.clear()
        self._import_graph.clear()

        file_count = 0

        for root, dirs, filenames in os.walk(self.workspace):
            # Prune skipped directories
            dirs[:] = [d for d in dirs if d not in self._SKIP_DIRS and not d.startswith(".")]

            for fname in filenames:
                if file_count >= max_files:
                    break

                fpath = Path(root) / fname
                rel_path = str(fpath.relative_to(self.workspace))

                ext = fpath.suffix.lower()
                if ext not in self._EXT_MAP and fname.lower() not in ("dockerfile", "makefile"):
                    continue

                lang = self._EXT_MAP.get(ext, "")
                if fname.lower() == "dockerfile":
                    lang = "docker"

                try:
                    stat = fpath.stat()
                    size = stat.st_size
                except OSError:
                    continue

                # Skip very large files
                if size > 500_000:
                    continue

                info = FileInfo(
                    path=rel_path,
                    size_bytes=size,
                    language=lang,
                )

                # Quick content analysis for Python files
                if lang == "python" and size < 100_000:
                    self._analyze_python_file(fpath, info)
                elif lang in ("javascript", "typescript", "react", "react-ts"):
                    self._analyze_js_file(fpath, info)

                self.files[rel_path] = info
                self.languages[lang] = self.languages.get(lang, 0) + 1
                file_count += 1

        # Build cross-references
        self._build_import_graph()
        self._detect_project_type()
        self._score_importance()
        self._build_concept_index()
        self._scanned = True

        logger.info(
            "ProjectMap: %d files, type=%s, frameworks=%s",
            len(self.files), self.project_type, self.frameworks,
        )
        return self

    def _analyze_python_file(self, fpath: Path, info: FileInfo) -> None:
        """Lightweight Python file analysis."""
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            info.line_count = content.count("\n") + 1

            # Extract imports
            for line in content.splitlines()[:100]:  # First 100 lines
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    info.imports.append(line)

            # Extract concepts from class/function names
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        info.concepts.append(node.name)
                    elif isinstance(node, ast.FunctionDef):
                        if not node.name.startswith("_"):
                            info.concepts.append(node.name)
            except SyntaxError:
                pass

        except (OSError, UnicodeDecodeError):
            pass

    def _analyze_js_file(self, fpath: Path, info: FileInfo) -> None:
        """Lightweight JS/TS file analysis."""
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            info.line_count = content.count("\n") + 1

            # Extract imports
            for match in re.finditer(
                r'''(?:import|require)\s*(?:\{[^}]*\}\s*from\s*)?['"]([^'"]+)['"]''',
                content,
            ):
                info.imports.append(match.group(0))

            # Extract exported names
            for match in re.finditer(
                r'export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)',
                content,
            ):
                info.concepts.append(match.group(1))

        except (OSError, UnicodeDecodeError):
            pass

    def _build_import_graph(self) -> None:
        """Build the import dependency graph."""
        for path, info in self.files.items():
            if info.language != "python":
                continue
            for imp in info.imports:
                # Try to resolve import to a local file
                resolved = self._resolve_import(imp)
                if resolved and resolved in self.files:
                    self._import_graph[path].add(resolved)
                    self.files[resolved].imported_by.append(path)

    def _resolve_import(self, import_line: str) -> Optional[str]:
        """Try to resolve a Python import to a local file path."""
        # from nexus.agent.chat import ChatSession → nexus/agent/chat.py
        match = re.match(r'from\s+([\w.]+)\s+import', import_line)
        if match:
            module = match.group(1)
        else:
            match = re.match(r'import\s+([\w.]+)', import_line)
            if match:
                module = match.group(1)
            else:
                return None

        # Convert module path to file path
        parts = module.split(".")
        # Try both src/module/path.py and module/path.py
        for prefix in ["src/", ""]:
            candidate = prefix + "/".join(parts) + ".py"
            if candidate in self.files:
                return candidate
            candidate = prefix + "/".join(parts) + "/__init__.py"
            if candidate in self.files:
                return candidate

        return None

    def _detect_project_type(self) -> None:
        """Detect what kind of project this is."""
        # Collect all content signals
        signals: List[str] = []

        # Check file contents for framework indicators
        for info in self.files.values():
            signals.extend(info.imports)
            signals.extend(info.concepts)

        # Check for config files and also scan raw content for decorators/patterns
        for fname in self.files:
            signals.append(fname)
            fpath = Path(self.workspace) / fname
            try:
                if fpath.stat().st_size < 100_000:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                    # Capture framework-specific patterns (decorators, calls)
                    for line in content.splitlines()[:200]:
                        stripped = line.strip()
                        if stripped.startswith("@") or "(" in stripped:
                            signals.append(stripped)
            except (OSError, UnicodeDecodeError):
                pass

        signal_text = " ".join(signals).lower()

        best_match = None
        best_score = 0

        for sig in _PROJECT_SIGNATURES:
            score = sum(1 for ind in sig.indicators if ind.lower() in signal_text)
            if score > best_score:
                best_score = score
                best_match = sig

        if best_match and best_score >= 2:
            self.project_type = best_match.project_type
            self.frameworks = best_match.frameworks[:]
        else:
            # Detect by primary language
            if self.languages:
                primary = max(self.languages, key=lambda k: self.languages[k])
                self.project_type = f"{primary}_project"

    def _score_importance(self) -> None:
        """Score file importance based on multiple signals."""
        if not self.files:
            return

        max_imports = max(
            (len(info.imported_by) for info in self.files.values()),
            default=1,
        ) or 1

        for path, info in self.files.items():
            score = 0.0

            # Signal 1: How many other files import this one (0-0.3)
            score += (len(info.imported_by) / max_imports) * 0.3

            # Signal 2: Is it an entry point or config? (0-0.2)
            basename = Path(path).name.lower()
            if basename in ("main.py", "app.py", "cli.py", "__main__.py", "server.py"):
                score += 0.2
            elif basename in ("pyproject.toml", "package.json", "Dockerfile"):
                score += 0.15
            elif basename == "__init__.py":
                score += 0.05

            # Signal 3: File size (moderate files are more important than tiny/huge)
            if 100 < info.line_count < 500:
                score += 0.15
            elif info.line_count >= 500:
                score += 0.1

            # Signal 4: Has many exports/concepts (it's a hub)
            if len(info.concepts) > 5:
                score += 0.15
            elif len(info.concepts) > 2:
                score += 0.1

            # Signal 5: Test files get a boost (they tell us what's tested)
            if "test" in path.lower():
                score += 0.1

            info.importance = min(score, 1.0)

    def _build_concept_index(self) -> None:
        """Build reverse index: concept name → file paths.

        This enables "smart context" — when the user says "the API",
        we know which files they probably mean.
        """
        for path, info in self.files.items():
            # Index by concept names
            for concept in info.concepts:
                key = concept.lower()
                if key not in self._concept_index:
                    self._concept_index[key] = []
                self._concept_index[key].append(path)

            # Index by filename stem
            stem = Path(path).stem.lower()
            if stem not in self._concept_index:
                self._concept_index[stem] = []
            self._concept_index[stem].append(path)

            # Index by directory name
            parts = Path(path).parts
            for part in parts[:-1]:
                key = part.lower()
                if key not in self._concept_index:
                    self._concept_index[key] = []
                if path not in self._concept_index[key]:
                    self._concept_index[key].append(path)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def hot_files(self, n: int = 10) -> List[Tuple[str, float]]:
        """Get the N most important files.

        Returns list of (path, importance_score) tuples.
        """
        ranked = sorted(
            self.files.items(),
            key=lambda x: x[1].importance,
            reverse=True,
        )
        return [(path, info.importance) for path, info in ranked[:n]]

    def dependencies(self, file_path: str) -> List[str]:
        """Get files that this file depends on (imports)."""
        return list(self._import_graph.get(file_path, set()))

    def dependents(self, file_path: str) -> List[str]:
        """Get files that depend on this file (imported_by)."""
        info = self.files.get(file_path)
        if info:
            return list(info.imported_by)
        return []

    def resolve_concept(self, concept: str) -> List[str]:
        """Resolve a concept name to file paths.

        The user says "the API" — this returns the files most likely
        related to "API" in this project.
        """
        key = concept.lower().strip()
        results = []

        # Exact match
        if key in self._concept_index:
            results.extend(self._concept_index[key])

        # Partial match
        for indexed_key, paths in self._concept_index.items():
            if key in indexed_key or indexed_key in key:
                for p in paths:
                    if p not in results:
                        results.append(p)

        # Sort by importance
        results.sort(
            key=lambda p: self.files.get(p, FileInfo(path=p)).importance,
            reverse=True,
        )
        return results[:10]

    def file_context(self, file_path: str) -> Dict[str, Any]:
        """Get rich context about a specific file."""
        info = self.files.get(file_path)
        if not info:
            return {"error": f"File not found: {file_path}"}

        return {
            "path": file_path,
            "language": info.language,
            "lines": info.line_count,
            "importance": round(info.importance, 2),
            "concepts": info.concepts[:20],
            "depends_on": self.dependencies(file_path),
            "depended_on_by": info.imported_by[:10],
            "import_count": len(info.imports),
        }

    def summary(self) -> Dict[str, Any]:
        """Get a summary of the project."""
        return {
            "name": self.project_name,
            "type": self.project_type,
            "frameworks": self.frameworks,
            "total_files": len(self.files),
            "languages": self.languages,
            "top_files": self.hot_files(5),
        }

    def to_prompt_context(self, max_chars: int = 2000) -> str:
        """Generate a concise project summary for LLM context injection.

        This gets prepended to the system prompt so the LLM already
        understands the project before the user asks anything.
        """
        parts = [
            f"Project: {self.project_name}",
            f"Type: {self.project_type}",
        ]
        if self.frameworks:
            parts.append(f"Frameworks: {', '.join(self.frameworks)}")
        parts.append(f"Files: {len(self.files)} ({', '.join(f'{v} {k}' for k, v in sorted(self.languages.items(), key=lambda x: -x[1])[:5])})")

        # Key files
        hot = self.hot_files(8)
        if hot:
            parts.append("\nKey files:")
            for path, score in hot:
                info = self.files[path]
                concepts = ", ".join(info.concepts[:3]) if info.concepts else ""
                detail = f" ({concepts})" if concepts else ""
                parts.append(f"  {path}{detail}")

        result = "\n".join(parts)
        return result[:max_chars]
