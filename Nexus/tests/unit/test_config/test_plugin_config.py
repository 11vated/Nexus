"""Tests for the .nexus/ plugin configuration system."""
import os
import pytest
from pathlib import Path

from nexus.config.plugin_config import (
    PluginConfigLoader,
    ProjectConfig,
    StanceConfig,
    HookConfig,
    WatcherConfig,
    ModelConfig,
)


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace."""
    return tmp_path


@pytest.fixture
def nexus_dir(workspace):
    """Create a .nexus/ directory in the workspace."""
    d = workspace / ".nexus"
    d.mkdir()
    return d


@pytest.fixture
def loader(workspace):
    """Create a PluginConfigLoader."""
    return PluginConfigLoader(str(workspace))


# ─── Existence and Defaults ────────────────────────────────────────────

class TestLoaderBasics:
    def test_no_nexus_dir(self, loader, workspace):
        """No .nexus/ → returns empty defaults."""
        assert not loader.exists
        config = loader.load()
        assert config.name == ""
        assert config.rules == ""
        assert config.stances == []
        assert config.hooks == []
        assert config.watchers == []

    def test_exists_with_nexus_dir(self, loader, nexus_dir):
        """Detects existing .nexus/ directory."""
        assert loader.exists

    def test_empty_nexus_dir(self, loader, nexus_dir):
        """Empty .nexus/ loads fine with defaults."""
        config = loader.load()
        assert isinstance(config, ProjectConfig)
        assert config.name == ""

    def test_get_config_caches(self, loader, nexus_dir):
        """get_config() loads once and caches."""
        c1 = loader.get_config()
        c2 = loader.get_config()
        assert c1 is c2

    def test_load_resets_cache(self, loader, nexus_dir):
        """load() always re-reads from disk."""
        c1 = loader.get_config()
        c2 = loader.load()
        # Both should be valid configs but different instances
        assert isinstance(c1, ProjectConfig)
        assert isinstance(c2, ProjectConfig)


# ─── config.yaml Loading ──────────────────────────────────────────────

class TestMainConfig:
    def test_project_metadata(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("""
project:
  name: test-project
  description: A test project
  language: python
  framework: fastapi
""")
        config = loader.load()
        assert config.name == "test-project"
        assert config.description == "A test project"
        assert config.language == "python"
        assert config.framework == "fastapi"

    def test_model_preferences(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("""
models:
  planning: llama3:70b
  coding: codellama:34b
  fast: phi3:mini
  review: deepseek-r1:14b
""")
        config = loader.load()
        assert config.models.planning == "llama3:70b"
        assert config.models.coding == "codellama:34b"
        assert config.models.fast == "phi3:mini"
        assert config.models.review == "deepseek-r1:14b"

    def test_behavior_settings(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("""
behavior:
  default_stance: architect
  trust_level: execute
  max_file_size: 50000
""")
        config = loader.load()
        assert config.default_stance == "architect"
        assert config.trust_level == "execute"
        assert config.max_file_size == 50000

    def test_ignore_patterns(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("""
ignore:
  - node_modules/
  - "*.pyc"
  - .git/
""")
        config = loader.load()
        assert "node_modules/" in config.ignore
        assert "*.pyc" in config.ignore
        assert len(config.ignore) == 3

    def test_inline_watchers(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("""
watchers:
  - name: py-watcher
    pattern: "**/*.py"
    action: run
    command: "pytest tests/ -x"
    debounce_ms: 2000
  - name: css-watcher
    pattern: "*.css"
    action: log
""")
        config = loader.load()
        assert len(config.watchers) == 2
        assert config.watchers[0].name == "py-watcher"
        assert config.watchers[0].action == "run"
        assert config.watchers[0].command == "pytest tests/ -x"
        assert config.watchers[0].debounce_ms == 2000
        assert config.watchers[1].name == "css-watcher"
        assert config.watchers[1].action == "log"

    def test_inline_hooks(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("""
hooks:
  - name: block-rm
    event: shell
    phase: PRE
    action: block
    pattern: "rm -rf"
    message: "Destructive command blocked"
""")
        config = loader.load()
        assert len(config.hooks) == 1
        assert config.hooks[0].name == "block-rm"
        assert config.hooks[0].event == "shell"
        assert config.hooks[0].phase == "PRE"
        assert config.hooks[0].action == "block"

    def test_invalid_yaml(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text(": invalid: [yaml: {broken")
        config = loader.load()
        # Should not crash — returns defaults
        assert config.name == ""

    def test_empty_config_yaml(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("")
        config = loader.load()
        assert config.name == ""

    def test_missing_sections(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("project:\n  name: minimal\n")
        config = loader.load()
        assert config.name == "minimal"
        assert config.models.planning == ""
        assert config.ignore == []


# ─── rules.md ─────────────────────────────────────────────────────────

class TestRules:
    def test_load_rules(self, loader, nexus_dir):
        (nexus_dir / "rules.md").write_text("# My Rules\nAlways use type hints.\n")
        config = loader.load()
        assert "Always use type hints" in config.rules
        assert config.rules.startswith("# My Rules")

    def test_rules_stripped(self, loader, nexus_dir):
        (nexus_dir / "rules.md").write_text("\n\n  Hello  \n\n")
        config = loader.load()
        assert config.rules == "Hello"


# ─── Stances Directory ────────────────────────────────────────────────

class TestStances:
    def test_load_stances(self, loader, nexus_dir):
        stances_dir = nexus_dir / "stances"
        stances_dir.mkdir()
        (stances_dir / "reviewer.yaml").write_text("""
name: code-reviewer
description: Thorough code review
system_prompt: Review code carefully.
temperature: 0.3
triggers:
  - review
  - check
priority: 70
""")
        config = loader.load()
        assert len(config.stances) == 1
        s = config.stances[0]
        assert s.name == "code-reviewer"
        assert s.temperature == 0.3
        assert "review" in s.triggers
        assert s.priority == 70

    def test_multiple_stances(self, loader, nexus_dir):
        stances_dir = nexus_dir / "stances"
        stances_dir.mkdir()
        (stances_dir / "a_architect.yaml").write_text(
            "name: architect\ndescription: Design mode\nsystem_prompt: Think big."
        )
        (stances_dir / "b_debugger.yaml").write_text(
            "name: debugger\ndescription: Debug mode\nsystem_prompt: Find bugs."
        )
        config = loader.load()
        assert len(config.stances) == 2
        # Sorted alphabetically by filename
        assert config.stances[0].name == "architect"
        assert config.stances[1].name == "debugger"

    def test_invalid_stance_yaml(self, loader, nexus_dir):
        stances_dir = nexus_dir / "stances"
        stances_dir.mkdir()
        (stances_dir / "broken.yaml").write_text(": bad: [")
        (stances_dir / "good.yaml").write_text("name: good\ndescription: ok\nsystem_prompt: hi")
        config = loader.load()
        assert len(config.stances) == 1
        assert config.stances[0].name == "good"

    def test_stance_defaults(self, loader, nexus_dir):
        stances_dir = nexus_dir / "stances"
        stances_dir.mkdir()
        (stances_dir / "minimal.yaml").write_text(
            "name: minimal\ndescription: bare\nsystem_prompt: go"
        )
        config = loader.load()
        s = config.stances[0]
        assert s.temperature == 0.7
        assert s.triggers == []
        assert s.priority == 50

    def test_stance_name_fallback(self, loader, nexus_dir):
        stances_dir = nexus_dir / "stances"
        stances_dir.mkdir()
        (stances_dir / "my_stance.yaml").write_text(
            "description: no name field\nsystem_prompt: test"
        )
        config = loader.load()
        assert config.stances[0].name == "my_stance"


# ─── Hooks Directory ──────────────────────────────────────────────────

class TestHooks:
    def test_load_single_hook(self, loader, nexus_dir):
        hooks_dir = nexus_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "lint.yaml").write_text(
            "name: auto-lint\n"
            "event: file_write\n"
            "phase: POST\n"
            "action: run\n"
            "pattern: '\\.py$'\n"
            "command: 'ruff check --fix .'\n"
            "priority: 30\n"
        )
        config = loader.load()
        assert len(config.hooks) == 1
        h = config.hooks[0]
        assert h.name == "auto-lint"
        assert h.event == "file_write"
        assert h.phase == "POST"
        assert h.action == "run"

    def test_load_multi_hook_file(self, loader, nexus_dir):
        hooks_dir = nexus_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "security.yaml").write_text(
            "hooks:\n"
            "  - name: block-eval\n"
            "    event: file_write\n"
            "    phase: PRE\n"
            "    action: block\n"
            "    pattern: 'eval\\('\n"
            "    message: eval() is not allowed\n"
            "  - name: log-secrets\n"
            "    event: file_write\n"
            "    phase: POST\n"
            "    action: log\n"
            "    pattern: '(API_KEY|SECRET)'\n"
            "    message: Possible secret detected\n"
        )
        config = loader.load()
        assert len(config.hooks) == 2
        assert config.hooks[0].name == "block-eval"
        assert config.hooks[1].name == "log-secrets"

    def test_combined_inline_and_file_hooks(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("""
hooks:
  - name: inline-hook
    event: shell
    phase: PRE
    action: log
""")
        hooks_dir = nexus_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "file.yaml").write_text("""
name: file-hook
event: git
phase: POST
action: log
""")
        config = loader.load()
        assert len(config.hooks) == 2
        names = {h.name for h in config.hooks}
        assert "inline-hook" in names
        assert "file-hook" in names

    def test_hook_defaults(self, loader, nexus_dir):
        hooks_dir = nexus_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "minimal.yaml").write_text("name: min\nevent: shell\nphase: POST\naction: log")
        config = loader.load()
        h = config.hooks[0]
        assert h.pattern == ""
        assert h.message == ""
        assert h.command == ""
        assert h.priority == 50
        assert h.enabled is True

    def test_disabled_hook(self, loader, nexus_dir):
        hooks_dir = nexus_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "off.yaml").write_text(
            "name: disabled\nevent: shell\nphase: PRE\naction: block\nenabled: false"
        )
        config = loader.load()
        assert config.hooks[0].enabled is False


# ─── Init Scaffolding ─────────────────────────────────────────────────

class TestInit:
    def test_init_creates_structure(self, loader, workspace):
        path = loader.init()
        assert path == workspace / ".nexus"
        assert (path / "config.yaml").exists()
        assert (path / "rules.md").exists()
        assert (path / "stances").is_dir()
        assert (path / "stances" / "example.yaml").exists()
        assert (path / "hooks").is_dir()
        assert (path / "hooks" / "example.yaml").exists()
        assert (path / "sessions").is_dir()

    def test_init_does_not_overwrite(self, loader, nexus_dir):
        (nexus_dir / "config.yaml").write_text("project:\n  name: custom\n")
        loader.init()
        content = (nexus_dir / "config.yaml").read_text()
        assert "custom" in content

    def test_init_then_load(self, loader, workspace):
        loader.init()
        config = loader.load()
        # Example config has project name "my-project"
        assert config.name == "my-project"
        assert len(config.stances) == 1  # example.yaml
        assert len(config.hooks) == 2  # example has 2 hooks

    def test_init_idempotent(self, loader, workspace):
        loader.init()
        loader.init()  # Should not crash or duplicate
        assert (workspace / ".nexus" / "config.yaml").exists()


# ─── Edge Cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_non_yaml_files_ignored(self, loader, nexus_dir):
        stances_dir = nexus_dir / "stances"
        stances_dir.mkdir()
        (stances_dir / "readme.txt").write_text("not a stance")
        (stances_dir / "valid.yaml").write_text(
            "name: valid\ndescription: ok\nsystem_prompt: go"
        )
        config = loader.load()
        assert len(config.stances) == 1

    def test_empty_yaml_files(self, loader, nexus_dir):
        stances_dir = nexus_dir / "stances"
        stances_dir.mkdir()
        (stances_dir / "empty.yaml").write_text("")
        config = loader.load()
        # Empty YAML -> safe_load returns None -> should handle gracefully
        assert len(config.stances) == 0

    def test_unicode_content(self, loader, nexus_dir):
        (nexus_dir / "rules.md").write_text("# 规则\n使用类型提示。\n🚀 Launch!", encoding="utf-8")
        config = loader.load()
        assert "规则" in config.rules
        assert "🚀" in config.rules

    def test_workspace_path_as_string(self, workspace):
        loader = PluginConfigLoader(str(workspace))
        assert loader.workspace == Path(workspace)
