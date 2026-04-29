"""Plugin configuration system for Nexus.

Discovers and loads project-specific configuration from .nexus/ directory.
Supports stances, hooks, watchers, rules, and model preferences.

Directory structure:
    .nexus/
    ├── config.yaml          # Main project configuration
    ├── rules.md             # Project-specific instructions for the AI
    ├── stances/             # Custom stance definitions
    │   └── *.yaml
    ├── hooks/               # Custom hook definitions
    │   └── *.yaml
    └── sessions/            # Saved conversation sessions
        └── *.json
"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class StanceConfig:
    """Custom stance definition."""
    name: str
    description: str
    system_prompt: str
    temperature: float = 0.7
    triggers: List[str] = field(default_factory=list)
    priority: int = 50


@dataclass
class HookConfig:
    """Custom hook definition."""
    name: str
    event: str  # tool name: file_write, shell, etc.
    phase: str  # PRE or POST
    action: str  # block, log, transform, run
    pattern: str = ""  # regex pattern to match against
    message: str = ""  # message for block/log actions
    command: str = ""  # command for run action
    priority: int = 50
    enabled: bool = True


@dataclass
class WatcherConfig:
    """Custom watcher definition."""
    name: str
    pattern: str  # glob pattern: *.py, tests/**, etc.
    action: str  # log, notify, run
    command: str = ""  # command for run action
    debounce_ms: int = 500
    enabled: bool = True


@dataclass
class ModelConfig:
    """Model preference overrides."""
    planning: str = ""
    coding: str = ""
    fast: str = ""
    review: str = ""


@dataclass
class ProjectConfig:
    """Complete project configuration loaded from .nexus/."""
    # Project metadata
    name: str = ""
    description: str = ""
    language: str = ""
    framework: str = ""

    # Model preferences
    models: ModelConfig = field(default_factory=ModelConfig)

    # AI behavior
    rules: str = ""  # Content of rules.md
    default_stance: str = ""
    trust_level: str = "write"  # read, write, execute, destructive
    max_file_size: int = 100_000  # bytes

    # Custom definitions
    stances: List[StanceConfig] = field(default_factory=list)
    hooks: List[HookConfig] = field(default_factory=list)
    watchers: List[WatcherConfig] = field(default_factory=list)

    # Ignore patterns (files the AI should not read/modify)
    ignore: List[str] = field(default_factory=list)

    # Sessions directory
    sessions_dir: str = ".nexus/sessions"


class PluginConfigLoader:
    """Loads and manages project-specific Nexus configuration.

    Usage:
        loader = PluginConfigLoader("/path/to/project")
        config = loader.load()
        # config.rules -> str (project instructions)
        # config.stances -> List[StanceConfig]
        # config.hooks -> List[HookConfig]
        # config.models.coding -> str
    """

    def __init__(self, workspace: str):
        self.workspace = Path(workspace)
        self.nexus_dir = self.workspace / ".nexus"
        self._config: Optional[ProjectConfig] = None

    @property
    def exists(self) -> bool:
        """Check if .nexus/ directory exists."""
        return self.nexus_dir.is_dir()

    def load(self) -> ProjectConfig:
        """Load all configuration from .nexus/ directory."""
        config = ProjectConfig()

        if not self.exists:
            logger.debug(f"No .nexus/ directory found in {self.workspace}")
            self._config = config
            return config

        # Load main config.yaml
        config_file = self.nexus_dir / "config.yaml"
        if config_file.exists():
            self._load_main_config(config, config_file)

        # Load rules.md
        rules_file = self.nexus_dir / "rules.md"
        if rules_file.exists():
            config.rules = rules_file.read_text(encoding="utf-8").strip()

        # Load custom stances
        stances_dir = self.nexus_dir / "stances"
        if stances_dir.is_dir():
            config.stances = self._load_stances(stances_dir)

        # Load custom hooks (extend, don't replace inline hooks from config.yaml)
        hooks_dir = self.nexus_dir / "hooks"
        if hooks_dir.is_dir():
            config.hooks.extend(self._load_hooks(hooks_dir))

        self._config = config
        logger.info(
            f"Loaded .nexus/ config: {len(config.stances)} stances, "
            f"{len(config.hooks)} hooks, {len(config.watchers)} watchers"
        )
        return config

    def _load_main_config(self, config: ProjectConfig, path: Path) -> None:
        """Load the main config.yaml file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (yaml.YAMLError, IOError) as e:
            logger.warning(f"Failed to load {path}: {e}")
            return

        # Project metadata
        project = data.get("project", {})
        config.name = project.get("name", "")
        config.description = project.get("description", "")
        config.language = project.get("language", "")
        config.framework = project.get("framework", "")

        # Model preferences
        models = data.get("models", {})
        config.models = ModelConfig(
            planning=models.get("planning", ""),
            coding=models.get("coding", ""),
            fast=models.get("fast", ""),
            review=models.get("review", ""),
        )

        # Behavior settings
        behavior = data.get("behavior", {})
        config.default_stance = behavior.get("default_stance", "")
        config.trust_level = behavior.get("trust_level", "write")
        config.max_file_size = behavior.get("max_file_size", 100_000)

        # Ignore patterns
        config.ignore = data.get("ignore", [])

        # Inline watchers
        for w in data.get("watchers", []):
            config.watchers.append(WatcherConfig(
                name=w.get("name", "unnamed"),
                pattern=w.get("pattern", ""),
                action=w.get("action", "log"),
                command=w.get("command", ""),
                debounce_ms=w.get("debounce_ms", 500),
                enabled=w.get("enabled", True),
            ))

        # Inline hooks
        for h in data.get("hooks", []):
            config.hooks.append(HookConfig(
                name=h.get("name", "unnamed"),
                event=h.get("event", ""),
                phase=h.get("phase", "POST"),
                action=h.get("action", "log"),
                pattern=h.get("pattern", ""),
                message=h.get("message", ""),
                command=h.get("command", ""),
                priority=h.get("priority", 50),
                enabled=h.get("enabled", True),
            ))

    def _load_stances(self, stances_dir: Path) -> List[StanceConfig]:
        """Load custom stance definitions from .nexus/stances/."""
        stances = []
        for yaml_file in sorted(stances_dir.glob("*.yaml")):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not data:
                    continue
                stances.append(StanceConfig(
                    name=data.get("name", yaml_file.stem),
                    description=data.get("description", ""),
                    system_prompt=data.get("system_prompt", ""),
                    temperature=data.get("temperature", 0.7),
                    triggers=data.get("triggers", []),
                    priority=data.get("priority", 50),
                ))
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"Failed to load stance {yaml_file}: {e}")
        return stances

    def _load_hooks(self, hooks_dir: Path) -> List[HookConfig]:
        """Load custom hook definitions from .nexus/hooks/."""
        hooks = []
        for yaml_file in sorted(hooks_dir.glob("*.yaml")):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                # A single file can define multiple hooks
                hook_list = data.get("hooks", [data])
                for h in hook_list:
                    hooks.append(HookConfig(
                        name=h.get("name", yaml_file.stem),
                        event=h.get("event", ""),
                        phase=h.get("phase", "POST"),
                        action=h.get("action", "log"),
                        pattern=h.get("pattern", ""),
                        message=h.get("message", ""),
                        command=h.get("command", ""),
                        priority=h.get("priority", 50),
                        enabled=h.get("enabled", True),
                    ))
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"Failed to load hook {yaml_file}: {e}")
        return hooks

    def init(self) -> Path:
        """Initialize a .nexus/ directory with example configuration.

        Returns the path to the created directory.
        """
        self.nexus_dir.mkdir(parents=True, exist_ok=True)

        # Create config.yaml
        config_file = self.nexus_dir / "config.yaml"
        if not config_file.exists():
            config_file.write_text(_EXAMPLE_CONFIG, encoding="utf-8")

        # Create rules.md
        rules_file = self.nexus_dir / "rules.md"
        if not rules_file.exists():
            rules_file.write_text(_EXAMPLE_RULES, encoding="utf-8")

        # Create stances directory with example
        stances_dir = self.nexus_dir / "stances"
        stances_dir.mkdir(exist_ok=True)
        example_stance = stances_dir / "example.yaml"
        if not example_stance.exists():
            example_stance.write_text(_EXAMPLE_STANCE, encoding="utf-8")

        # Create hooks directory with example
        hooks_dir = self.nexus_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        example_hook = hooks_dir / "example.yaml"
        if not example_hook.exists():
            example_hook.write_text(_EXAMPLE_HOOK, encoding="utf-8")

        # Create sessions directory
        sessions_dir = self.nexus_dir / "sessions"
        sessions_dir.mkdir(exist_ok=True)

        logger.info(f"Initialized .nexus/ in {self.workspace}")
        return self.nexus_dir

    def get_config(self) -> ProjectConfig:
        """Get cached config, loading if needed."""
        if self._config is None:
            self.load()
        return self._config


# ─── Example templates ────────────────────────────────────────────────────

_EXAMPLE_CONFIG = """\
# Nexus Project Configuration
# https://github.com/11vated/Nexus

project:
  name: my-project
  description: A brief description of your project
  language: python         # python, typescript, rust, go, etc.
  framework: fastapi       # fastapi, django, react, etc.

models:
  planning: deepseek-r1:7b
  coding: qwen2.5-coder:14b
  fast: qwen2.5-coder:7b
  # review: deepseek-r1:7b  # defaults to planning model

behavior:
  default_stance: ""       # auto-detect (or: architect, debugger, reviewer, etc.)
  trust_level: write       # read, write, execute, destructive
  max_file_size: 100000    # skip files larger than this (bytes)

ignore:
  - node_modules/
  - .git/
  - __pycache__/
  - "*.pyc"
  - dist/
  - build/
  - .env

# Inline watchers (or use .nexus/hooks/*.yaml for more complex setups)
watchers:
  - name: test-watcher
    pattern: "tests/**/*.py"
    action: log
    debounce_ms: 1000
"""

_EXAMPLE_RULES = """\
# Project Rules for Nexus

These instructions are included in every conversation with Nexus about this project.

## Code Style
- Use type hints on all function signatures
- Write docstrings for public methods
- Prefer f-strings over .format()
- Maximum line length: 100 characters

## Architecture
- Follow the existing module structure
- New features go in their own module under src/
- Every module needs tests in tests/unit/

## Testing
- Write tests for all new code
- Use pytest fixtures for setup
- Aim for >80% coverage on new code

## Conventions
- Branch names: feat/*, fix/*, docs/*
- Commit messages: conventional commits (feat:, fix:, docs:, etc.)
"""

_EXAMPLE_STANCE = """\
# Custom stance definition
# Place in .nexus/stances/<name>.yaml

name: security-reviewer
description: Security-focused code review mode
system_prompt: |
  You are a security-focused code reviewer. Examine all code for:
  - Injection vulnerabilities (SQL, command, path traversal)
  - Authentication and authorization issues
  - Data exposure and privacy concerns
  - Cryptographic misuse
  - Race conditions and TOCTOU bugs
  Be thorough but practical. Suggest fixes, not just problems.
temperature: 0.3
triggers:
  - security
  - vulnerability
  - audit
  - cve
  - injection
priority: 60
"""

_EXAMPLE_HOOK = """\
# Custom hook definitions
# Place in .nexus/hooks/<name>.yaml

hooks:
  - name: block-force-push
    event: git
    phase: PRE
    action: block
    pattern: 'force|push.*-f|push.*--force'
    message: "Force push is blocked by project policy"
    priority: 10

  - name: lint-after-write
    event: file_write
    phase: POST
    action: log
    pattern: '\\.py$'
    message: "Python file modified — consider running linter"
    priority: 50
"""
