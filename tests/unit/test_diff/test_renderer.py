"""Tests for the Diff Renderer — Rich-formatted diff display."""

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nexus.diff.engine import Changeset, DiffEngine, DiffHunk, DiffResult, DiffType
from nexus.diff.renderer import DiffRenderer


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "def hello():\n    print('hello')\n\ndef goodbye():\n    print('bye')\n"
    )
    return str(tmp_path)


@pytest.fixture
def engine(workspace):
    return DiffEngine(workspace=workspace)


@pytest.fixture
def renderer():
    return DiffRenderer(console=Console(force_terminal=True, width=120))


@pytest.fixture
def sample_diff(engine, workspace):
    return engine.diff(
        "src/main.py",
        "def hello():\n    print('hello world')\n\ndef goodbye():\n    print('see ya')\n",
    )


class TestUnifiedRendering:
    """Test unified diff rendering."""

    def test_renders_panel(self, renderer, sample_diff):
        result = renderer.render_unified(sample_diff)
        assert isinstance(result, Panel)

    def test_shows_additions_deletions(self, renderer, sample_diff):
        panel = renderer.render_unified(sample_diff)
        # Panel has a title containing the path
        assert "main.py" in str(panel.title)

    def test_empty_diff(self, renderer, engine, workspace):
        content = (engine._resolve_path("src/main.py")).read_text()
        diff = engine.diff("src/main.py", content)
        panel = renderer.render_unified(diff)
        assert isinstance(panel, Panel)


class TestSideBySideRendering:
    """Test side-by-side rendering."""

    def test_renders_panel(self, renderer, sample_diff):
        result = renderer.render_side_by_side(sample_diff)
        assert isinstance(result, Panel)

    def test_has_columns(self, renderer, sample_diff):
        panel = renderer.render_side_by_side(sample_diff)
        assert "side by side" in str(panel.title)


class TestInlineRendering:
    """Test inline word-level diff rendering."""

    def test_renders_panel(self, renderer, sample_diff):
        result = renderer.render_inline(sample_diff)
        assert isinstance(result, Panel)

    def test_inline_label(self, renderer, sample_diff):
        panel = renderer.render_inline(sample_diff)
        assert "inline" in str(panel.title)


class TestSummaryRendering:
    """Test summary rendering for diffs and changesets."""

    def test_diff_summary(self, renderer, sample_diff):
        result = renderer.render_summary(sample_diff)
        assert isinstance(result, Panel)

    def test_changeset_summary(self, renderer, engine, workspace):
        cs = engine.changeset([
            ("src/main.py", "changed main\n"),
            ("src/utils.py", "changed utils\n"),
        ], description="Multi-file change")

        result = renderer.render_summary(cs)
        assert isinstance(result, Panel)

    def test_changeset_summary_shows_description(self, renderer, engine, workspace):
        cs = engine.changeset([
            ("src/main.py", "changed\n"),
        ], description="My Changes")

        panel = renderer.render_summary(cs)
        assert "My Changes" in str(panel.title)


class TestHunkSelector:
    """Test interactive hunk selector rendering."""

    def test_renders_panel(self, renderer, sample_diff):
        result = renderer.render_hunk_selector(sample_diff)
        assert isinstance(result, Panel)

    def test_shows_hunk_status(self, renderer, sample_diff):
        sample_diff.accept_hunk(0)
        panel = renderer.render_hunk_selector(sample_diff)
        assert isinstance(panel, Panel)

    def test_selector_title(self, renderer, sample_diff):
        panel = renderer.render_hunk_selector(sample_diff)
        assert "Review" in str(panel.title)


class TestLexerDetection:
    """Test syntax lexer detection."""

    def test_python(self, renderer):
        assert renderer._detect_lexer("main.py") == "python"

    def test_javascript(self, renderer):
        assert renderer._detect_lexer("app.js") == "javascript"

    def test_typescript(self, renderer):
        assert renderer._detect_lexer("index.ts") == "typescript"

    def test_rust(self, renderer):
        assert renderer._detect_lexer("main.rs") == "rust"

    def test_unknown(self, renderer):
        assert renderer._detect_lexer("file.xyz") == "text"

    def test_json(self, renderer):
        assert renderer._detect_lexer("config.json") == "json"

    def test_yaml(self, renderer):
        assert renderer._detect_lexer("config.yaml") == "yaml"

    def test_markdown(self, renderer):
        assert renderer._detect_lexer("README.md") == "markdown"


class TestConvenienceMethods:
    """Test print convenience methods."""

    def test_print_diff_unified(self, renderer, sample_diff, capsys):
        renderer.print_diff(sample_diff, mode="unified")

    def test_print_diff_side_by_side(self, renderer, sample_diff, capsys):
        renderer.print_diff(sample_diff, mode="side_by_side")

    def test_print_diff_inline(self, renderer, sample_diff, capsys):
        renderer.print_diff(sample_diff, mode="inline")

    def test_print_diff_summary(self, renderer, sample_diff, capsys):
        renderer.print_diff(sample_diff, mode="summary")

    def test_print_changeset(self, renderer, engine, workspace):
        cs = engine.changeset([
            ("src/main.py", "changed\n"),
        ])
        renderer.print_changeset(cs, mode="summary")
