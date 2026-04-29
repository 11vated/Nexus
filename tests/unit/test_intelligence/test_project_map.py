"""Tests for the project intelligence map."""

import os
import tempfile
import pytest
from pathlib import Path

from nexus.intelligence.project_map import ProjectMap, FileInfo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_project(tmp_path):
    """Create a minimal Python project for testing."""
    # Create a FastAPI-style project
    src = tmp_path / "src" / "myapp"
    src.mkdir(parents=True)

    # __init__.py
    (src / "__init__.py").write_text('"""My app package."""\n')

    # main.py (FastAPI entry point)
    (src / "main.py").write_text('''\
"""Main application entry point."""
from fastapi import FastAPI
from myapp.routes import router

app = FastAPI()
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}
''')

    # routes.py
    (src / "routes.py").write_text('''\
"""API routes."""
from fastapi import APIRouter
from myapp.models import User

router = APIRouter()

@router.get("/users")
async def list_users():
    return []

@router.post("/users")
async def create_user(user: User):
    return user
''')

    # models.py
    (src / "models.py").write_text('''\
"""Data models."""
from pydantic import BaseModel

class User(BaseModel):
    name: str
    email: str

class Item(BaseModel):
    title: str
    price: float
''')

    # utils.py (unused — low importance)
    (src / "utils.py").write_text('''\
"""Utilities."""

def format_name(name: str) -> str:
    return name.strip().title()
''')

    # test file
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text('''\
"""Tests for main."""
import pytest
from myapp.main import app

def test_health():
    assert True
''')

    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text('''\
[project]
name = "myapp"
version = "0.1.0"
dependencies = ["fastapi", "uvicorn"]
''')

    return tmp_path


@pytest.fixture
def project_map(temp_project):
    """Create and scan a project map."""
    pmap = ProjectMap(str(temp_project))
    pmap.scan()
    return pmap


# ---------------------------------------------------------------------------
# Scanning tests
# ---------------------------------------------------------------------------

class TestScanning:
    """Tests for project scanning."""

    def test_scan_finds_files(self, project_map):
        assert len(project_map.files) > 0

    def test_scan_finds_python_files(self, project_map):
        py_files = [f for f in project_map.files if f.endswith(".py")]
        assert len(py_files) >= 5  # __init__, main, routes, models, utils, test_main

    def test_scan_detects_languages(self, project_map):
        assert "python" in project_map.languages

    def test_scan_counts_lines(self, project_map):
        main_files = [f for f in project_map.files if "main.py" in f]
        assert len(main_files) > 0
        info = project_map.files[main_files[0]]
        assert info.line_count > 0

    def test_scan_extracts_imports(self, project_map):
        route_files = [f for f in project_map.files if "routes.py" in f]
        assert len(route_files) > 0
        info = project_map.files[route_files[0]]
        assert len(info.imports) > 0

    def test_scan_extracts_concepts(self, project_map):
        model_files = [f for f in project_map.files if "models.py" in f]
        assert len(model_files) > 0
        info = project_map.files[model_files[0]]
        assert "User" in info.concepts
        assert "Item" in info.concepts

    def test_scan_skips_pycache(self, temp_project):
        # Create __pycache__ dir
        cache = temp_project / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-312.pyc").write_bytes(b"fake")

        pmap = ProjectMap(str(temp_project))
        pmap.scan()
        assert not any("__pycache__" in f for f in pmap.files)

    def test_scan_returns_self(self, temp_project):
        pmap = ProjectMap(str(temp_project))
        result = pmap.scan()
        assert result is pmap


# ---------------------------------------------------------------------------
# Project type detection
# ---------------------------------------------------------------------------

class TestProjectTypeDetection:
    """Tests for automatic project type detection."""

    def test_detects_fastapi(self, project_map):
        assert project_map.project_type == "fastapi_app"

    def test_detects_frameworks(self, project_map):
        assert "fastapi" in project_map.frameworks


# ---------------------------------------------------------------------------
# File importance scoring
# ---------------------------------------------------------------------------

class TestImportanceScoring:
    """Tests for file importance rankings."""

    def test_hot_files_returns_ranked_list(self, project_map):
        hot = project_map.hot_files(5)
        assert len(hot) > 0
        # Should be sorted by score descending
        scores = [s for _, s in hot]
        assert scores == sorted(scores, reverse=True)

    def test_main_file_has_high_importance(self, project_map):
        main_files = [f for f in project_map.files if "main.py" in f]
        if main_files:
            info = project_map.files[main_files[0]]
            assert info.importance > 0


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

class TestDependencyGraph:
    """Tests for import dependency tracking."""

    def test_dependencies_returns_list(self, project_map):
        for path in project_map.files:
            deps = project_map.dependencies(path)
            assert isinstance(deps, list)

    def test_dependents_returns_list(self, project_map):
        for path in project_map.files:
            deps = project_map.dependents(path)
            assert isinstance(deps, list)


# ---------------------------------------------------------------------------
# Concept resolution
# ---------------------------------------------------------------------------

class TestConceptResolution:
    """Tests for concept-to-file resolution."""

    def test_resolve_user_concept(self, project_map):
        results = project_map.resolve_concept("User")
        assert len(results) > 0
        # Should include models.py
        assert any("models" in r for r in results)

    def test_resolve_routes_concept(self, project_map):
        results = project_map.resolve_concept("routes")
        assert len(results) > 0

    def test_resolve_unknown_returns_empty(self, project_map):
        results = project_map.resolve_concept("xyznonexistent")
        assert results == []

    def test_resolve_returns_max_10(self, project_map):
        results = project_map.resolve_concept("a")
        assert len(results) <= 10


# ---------------------------------------------------------------------------
# File context
# ---------------------------------------------------------------------------

class TestFileContext:
    """Tests for rich file context."""

    def test_file_context_returns_dict(self, project_map):
        for path in list(project_map.files.keys())[:1]:
            ctx = project_map.file_context(path)
            assert "path" in ctx
            assert "language" in ctx
            assert "importance" in ctx

    def test_file_context_unknown_returns_error(self, project_map):
        ctx = project_map.file_context("nonexistent.py")
        assert "error" in ctx


# ---------------------------------------------------------------------------
# Summary & prompt context
# ---------------------------------------------------------------------------

class TestSummary:
    """Tests for project summary and prompt context."""

    def test_summary_has_required_fields(self, project_map):
        summary = project_map.summary()
        assert "name" in summary
        assert "type" in summary
        assert "total_files" in summary
        assert "languages" in summary

    def test_to_prompt_context_fits_budget(self, project_map):
        ctx = project_map.to_prompt_context(max_chars=500)
        assert len(ctx) <= 500

    def test_to_prompt_context_includes_project_info(self, project_map):
        ctx = project_map.to_prompt_context()
        assert "Project:" in ctx
        assert "Type:" in ctx


# ---------------------------------------------------------------------------
# Empty project
# ---------------------------------------------------------------------------

class TestEmptyProject:
    """Tests for scanning an empty directory."""

    def test_empty_dir_scans_without_error(self, tmp_path):
        pmap = ProjectMap(str(tmp_path))
        pmap.scan()
        assert len(pmap.files) == 0
        assert pmap.project_type == "unknown"

    def test_empty_project_summary(self, tmp_path):
        pmap = ProjectMap(str(tmp_path))
        pmap.scan()
        summary = pmap.summary()
        assert summary["total_files"] == 0
