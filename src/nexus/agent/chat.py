"""Collaborative chat session — conversational coding partner.

Unlike the autonomous AgentLoop (Plan → Act → Observe → Reflect),
ChatSession maintains a persistent dialogue where the user and Nexus
collaborate interactively.  The LLM can call tools, but only when it
makes sense in the conversation — never firing off an autonomous
multi-step pipeline unless the user explicitly asks.

The design mirrors how Claude Code or Copilot Chat work:
  1. User types a message
  2. Nexus responds (streaming) — may include tool calls
  3. Tool results are fed back into the conversation
  4. The user can refine, approve, reject, or redirect at any point

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
        self._setup_tools()

    # -- setup ---------------------------------------------------------------

    def _setup_tools(self) -> None:
        """Initialize the default tool set."""
        raw_tools = create_default_tools(self.workspace)
        for name, tool in raw_tools.items():
            self._tools[name] = tool

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
        """Build the system prompt with current context."""
        rules_section = ""
        if self.project_rules:
            rules_section = (
                f"Project-specific rules (.nexus/rules.md):\n"
                f"{self.project_rules}\n"
            )
        return CHAT_SYSTEM_PROMPT.format(
            tool_descriptions=self._get_tool_descriptions(),
            project_rules=rules_section,
            workspace=self.workspace,
        )

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

    # -- core chat loop ------------------------------------------------------

    async def send(self, user_message: str) -> AsyncIterator[ChatEvent]:
        """Send a user message and stream the response.

        This is the main entry point. It:
        1. Adds the user message to history
        2. Calls the LLM with full history
        3. Parses the response for tool calls
        4. Executes tool calls inline
        5. If tool calls were made, sends another LLM turn with results
        6. Yields ChatEvent objects throughout

        Args:
            user_message: The user's message text.

        Yields:
            ChatEvent objects for each stage of the response.
        """
        self.history.append({"role": "user", "content": user_message})

        # Allow up to N sequential tool-call rounds per user turn
        max_tool_rounds = 10
        for round_num in range(max_tool_rounds):
            response_text = ""

            # Build messages with system prompt
            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                *self.history,
            ]

            # Get LLM response (non-streaming for tool detection reliability)
            try:
                response_text = await self.llm.chat(
                    messages=messages,
                    model=self.model,
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

        This is the preferred method for TUI display.
        """
        self.history.append({"role": "user", "content": user_message})

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
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": self.config.temperature},
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
        return {
            "turns": self.turn_count,
            "messages": len(self.history),
            "tool_calls": self._tool_call_count,
            "duration_seconds": round(time.time() - self._session_start, 1),
            "model": self.model,
            "workspace": self.workspace,
        }
