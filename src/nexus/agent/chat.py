"""Collaborative chat session — conversational coding partner.

Unlike the autonomous AgentLoop (Plan → Act → Observe → Reflect),
ChatSession maintains a persistent dialogue where the user and Nexus
collaborate interactively.  The LLM can call tools, but only when it
makes sense in the conversation — never firing off an autonomous
multi-step pipeline unless the user explicitly asks.

What makes THIS different from any other chat wrapper:

1. **Multi-Model Routing** — each message is analyzed and routed to
   the best local model (reasoning, coding, or fast) automatically.
   The user sees one conversation; Nexus picks the specialist.

2. **Adaptive Stances** — Nexus shifts behavior based on context:
   architect mode for design, debugger mode for bugs, reviewer mode
   for code review. Each stance has different prompts, temperatures,
   and tool preferences.

3. **Project Intelligence** — before you ask, Nexus scans your project
   and understands its structure, dependencies, and architecture.
   When you say "the API", it knows which files you mean.

4. **Session Persistence** — save and resume conversations with full
   context. Your sessions are local JSON files, not cloud data.

5. **Live Diff Preview** — every file modification generates a diff
   that's shown before (or alongside) the change. Accept, reject,
   or undo at the hunk level.

6. **Conversation Branching** — fork conversations like git branches
   to explore multiple approaches. Compare, switch, merge back.

7. **Safety & Permissions** — granular control over what tools can do.
   Dangerous ops need confirmation. Full audit trail of every action.

8. **Hooks & Watchers** — extensible pre/post hooks around tool calls.
   File watchers that react to project changes automatically.

Usage:
    session = ChatSession(workspace="/path/to/project")
    session.load_project_rules()   # reads .nexus/rules.md
    async for event in session.send("Add a health endpoint to the API"):
        ...  # ChatEvent(type="token"|"tool_call"|"tool_result"|"plan"|"done")
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from nexus.agent.llm import OllamaClient, extract_json
from nexus.agent.models import AgentConfig
from nexus.tools import create_default_tools
from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Events emitted by ChatSession
# ---------------------------------------------------------------------------

class EventType(Enum):
    """Types of events produced during a chat turn."""
    TOKEN = "token"                  # Streaming text token
    TOOL_CALL = "tool_call"          # LLM wants to call a tool
    TOOL_RESULT = "tool_result"      # Result from tool execution
    PLAN = "plan"                    # LLM proposed a multi-step plan
    THINKING = "thinking"            # LLM reasoning / scratchpad
    ROUTING = "routing"              # Model routing decision
    STANCE_CHANGE = "stance"         # Stance change notification
    DIFF_PREVIEW = "diff_preview"    # Diff generated for file write
    PERMISSION = "permission"        # Permission check result
    HOOK = "hook"                    # Hook fired (pre/post)
    BRANCH = "branch"                # Branch operation
    COGNITIVE = "cognitive"          # Cognitive layer event
    AMBIGUITY = "ambiguity"          # Ambiguity detected in user message
    VERIFICATION = "verification"    # Design verification result
    KNOWLEDGE = "knowledge"          # Knowledge retrieval/update
    MEMORY = "memory"                # Memory recall
    ERROR = "error"                  # Something went wrong
    DONE = "done"                    # Turn complete


@dataclass
class ChatEvent:
    """A single event from a chat turn."""
    type: EventType
    content: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# System prompt — collaborative, not autonomous
# ---------------------------------------------------------------------------

CHAT_SYSTEM_PROMPT = """\
You are Nexus, a collaborative AI coding partner running locally via Ollama.

You work *with* the user, not autonomously. Your job is to:
1. Understand what they want to build
2. Ask clarifying questions when the goal is ambiguous
3. Propose a plan and wait for approval before executing
4. Show what you're doing and explain your reasoning
5. Write high-quality, tested code

When you need to perform an action, respond with a tool call in this format:
```tool
{{"tool": "tool_name", "args": {{"arg1": "value1"}}}}
```

Available tools:
{tool_descriptions}

Behavioral rules:
- Never execute destructive actions (delete files, force push) without asking first
- When the user asks you to build something, first outline a plan in numbered steps
- After showing the plan, ask "Shall I proceed?" before executing
- If a tool call fails, explain what went wrong and suggest alternatives
- Use code blocks with language tags for all code snippets
- Be concise but thorough — no filler text
- When writing files, show the key parts and explain your choices

{stance_prompt}

{project_context}

{project_rules}

{branch_context}

Current workspace: {workspace}
"""


# ---------------------------------------------------------------------------
# ChatSession
# ---------------------------------------------------------------------------

class ChatSession:
    """A persistent, conversational coding session.

    Maintains full conversation history, handles tool dispatch inline,
    and streams responses token-by-token for live display.

    Intelligence features (auto-enabled):
    - ModelRouter:  routes each message to the best local model
    - StanceManager: adapts behavior (architect, debugger, reviewer, etc.)
    - ProjectMap:   deep project understanding for auto-context
    - SessionStore: save/resume sessions

    Interactive features (auto-enabled):
    - DiffEngine:        live diff preview for file writes
    - ConversationTree:  git-like conversation branching
    - PermissionManager: safety gates around tool execution
    - HookEngine:        extensible pre/post tool hooks
    - WatcherEngine:     background file monitoring
    """

    def __init__(
        self,
        workspace: str = ".",
        config: Optional[AgentConfig] = None,
        model: Optional[str] = None,
    ):
        self.workspace = str(Path(workspace).resolve())
        self.config = config or AgentConfig(workspace_path=self.workspace)
        self.model = model or self.config.coding_model
        self.llm = OllamaClient(self.config)
        self.history: List[Dict[str, str]] = []
        self.project_rules: str = ""
        self._tools: Dict[str, BaseTool] = {}
        self._tool_call_count = 0
        self._session_start = time.time()

        # Intelligence layer — what makes Nexus unique
        self._router = None           # ModelRouter
        self._stances = None          # StanceManager
        self._project_map = None      # ProjectMap
        self._session_store = None    # SessionStore
        self._intelligence_enabled = True
        self._session_id: Optional[str] = None

        # Interactive layer — collaborative power tools
        self._diff_engine = None      # DiffEngine
        self._diff_renderer = None    # DiffRenderer
        self._branch_tree = None      # ConversationTree
        self._permissions = None      # PermissionManager
        self._hooks = None            # HookEngine
        self._watcher = None          # WatcherEngine
        self._interactive_enabled = True

        # Cognitive layer — deep intelligence & partnership
        self._cognitive = None        # CognitiveLayer
        self._cognitive_enabled = True

        # Diff preview config
        self._diff_auto_apply = True  # Apply diffs automatically (show diff for info)
        self._diff_mode = "unified"   # Default render mode

        self._setup_tools()
        self._setup_intelligence()
        self._setup_interactive()
        self._setup_cognitive()

    # -- setup ---------------------------------------------------------------

    def _setup_tools(self) -> None:
        """Initialize the default tool set."""
        raw_tools = create_default_tools(self.workspace)
        for name, tool in raw_tools.items():
            self._tools[name] = tool

    def _setup_intelligence(self) -> None:
        """Initialize the intelligence layer.

        These are Nexus's unique differentiators — not just chat,
        but intelligent, adaptive, project-aware conversation.
        """
        try:
            from nexus.intelligence.model_router import ModelRouter
            from nexus.intelligence.stances import StanceManager
            from nexus.intelligence.project_map import ProjectMap
            from nexus.intelligence.session_store import SessionStore

            self._router = ModelRouter(self.config)
            self._stances = StanceManager()
            self._project_map = ProjectMap(self.workspace)
            self._session_store = SessionStore(self.workspace)

            # Scan the project for auto-context
            try:
                self._project_map.scan()
                logger.info(
                    "ProjectMap: %s (%d files, type=%s)",
                    self._project_map.project_name,
                    len(self._project_map.files),
                    self._project_map.project_type,
                )
            except Exception as exc:
                logger.warning("ProjectMap scan failed: %s", exc)

        except ImportError as exc:
            logger.warning("Intelligence layer not available: %s", exc)
            self._intelligence_enabled = False

    def _setup_interactive(self) -> None:
        """Initialize the interactive layer.

        Diff preview, conversation branching, safety permissions,
        hooks, and file watchers — the collaborative power tools.
        """
        try:
            from nexus.diff.engine import DiffEngine
            from nexus.diff.renderer import DiffRenderer
            from nexus.intelligence.branching import ConversationTree
            from nexus.safety.permissions import PermissionManager, PermissionLevel
            from nexus.hooks.engine import HookEngine, WatcherEngine

            self._diff_engine = DiffEngine(self.workspace)
            self._diff_renderer = DiffRenderer()
            self._branch_tree = ConversationTree(self.workspace)
            self._permissions = PermissionManager(
                workspace=self.workspace,
                trust_level=PermissionLevel.WRITE,
            )
            self._hooks = HookEngine()
            self._watcher = WatcherEngine(self.workspace)

            logger.info("Interactive layer initialized (diff, branching, safety, hooks, watchers)")
        except ImportError as exc:
            logger.warning("Interactive layer not available: %s", exc)
            self._interactive_enabled = False

    def _setup_cognitive(self) -> None:
        """Initialize the cognitive layer.

        Meta-cognitive reasoning, knowledge architecture, design verification,
        ambiguity detection, multi-memory mesh — the thinking partner brain.
        """
        try:
            from nexus.cognitive.integration import CognitiveLayer

            self._cognitive = CognitiveLayer(workspace=self.workspace)
            logger.info("Cognitive layer initialized (loop, trace, knowledge, memory, verification)")
        except ImportError as exc:
            logger.warning("Cognitive layer not available: %s", exc)
            self._cognitive_enabled = False

    def _get_tool_descriptions(self) -> str:
        """Format tool descriptions for the system prompt."""
        lines = []
        for name, tool in self._tools.items():
            lines.append(tool.to_prompt_description())
        return "\n".join(lines)

    def load_project_rules(self) -> str:
        """Load .nexus/rules.md from the workspace if it exists."""
        rules_path = Path(self.workspace) / ".nexus" / "rules.md"
        if rules_path.exists():
            self.project_rules = rules_path.read_text(encoding="utf-8").strip()
            logger.info("Loaded project rules from %s", rules_path)
        else:
            self.project_rules = ""
        return self.project_rules

    def _build_system_prompt(self) -> str:
        """Build the system prompt with intelligence + interactive context."""
        # Stance prompt addon
        stance_prompt = ""
        if self._stances:
            modifier = self._stances.get_prompt_modifier()
            if modifier:
                stance_prompt = modifier

        # Project context from ProjectMap
        project_context = ""
        if self._project_map and self._project_map._scanned:
            project_context = (
                f"Project intelligence (auto-detected):\n"
                f"{self._project_map.to_prompt_context()}\n"
            )

        # Project rules from .nexus/rules.md
        rules_section = ""
        if self.project_rules:
            rules_section = (
                f"Project-specific rules (.nexus/rules.md):\n"
                f"{self.project_rules}\n"
            )

        # Branch context
        branch_context = ""
        if self._branch_tree and self._branch_tree.branch_count > 1:
            branch_context = (
                f"Conversation branch: {self._branch_tree.current_branch} "
                f"({self._branch_tree.branch_count} total branches)"
            )

        # Cognitive context (reasoning trace, knowledge, memory)
        cognitive_context = ""
        if self._cognitive:
            # Use last user message for context augmentation
            last_user_msg = ""
            for msg in reversed(self.history):
                if msg["role"] == "user":
                    last_user_msg = msg["content"]
                    break
            cognitive_context = self._cognitive.get_context_augmentation(last_user_msg)

        prompt = CHAT_SYSTEM_PROMPT.format(
            tool_descriptions=self._get_tool_descriptions(),
            stance_prompt=stance_prompt,
            project_context=project_context,
            project_rules=rules_section,
            branch_context=branch_context,
            workspace=self.workspace,
        )

        if cognitive_context:
            prompt += f"\n{cognitive_context}"

        return prompt

    # -- intelligence controls -----------------------------------------------

    def set_stance(self, stance_name: str) -> Optional[str]:
        """Manually set conversation stance.

        Returns the stance display name, or None if not found.
        """
        if not self._stances:
            return None

        from nexus.intelligence.stances import Stance
        try:
            stance = Stance(stance_name.lower().strip())
        except ValueError:
            return None

        config = self._stances.set_stance(stance)
        return f"{config.emoji} {config.display_name}"

    def list_stances(self) -> List[Dict[str, str]]:
        """List available stances."""
        if self._stances:
            return self._stances.list_stances()
        return []

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get model routing statistics."""
        if self._router:
            return self._router.stats()
        return {}

    def get_project_summary(self) -> Dict[str, Any]:
        """Get project intelligence summary."""
        if self._project_map and self._project_map._scanned:
            return self._project_map.summary()
        return {}

    # -- session persistence -------------------------------------------------

    def save_session(self, title: Optional[str] = None) -> Optional[str]:
        """Save the current session. Returns session ID."""
        if not self._session_store:
            return None

        metadata = {
            "model": self.model,
            "tool_calls": self._tool_call_count,
            "duration": round(time.time() - self._session_start, 1),
        }
        if self._stances:
            metadata["stance"] = self._stances.current.value
        if self._router:
            metadata["routing_stats"] = self._router.stats()
        if self._branch_tree:
            metadata["branch"] = self._branch_tree.current_branch
            metadata["branch_count"] = self._branch_tree.branch_count

        project_ctx = {}
        if self._project_map and self._project_map._scanned:
            project_ctx = self._project_map.summary()

        self._session_id = self._session_store.save(
            messages=self.history,
            metadata=metadata,
            project_context=project_ctx,
            title=title,
            session_id=self._session_id,
        )

        # Also save the branch tree
        if self._branch_tree:
            try:
                self._branch_tree.save()
            except Exception as exc:
                logger.warning("Failed to save branch tree: %s", exc)

        # Save audit log
        if self._permissions:
            try:
                self._permissions.save_audit()
            except Exception as exc:
                logger.warning("Failed to save audit log: %s", exc)

        return self._session_id

    def load_session(self, session_id: str) -> bool:
        """Load a saved session. Returns True if successful."""
        if not self._session_store:
            return False

        snapshot = self._session_store.load(session_id)
        if not snapshot:
            return False

        self.history = snapshot.messages
        self._session_id = snapshot.session_id

        # Restore stance if saved
        if snapshot.metadata.get("stance") and self._stances:
            from nexus.intelligence.stances import Stance
            try:
                self._stances.set_stance(Stance(snapshot.metadata["stance"]))
            except ValueError:
                pass

        # Restore model if saved
        if snapshot.metadata.get("model"):
            self.model = snapshot.metadata["model"]

        # Load branch tree
        if self._branch_tree:
            self._branch_tree.load()

        logger.info(
            "Loaded session %s (%d messages)",
            session_id, len(self.history),
        )
        return True

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List saved sessions."""
        if not self._session_store:
            return []

        return [
            {
                "id": s.session_id,
                "title": s.title,
                "messages": s.message_count,
                "when": s.duration_display,
                "tags": s.tags,
            }
            for s in self._session_store.list_sessions()
        ]

    # -- conversation management ---------------------------------------------

    def clear_history(self) -> None:
        """Clear conversation history (start fresh)."""
        self.history.clear()

    def get_history(self) -> List[Dict[str, str]]:
        """Get the current conversation history."""
        return list(self.history)

    @property
    def turn_count(self) -> int:
        """Number of user turns so far."""
        return sum(1 for m in self.history if m["role"] == "user")

    # -- model routing -------------------------------------------------------

    def _route_message(self, message: str) -> Optional[str]:
        """Route a message to the best model.

        Returns the model name to use, or None to keep current.
        Also updates stance automatically.
        """
        if not self._router or not self._intelligence_enabled:
            return None

        decision = self._router.route(message)

        # Also update stance from the detected intent
        if self._stances:
            self._stances.detect_from_intent(decision.intent)

        return decision.model

    # ========================================================================
    # Conversation Branching — git for conversations
    # ========================================================================

    def create_branch(self, name: str, description: str = "", switch: bool = True) -> str:
        """Create a new conversation branch from the current point.

        Args:
            name: Branch name.
            description: Optional description.
            switch: Whether to switch to the new branch (default True).

        Returns a description string of what happened.
        """
        if not self._branch_tree:
            return "Branching not available."

        try:
            branch = self._branch_tree.create_branch(name, description=description, switch=switch)
            return (
                f"Created branch '{name}' from '{branch.parent_branch}' "
                f"at message {branch.fork_point}"
            )
        except ValueError as exc:
            return f"Error: {exc}"

    def switch_branch(self, name: str) -> str:
        """Switch to a different conversation branch.

        Returns a description of the switch.
        """
        if not self._branch_tree:
            return "Branching not available."

        try:
            branch = self._branch_tree.switch_branch(name)
            # Update history to match the branch
            messages = self._branch_tree.get_history_dicts(name)
            self.history = messages
            return (
                f"Switched to branch '{name}' "
                f"({len(messages)} messages)"
            )
        except ValueError as exc:
            return f"Error: {exc}"

    def delete_branch(self, name: str) -> str:
        """Delete a conversation branch."""
        if not self._branch_tree:
            return "Branching not available."

        try:
            self._branch_tree.delete_branch(name)
            return f"Deleted branch '{name}'"
        except ValueError as exc:
            return f"Error: {exc}"

    def list_branches(self) -> List[Dict[str, Any]]:
        """List all conversation branches."""
        if not self._branch_tree:
            return []
        return self._branch_tree.list_branches()

    def compare_branches(self, branch_a: str, branch_b: str) -> Dict[str, Any]:
        """Compare two conversation branches."""
        if not self._branch_tree:
            return {"error": "Branching not available"}

        try:
            comp = self._branch_tree.compare(branch_a, branch_b)
            return {
                "branch_a": comp.branch_a,
                "branch_b": comp.branch_b,
                "fork_point": comp.fork_point,
                "shared_messages": comp.shared_messages,
                "unique_a": comp.unique_a,
                "unique_b": comp.unique_b,
                "a_summary": comp.a_summary,
                "b_summary": comp.b_summary,
                "a_tool_calls": comp.a_tool_calls,
                "b_tool_calls": comp.b_tool_calls,
            }
        except ValueError as exc:
            return {"error": str(exc)}

    def merge_branch(self, source: str, strategy: str = "append") -> Dict[str, Any]:
        """Merge a branch into the current branch."""
        if not self._branch_tree:
            return {"error": "Branching not available"}

        try:
            count = self._branch_tree.merge(source, strategy=strategy)
            # Refresh history from the merged branch
            messages = self._branch_tree.get_history_dicts()
            self.history = messages
            return {
                "merged": count,
                "source": source,
                "target": self._branch_tree.current_branch,
                "strategy": strategy,
            }
        except ValueError as exc:
            return {"error": str(exc)}

    def get_branch_tree(self) -> str:
        """Get a visual tree of all branches."""
        if not self._branch_tree:
            return "Branching not available."
        return self._branch_tree.tree_display()

    @property
    def current_branch(self) -> str:
        """Name of the current conversation branch."""
        if self._branch_tree:
            return self._branch_tree.current_branch
        return "main"

    # ========================================================================
    # Diff Engine — live diff preview
    # ========================================================================

    def get_pending_diffs(self) -> List[Any]:
        """Get all pending (unapplied) diffs."""
        if not self._diff_engine:
            return []
        return self._diff_engine.pending_diffs

    def accept_diff(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Accept and apply a pending diff (or all pending diffs).

        Args:
            path: Specific file path, or None to accept all.

        Returns:
            Application result dict.
        """
        if not self._diff_engine:
            return {"error": "Diff engine not available"}

        pending = self._diff_engine.pending_diffs
        if not pending:
            return {"message": "No pending diffs"}

        if path:
            target = next((d for d in pending if d.path == path), None)
            if not target:
                return {"error": f"No pending diff for '{path}'"}
            target.accept_all()
            return self._diff_engine.apply(target)
        else:
            # Accept all
            results: Dict[str, Any] = {"applied": [], "skipped": [], "errors": []}
            for diff in list(pending):
                diff.accept_all()
                sub = self._diff_engine.apply(diff)
                results["applied"].extend(sub.get("applied", []))
                results["skipped"].extend(sub.get("skipped", []))
                results["errors"].extend(sub.get("errors", []))
            return results

    def reject_diff(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Reject a pending diff (or all pending diffs).

        Args:
            path: Specific file path, or None to reject all.

        Returns:
            Summary of rejected diffs.
        """
        if not self._diff_engine:
            return {"error": "Diff engine not available"}

        pending = self._diff_engine.pending_diffs
        if not pending:
            return {"message": "No pending diffs"}

        rejected = []
        if path:
            target = next((d for d in pending if d.path == path), None)
            if not target:
                return {"error": f"No pending diff for '{path}'"}
            self._diff_engine.reject(target)
            rejected.append(target.path)
        else:
            for diff in list(pending):
                self._diff_engine.reject(diff)
                rejected.append(diff.path)

        return {"rejected": rejected, "count": len(rejected)}

    def undo_last_change(self) -> Dict[str, Any]:
        """Undo the most recently applied file change."""
        if not self._diff_engine:
            return {"error": "Diff engine not available"}

        result = self._diff_engine.undo_last()
        if result is None:
            return {"message": "Nothing to undo"}
        return result

    def get_diff_stats(self) -> Dict[str, Any]:
        """Get diff engine statistics."""
        if not self._diff_engine:
            return {}
        return {
            "pending": self._diff_engine.pending_count,
            "history": self._diff_engine.history_count,
            "auto_apply": self._diff_auto_apply,
            "mode": self._diff_mode,
        }

    # ========================================================================
    # Safety & Permissions
    # ========================================================================

    def get_audit_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the tool execution audit log."""
        if not self._permissions:
            return []
        return [e.to_dict() for e in self._permissions.audit_log(limit=limit)]

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get a summary of the audit log."""
        if not self._permissions:
            return {}
        return self._permissions.audit_summary()

    def set_trust_level(self, level_name: str) -> str:
        """Set the trust level for auto-approving tool calls.

        Args:
            level_name: One of "read", "write", "execute", "destructive"

        Returns:
            Confirmation string.
        """
        if not self._permissions:
            return "Permission manager not available."

        from nexus.safety.permissions import PermissionLevel

        level_map = {
            "read": PermissionLevel.READ,
            "write": PermissionLevel.WRITE,
            "execute": PermissionLevel.EXECUTE,
            "destructive": PermissionLevel.DESTRUCTIVE,
        }

        level = level_map.get(level_name.lower().strip())
        if not level:
            return f"Unknown level '{level_name}'. Use: read, write, execute, destructive"

        self._permissions.set_trust_level(level)
        return f"Trust level set to {level.name}"

    def get_trust_level(self) -> str:
        """Get the current trust level."""
        if not self._permissions:
            return "unknown"
        return self._permissions.trust_level.name

    # ========================================================================
    # Hooks & Watchers
    # ========================================================================

    def get_hooks(self) -> List[Dict[str, Any]]:
        """List all registered hooks."""
        if not self._hooks:
            return []
        return self._hooks.list_hooks()

    def get_hook_history(self) -> List[Dict[str, Any]]:
        """Get recent hook execution history."""
        if not self._hooks:
            return []
        return [
            {
                "name": hr.hook_name,
                "phase": hr.phase.value,
                "success": hr.success,
                "message": hr.message,
                "blocked": hr.blocked,
                "duration_ms": hr.duration_ms,
            }
            for hr in self._hooks.history[-20:]
        ]

    def get_watcher_status(self) -> Dict[str, Any]:
        """Get file watcher status."""
        if not self._watcher:
            return {}
        return {
            "watchers": self._watcher.list_watchers(),
            "recent_events": [
                {
                    "type": e.event_type.value,
                    "path": e.path,
                    "timestamp": e.timestamp,
                }
                for e in self._watcher.recent_events[-10:]
            ],
        }

    # ========================================================================
    # Cognitive Layer
    # ========================================================================

    def set_cognitive_mode(self, mode: str) -> str:
        """Set cognitive mode (off/passive/guided/autonomous)."""
        if not self._cognitive:
            return "Cognitive layer not available."
        return self._cognitive.set_mode(mode)

    def get_cognitive_mode(self) -> str:
        """Get the current cognitive mode."""
        if not self._cognitive:
            return "off"
        return self._cognitive.mode.value

    def cognitive_learn(self, content: str, **kwargs) -> str:
        """Teach Nexus something explicitly."""
        if not self._cognitive:
            return ""
        return self._cognitive.learn(content, **kwargs)

    def cognitive_remember(self, content: str, **kwargs) -> str:
        """Store a memory explicitly."""
        if not self._cognitive:
            return ""
        return self._cognitive.remember(content, **kwargs)

    def get_cognitive_stats(self) -> Dict[str, Any]:
        """Get cognitive layer statistics."""
        if not self._cognitive:
            return {}
        return self._cognitive.stats()

    def get_reasoning_trace(self) -> str:
        """Get the reasoning trace summary."""
        if not self._cognitive:
            return "Cognitive layer not available."
        return self._cognitive.get_trace_summary()

    def get_knowledge_summary(self) -> str:
        """Get the knowledge store summary."""
        if not self._cognitive:
            return "Cognitive layer not available."
        return self._cognitive.get_knowledge_summary()

    def get_memory_summary(self) -> str:
        """Get the memory mesh summary."""
        if not self._cognitive:
            return "Cognitive layer not available."
        return self._cognitive.get_memory_summary()

    # -- core chat loop ------------------------------------------------------

    async def send(self, user_message: str) -> AsyncIterator[ChatEvent]:
        """Send a user message and stream the response.

        This is the main entry point. Intelligence features activate:
        1. ModelRouter picks the best model for this message
        2. StanceManager adapts behavior
        3. ProjectMap provides auto-context in the system prompt
        4. Tool calls are executed inline with safety checks

        Interactive features:
        5. PermissionManager gates tool execution
        6. HookEngine fires pre/post around tools
        7. DiffEngine generates previews for file writes
        8. ConversationTree tracks messages on branches

        Args:
            user_message: The user's message text.

        Yields:
            ChatEvent objects for each stage of the response.
        """
        self.history.append({"role": "user", "content": user_message})

        # Track message on branch tree
        if self._branch_tree:
            self._branch_tree.add_message("user", user_message)

        # === Cognitive: Analyze user message ===
        if self._cognitive:
            cog_events = self._cognitive.analyze_message(user_message)
            for ce in cog_events:
                if ce.event == "ambiguity_detected":
                    yield ChatEvent(
                        type=EventType.AMBIGUITY,
                        content=f"⚠ {ce.data.get('question_count', 0)} potential ambiguities detected",
                        data=ce.data,
                    )
                elif ce.event == "knowledge_retrieved":
                    yield ChatEvent(
                        type=EventType.KNOWLEDGE,
                        content=f"📚 {ce.data.get('count', 0)} relevant knowledge entries found",
                        data=ce.data,
                    )
                elif ce.event == "memory_recalled":
                    yield ChatEvent(
                        type=EventType.MEMORY,
                        content=f"🧠 {ce.data.get('count', 0)} related memories recalled",
                        data=ce.data,
                    )
                elif ce.event == "goal_set":
                    yield ChatEvent(
                        type=EventType.COGNITIVE,
                        content=f"🎯 Goal set: {ce.data.get('goal', '')[:80]}",
                        data=ce.data,
                    )

        # === Intelligence: Route to best model ===
        routed_model = self._route_message(user_message)
        turn_model = routed_model or self.model

        if routed_model and routed_model != self.model:
            decision = self._router.history[-1] if self._router else None
            yield ChatEvent(
                type=EventType.ROUTING,
                content=f"→ {routed_model}",
                data={
                    "model": routed_model,
                    "intent": decision.intent.value if decision else "general",
                    "confidence": decision.confidence if decision else 0,
                    "reasoning": decision.reasoning if decision else "",
                },
            )

        # === Intelligence: Notify stance change ===
        if self._stances and self._stances.current_config.stance.value != "default":
            cfg = self._stances.current_config
            yield ChatEvent(
                type=EventType.STANCE_CHANGE,
                content=f"{cfg.emoji} {cfg.display_name}",
                data={"stance": cfg.stance.value},
            )

        # Allow up to N sequential tool-call rounds per user turn
        max_tool_rounds = 10
        for round_num in range(max_tool_rounds):
            response_text = ""

            # Build messages with intelligence-enhanced system prompt
            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                *self.history,
            ]

            # Get LLM response using the routed model
            try:
                response_text = await self.llm.chat(
                    messages=messages,
                    model=turn_model,
                )
            except Exception as exc:
                yield ChatEvent(
                    type=EventType.ERROR,
                    content=f"LLM error: {exc}",
                )
                return

            if not response_text.strip():
                yield ChatEvent(
                    type=EventType.ERROR,
                    content="Empty response from LLM.",
                )
                return

            # Parse for tool calls
            tool_calls = self._extract_tool_calls(response_text)

            if not tool_calls:
                # No tool calls — plain response
                # Check if it contains a plan
                plan = self._extract_plan(response_text)
                if plan:
                    yield ChatEvent(
                        type=EventType.PLAN,
                        content=response_text,
                        data={"steps": plan},
                    )
                else:
                    yield ChatEvent(
                        type=EventType.TOKEN,
                        content=response_text,
                    )
                self.history.append({"role": "assistant", "content": response_text})

                # Track on branch tree
                if self._branch_tree:
                    self._branch_tree.add_message("assistant", response_text)

                # === Cognitive: Analyze AI response ===
                if self._cognitive:
                    self._cognitive.analyze_response(response_text)

                yield ChatEvent(type=EventType.DONE)
                return

            # Has tool calls — split text around them
            text_before_tools = self._text_before_first_tool(response_text)
            if text_before_tools.strip():
                yield ChatEvent(
                    type=EventType.THINKING,
                    content=text_before_tools.strip(),
                )

            # Execute each tool call with safety layer
            tool_results = []
            for tc in tool_calls:
                tool_name = tc["tool"]
                tool_args = tc.get("args", {})
                self._tool_call_count += 1

                yield ChatEvent(
                    type=EventType.TOOL_CALL,
                    content=f"Calling {tool_name}",
                    data={"tool": tool_name, "args": tool_args, "index": self._tool_call_count},
                )

                # === Safety: Permission check ===
                # Only run permission checks for known tools — unknown tools
                # fall through to _execute_tool which returns a clear error.
                permission_blocked = False
                tool_is_known = tool_name in self._tools
                if self._permissions and tool_is_known:
                    blocked_reason = self._permissions.is_blocked(tool_name, tool_args)
                    if blocked_reason:
                        result = f"⛔ {blocked_reason}"
                        permission_blocked = True
                        yield ChatEvent(
                            type=EventType.PERMISSION,
                            content=f"Blocked: {tool_name}",
                            data={"tool": tool_name, "status": "blocked", "reason": blocked_reason},
                        )
                    elif not self._permissions.check(tool_name, tool_args):
                        result = (
                            f"⚠ Permission denied: '{tool_name}' requires higher trust level "
                            f"(current: {self._permissions.trust_level.name})"
                        )
                        permission_blocked = True
                        yield ChatEvent(
                            type=EventType.PERMISSION,
                            content=f"Denied: {tool_name}",
                            data={
                                "tool": tool_name,
                                "status": "denied",
                                "trust_level": self._permissions.trust_level.name,
                            },
                        )

                if not permission_blocked:
                    # === Cognitive: Pre-execution verification ===
                    if self._cognitive:
                        cog_pre = self._cognitive.before_tool_call(tool_name, tool_args)
                        for ce in cog_pre:
                            if ce.event == "verification_warning":
                                yield ChatEvent(
                                    type=EventType.VERIFICATION,
                                    content=f"⚡ Design check: {ce.data.get('summary', '')}",
                                    data=ce.data,
                                )

                    # === Hooks: Pre-execution ===
                    hook_blocked = False
                    if self._hooks:
                        pre_results = await self._hooks.fire_pre(tool_name, tool_args)
                        for hr in pre_results:
                            if hr.blocked:
                                result = f"🪝 Blocked by hook '{hr.hook_name}': {hr.message}"
                                hook_blocked = True
                                yield ChatEvent(
                                    type=EventType.HOOK,
                                    content=f"PRE hook blocked: {hr.hook_name}",
                                    data={
                                        "hook": hr.hook_name,
                                        "phase": "pre",
                                        "blocked": True,
                                        "message": hr.message,
                                    },
                                )
                                break
                            elif hr.modified_args:
                                tool_args = hr.modified_args
                                yield ChatEvent(
                                    type=EventType.HOOK,
                                    content=f"PRE hook modified args: {hr.hook_name}",
                                    data={
                                        "hook": hr.hook_name,
                                        "phase": "pre",
                                        "modified": True,
                                    },
                                )

                    if not hook_blocked:
                        # === Diff preview for file writes ===
                        diff_generated = False
                        if (
                            self._diff_engine
                            and tool_name == "file_write"
                            and "path" in tool_args
                            and "content" in tool_args
                        ):
                            try:
                                diff = self._diff_engine.diff(
                                    tool_args["path"],
                                    tool_args["content"],
                                )
                                if not diff.is_empty:
                                    diff_generated = True
                                    yield ChatEvent(
                                        type=EventType.DIFF_PREVIEW,
                                        content=diff.unified,
                                        data={
                                            "path": diff.path,
                                            "type": diff.diff_type.value,
                                            "stats": diff.stats,
                                            "hunks": len(diff.hunks),
                                        },
                                    )
                                    # Auto-apply if configured
                                    if self._diff_auto_apply:
                                        diff.accept_all()
                                        self._diff_engine.apply(diff)
                            except Exception as exc:
                                logger.warning("Diff generation failed: %s", exc)

                        # Execute the tool
                        start_time = time.time()
                        if diff_generated and self._diff_auto_apply:
                            # file_write was already applied via diff engine
                            result = f"✅ File written via diff engine: {tool_args.get('path', '?')}"
                        else:
                            result = await self._execute_tool(tool_name, tool_args)
                        duration_ms = (time.time() - start_time) * 1000

                        # === Hooks: Post-execution ===
                        if self._hooks:
                            post_results = await self._hooks.fire_post(
                                tool_name,
                                tool_args,
                                result=str(result)[:500],
                                success=not str(result).startswith("Error"),
                            )
                            for hr in post_results:
                                if hr.message:
                                    yield ChatEvent(
                                        type=EventType.HOOK,
                                        content=f"POST hook: {hr.hook_name}",
                                        data={
                                            "hook": hr.hook_name,
                                            "phase": "post",
                                            "message": hr.message,
                                        },
                                    )

                        # === Audit: Log execution ===
                        if self._permissions:
                            self._permissions.log_execution(
                                tool_name,
                                tool_args,
                                result=str(result)[:200],
                                success=not str(result).startswith("Error"),
                                duration_ms=duration_ms,
                            )

                        # === Cognitive: Post-execution learning ===
                        if self._cognitive:
                            self._cognitive.after_tool_call(
                                tool_name, tool_args, str(result)[:1000],
                                success=not str(result).startswith("Error"),
                            )

                tool_results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                })

                yield ChatEvent(
                    type=EventType.TOOL_RESULT,
                    content=result[:2000],
                    data={"tool": tool_name, "success": not result.startswith("Error")},
                )

            # Add assistant message and tool results to history
            self.history.append({"role": "assistant", "content": response_text})
            if self._branch_tree:
                self._branch_tree.add_message("assistant", response_text)

            # Format tool results for the next LLM turn
            results_text = "\n".join(
                f"[Tool: {r['tool']}]\n{r['result']}" for r in tool_results
            )
            self.history.append({
                "role": "user",
                "content": f"[Tool results — do not repeat these, just continue]\n{results_text}",
            })

            # Continue the loop — LLM sees tool results and can respond or call more tools

        # If we hit max rounds
        yield ChatEvent(
            type=EventType.ERROR,
            content=f"Reached maximum tool rounds ({max_tool_rounds}).",
        )

    # -- streaming send (token-by-token) ------------------------------------

    async def send_streaming(self, user_message: str) -> AsyncIterator[ChatEvent]:
        """Send a user message with token-by-token streaming.

        Unlike send(), this streams individual tokens for live display.
        Tool calls are detected after the full response is received,
        then executed, and the conversation continues.

        Also uses intelligence layer (routing, stances, project context)
        and interactive layer (permissions, hooks, diffs).
        """
        self.history.append({"role": "user", "content": user_message})

        if self._branch_tree:
            self._branch_tree.add_message("user", user_message)

        # === Cognitive: Analyze user message ===
        if self._cognitive:
            cog_events = self._cognitive.analyze_message(user_message)
            for ce in cog_events:
                if ce.event == "ambiguity_detected":
                    yield ChatEvent(
                        type=EventType.AMBIGUITY,
                        content=f"⚠ {ce.data.get('question_count', 0)} potential ambiguities detected",
                        data=ce.data,
                    )
                elif ce.event == "knowledge_retrieved":
                    yield ChatEvent(
                        type=EventType.KNOWLEDGE,
                        content=f"📚 {ce.data.get('count', 0)} relevant knowledge entries found",
                        data=ce.data,
                    )
                elif ce.event == "memory_recalled":
                    yield ChatEvent(
                        type=EventType.MEMORY,
                        content=f"🧠 {ce.data.get('count', 0)} related memories recalled",
                        data=ce.data,
                    )
                elif ce.event == "goal_set":
                    yield ChatEvent(
                        type=EventType.COGNITIVE,
                        content=f"🎯 Goal set: {ce.data.get('goal', '')[:80]}",
                        data=ce.data,
                    )

        # === Intelligence: Route to best model ===
        routed_model = self._route_message(user_message)
        turn_model = routed_model or self.model

        if routed_model and routed_model != self.model:
            decision = self._router.history[-1] if self._router else None
            yield ChatEvent(
                type=EventType.ROUTING,
                content=f"→ {routed_model}",
                data={
                    "model": routed_model,
                    "intent": decision.intent.value if decision else "general",
                    "confidence": decision.confidence if decision else 0,
                },
            )

        # === Intelligence: Notify stance change ===
        if self._stances and self._stances.current_config.stance.value != "default":
            cfg = self._stances.current_config
            yield ChatEvent(
                type=EventType.STANCE_CHANGE,
                content=f"{cfg.emoji} {cfg.display_name}",
                data={"stance": cfg.stance.value},
            )

        # Stance temperature modifier
        temp = self.config.temperature
        if self._stances:
            temp += self._stances.get_temperature_modifier()
            temp = max(0.0, min(temp, 2.0))  # Clamp

        max_tool_rounds = 10
        for round_num in range(max_tool_rounds):
            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                *self.history,
            ]

            # Stream the response token by token
            full_response = ""
            try:
                payload = {
                    "model": turn_model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": temp},
                }
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = f"{self.config.ollama_url}/api/chat"
                    async with session.post(url, json=payload) as resp:
                        async for line in resp.content:
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    full_response += token
                                    yield ChatEvent(
                                        type=EventType.TOKEN,
                                        content=token,
                                    )
                                if data.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
            except Exception as exc:
                yield ChatEvent(type=EventType.ERROR, content=f"Stream error: {exc}")
                return

            if not full_response.strip():
                yield ChatEvent(type=EventType.ERROR, content="Empty response.")
                return

            # Check for tool calls in the complete response
            tool_calls = self._extract_tool_calls(full_response)

            if not tool_calls:
                self.history.append({"role": "assistant", "content": full_response})
                if self._branch_tree:
                    self._branch_tree.add_message("assistant", full_response)
                yield ChatEvent(type=EventType.DONE)
                return

            # Execute tool calls with safety layer
            tool_results = []
            for tc in tool_calls:
                tool_name = tc["tool"]
                tool_args = tc.get("args", {})
                self._tool_call_count += 1

                yield ChatEvent(
                    type=EventType.TOOL_CALL,
                    content=f"Calling {tool_name}",
                    data={"tool": tool_name, "args": tool_args},
                )

                # Permission check (only for known tools)
                permission_ok = True
                tool_is_known = tool_name in self._tools
                if self._permissions and tool_is_known:
                    blocked = self._permissions.is_blocked(tool_name, tool_args)
                    if blocked:
                        result = f"⛔ {blocked}"
                        permission_ok = False
                    elif not self._permissions.check(tool_name, tool_args):
                        result = f"⚠ Permission denied for '{tool_name}'"
                        permission_ok = False

                if permission_ok:
                    # Pre hooks
                    hook_ok = True
                    if self._hooks:
                        pre_results = await self._hooks.fire_pre(tool_name, tool_args)
                        for hr in pre_results:
                            if hr.blocked:
                                result = f"🪝 Blocked by '{hr.hook_name}'"
                                hook_ok = False
                                break
                            if hr.modified_args:
                                tool_args = hr.modified_args

                    if hook_ok:
                        # Diff preview for file writes
                        diff_applied = False
                        if (
                            self._diff_engine
                            and tool_name == "file_write"
                            and "path" in tool_args
                            and "content" in tool_args
                        ):
                            try:
                                diff = self._diff_engine.diff(
                                    tool_args["path"], tool_args["content"]
                                )
                                if not diff.is_empty:
                                    yield ChatEvent(
                                        type=EventType.DIFF_PREVIEW,
                                        content=diff.unified,
                                        data={
                                            "path": diff.path,
                                            "stats": diff.stats,
                                        },
                                    )
                                    if self._diff_auto_apply:
                                        diff.accept_all()
                                        self._diff_engine.apply(diff)
                                        diff_applied = True
                            except Exception:
                                pass

                        start_time = time.time()
                        if diff_applied:
                            result = f"✅ Written via diff: {tool_args.get('path', '?')}"
                        else:
                            result = await self._execute_tool(tool_name, tool_args)
                        duration_ms = (time.time() - start_time) * 1000

                        # Post hooks
                        if self._hooks:
                            await self._hooks.fire_post(
                                tool_name, tool_args,
                                result=str(result)[:500],
                                success=not str(result).startswith("Error"),
                            )

                        # Audit
                        if self._permissions:
                            self._permissions.log_execution(
                                tool_name, tool_args,
                                result=str(result)[:200],
                                duration_ms=duration_ms,
                            )

                tool_results.append({"tool": tool_name, "result": result})

                yield ChatEvent(
                    type=EventType.TOOL_RESULT,
                    content=result[:2000],
                    data={"tool": tool_name, "success": not result.startswith("Error")},
                )

            self.history.append({"role": "assistant", "content": full_response})
            if self._branch_tree:
                self._branch_tree.add_message("assistant", full_response)

            results_text = "\n".join(
                f"[Tool: {r['tool']}]\n{r['result']}" for r in tool_results
            )
            self.history.append({
                "role": "user",
                "content": f"[Tool results — do not repeat these, just continue]\n{results_text}",
            })

        yield ChatEvent(type=EventType.DONE)

    # -- tool execution ------------------------------------------------------

    async def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool and return the result string."""
        tool = self._tools.get(name)
        if not tool:
            # Try fuzzy matching
            for tname, t in self._tools.items():
                if name.lower() in tname.lower() or tname.lower() in name.lower():
                    tool = t
                    break
                if hasattr(t, "aliases"):
                    for alias in t.aliases:
                        if name.lower() == alias.lower():
                            tool = t
                            break

        if not tool:
            return f"Error: Unknown tool '{name}'. Available: {', '.join(self._tools.keys())}"

        try:
            result = await tool.execute(**args)
            return str(result)
        except Exception as exc:
            logger.error("Tool %s failed: %s", name, exc)
            return f"Error executing {name}: {exc}"

    # -- parsing helpers -----------------------------------------------------

    @staticmethod
    def _extract_tool_calls(text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from LLM response text.

        Looks for ```tool ... ``` blocks containing JSON with
        "tool" and "args" keys.
        """
        calls = []

        # Pattern 1: ```tool { ... } ```
        tool_blocks = re.findall(
            r'```tool\s*\n?(.*?)\n?```',
            text,
            re.DOTALL,
        )
        for block in tool_blocks:
            parsed = extract_json(block)
            if isinstance(parsed, dict) and "tool" in parsed:
                calls.append(parsed)
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "tool" in item:
                        calls.append(item)

        # Pattern 2: ```json { "tool": ... } ``` (common LLM habit)
        if not calls:
            json_blocks = re.findall(
                r'```(?:json)?\s*\n?(.*?)\n?```',
                text,
                re.DOTALL,
            )
            for block in json_blocks:
                parsed = extract_json(block)
                if isinstance(parsed, dict) and "tool" in parsed:
                    calls.append(parsed)

        return calls

    @staticmethod
    def _extract_plan(text: str) -> List[str]:
        """Extract a numbered plan from the response text.

        Returns a list of plan step strings, or empty list if no plan found.
        """
        # Look for numbered lists (1. ... 2. ... 3. ...)
        steps = re.findall(r'^\s*(\d+)\.\s+(.+)$', text, re.MULTILINE)
        if len(steps) >= 2:
            return [step_text.strip() for _, step_text in steps]
        return []

    @staticmethod
    def _text_before_first_tool(text: str) -> str:
        """Get text content before the first tool call block."""
        match = re.search(r'```tool', text)
        if match:
            return text[:match.start()]
        return text

    # -- session info --------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        result = {
            "turns": self.turn_count,
            "messages": len(self.history),
            "tool_calls": self._tool_call_count,
            "duration_seconds": round(time.time() - self._session_start, 1),
            "model": self.model,
            "workspace": self.workspace,
        }

        # Intelligence stats
        if self._stances:
            result["stance"] = self._stances.current.value
        if self._router:
            result["routing"] = self._router.stats()
        if self._project_map and self._project_map._scanned:
            result["project"] = {
                "type": self._project_map.project_type,
                "files": len(self._project_map.files),
            }

        # Interactive stats
        if self._branch_tree:
            result["branch"] = self._branch_tree.current_branch
            result["branches"] = self._branch_tree.branch_count
        if self._diff_engine:
            result["pending_diffs"] = self._diff_engine.pending_count
            result["diff_history"] = self._diff_engine.history_count
        if self._permissions:
            audit = self._permissions.audit_summary()
            result["audit"] = {
                "approved": audit.get("approved", 0),
                "blocked": audit.get("blocked", 0),
                "trust_level": audit.get("trust_level", "?"),
            }
        if self._hooks:
            result["hooks"] = len(self._hooks.list_hooks())

        # Cognitive stats
        if self._cognitive:
            result["cognitive"] = self._cognitive.stats()

        return result
