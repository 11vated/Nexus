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
    TOKEN = "token"              # Streaming text token
    TOOL_CALL = "tool_call"      # LLM wants to call a tool
    TOOL_RESULT = "tool_result"  # Result from tool execution
    PLAN = "plan"                # LLM proposed a multi-step plan
    THINKING = "thinking"        # LLM reasoning / scratchpad
    ROUTING = "routing"          # Model routing decision (new!)
    STANCE_CHANGE = "stance"     # Stance change notification (new!)
    ERROR = "error"              # Something went wrong
    DONE = "done"                # Turn complete


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
        self._router = None       # ModelRouter
        self._stances = None      # StanceManager
        self._project_map = None  # ProjectMap
        self._session_store = None  # SessionStore
        self._intelligence_enabled = True
        self._session_id: Optional[str] = None

        self._setup_tools()
        self._setup_intelligence()

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
        """Build the system prompt with intelligence context."""
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

        return CHAT_SYSTEM_PROMPT.format(
            tool_descriptions=self._get_tool_descriptions(),
            stance_prompt=stance_prompt,
            project_context=project_context,
            project_rules=rules_section,
            workspace=self.workspace,
        )

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

    # -- core chat loop ------------------------------------------------------

    async def send(self, user_message: str) -> AsyncIterator[ChatEvent]:
        """Send a user message and stream the response.

        This is the main entry point. Intelligence features activate:
        1. ModelRouter picks the best model for this message
        2. StanceManager adapts behavior
        3. ProjectMap provides auto-context in the system prompt
        4. Tool calls are executed inline

        Args:
            user_message: The user's message text.

        Yields:
            ChatEvent objects for each stage of the response.
        """
        self.history.append({"role": "user", "content": user_message})

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
                yield ChatEvent(type=EventType.DONE)
                return

            # Has tool calls — split text around them
            text_before_tools = self._text_before_first_tool(response_text)
            if text_before_tools.strip():
                yield ChatEvent(
                    type=EventType.THINKING,
                    content=text_before_tools.strip(),
                )

            # Execute each tool call
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

                result = await self._execute_tool(tool_name, tool_args)
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

        Also uses intelligence layer (routing, stances, project context).
        """
        self.history.append({"role": "user", "content": user_message})

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
                yield ChatEvent(type=EventType.DONE)
                return

            # Execute tool calls
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

                result = await self._execute_tool(tool_name, tool_args)
                tool_results.append({"tool": tool_name, "result": result})

                yield ChatEvent(
                    type=EventType.TOOL_RESULT,
                    content=result[:2000],
                    data={"tool": tool_name, "success": not result.startswith("Error")},
                )

            self.history.append({"role": "assistant", "content": full_response})
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

        return result
