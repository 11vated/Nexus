"""Conversation Stances — adaptive personas for different tasks.

Most AI tools have one personality. Nexus shifts its behavior based on
what you're doing — like a senior engineer who naturally switches between
being a careful code reviewer and a creative brainstorming partner.

Each stance modifies:
- System prompt tone and rules
- Temperature (creative vs precise)
- Tool preferences (which tools to favor)
- Response style (verbose vs concise)

Stances can be set manually (/stance reviewer) or detected automatically
from the conversation context.

Usage:
    manager = StanceManager()
    stance = manager.detect("Find the bug in this function")
    # → Stance.DEBUGGER

    prompt_modifier = manager.get_prompt_modifier(stance)
    # → "You are in debugging mode. Be systematic..."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from nexus.intelligence.model_router import TaskIntent


class Stance(Enum):
    """Available conversation stances."""
    ARCHITECT = "architect"
    PAIR_PROGRAMMER = "pair_programmer"
    DEBUGGER = "debugger"
    REVIEWER = "reviewer"
    TEACHER = "teacher"
    EXPLORER = "explorer"
    DEFAULT = "default"


@dataclass
class StanceConfig:
    """Configuration for a conversation stance."""
    stance: Stance
    display_name: str
    emoji: str
    description: str

    # Behavioral modifiers
    system_prompt_addon: str        # Added to the system prompt
    temperature_modifier: float     # Added to base temperature
    preferred_tools: List[str]      # Tools this stance favors
    response_style: str             # "concise", "detailed", "socratic"
    auto_plan: bool                 # Auto-propose plans before executing?

    # Intent triggers — which intents activate this stance
    triggered_by: List[TaskIntent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in stance configurations
# ---------------------------------------------------------------------------

_STANCE_CONFIGS: Dict[Stance, StanceConfig] = {
    Stance.ARCHITECT: StanceConfig(
        stance=Stance.ARCHITECT,
        display_name="Architect",
        emoji="🏗",
        description="High-level design and planning. Asks probing questions, thinks about trade-offs.",
        system_prompt_addon="""\
You are in ARCHITECT mode. Your focus is on design and planning.

Behavioral rules for this mode:
- Think about the big picture before diving into code
- Ask clarifying questions about requirements and constraints
- Consider trade-offs explicitly (performance vs simplicity, etc.)
- Propose multiple approaches when there's no obvious best choice
- Use diagrams (ASCII art) when they help explain structure
- Reference design patterns by name when applicable
- DON'T write implementation code unless the user explicitly asks
- DO outline file structure, interfaces, and data flow
""",
        temperature_modifier=0.2,
        preferred_tools=["file_list", "search", "file_read"],
        response_style="detailed",
        auto_plan=True,
        triggered_by=[TaskIntent.ARCHITECTURE],
    ),

    Stance.PAIR_PROGRAMMER: StanceConfig(
        stance=Stance.PAIR_PROGRAMMER,
        display_name="Pair Programmer",
        emoji="👥",
        description="Write code together. Explains choices, offers alternatives.",
        system_prompt_addon="""\
You are in PAIR PROGRAMMING mode. You're coding alongside the user.

Behavioral rules for this mode:
- Write code incrementally — show small pieces, explain, then continue
- Explain WHY you made each choice, not just what you wrote
- Offer alternatives when there's more than one good approach
- Use the user's existing code style (match indentation, naming, patterns)
- Run code and tests after writing to verify immediately
- If you're unsure about something, say so and ask
- Keep a running commentary of what you're thinking
""",
        temperature_modifier=0.0,
        preferred_tools=["file_write", "file_read", "code_run", "test_run"],
        response_style="detailed",
        auto_plan=False,
        triggered_by=[TaskIntent.CODE_GENERATION, TaskIntent.CODE_EDIT],
    ),

    Stance.DEBUGGER: StanceConfig(
        stance=Stance.DEBUGGER,
        display_name="Debugger",
        emoji="🔍",
        description="Systematic bug hunting. Forms hypotheses, tests them.",
        system_prompt_addon="""\
You are in DEBUGGER mode. Be systematic and thorough.

Behavioral rules for this mode:
- Start by gathering information: read the error, check logs, inspect state
- Form explicit hypotheses: "This could be caused by X, Y, or Z"
- Test one hypothesis at a time, starting with the most likely
- Read relevant source code before making assumptions
- Check for common causes: off-by-one, null/None, wrong type, race condition
- After finding the bug, explain the root cause clearly
- Suggest a fix AND explain why the bug happened to prevent recurrence
- Use the search tool to find similar patterns that might have the same bug
""",
        temperature_modifier=-0.1,
        preferred_tools=["search", "file_read", "shell", "test_run"],
        response_style="detailed",
        auto_plan=True,
        triggered_by=[TaskIntent.DEBUGGING],
    ),

    Stance.REVIEWER: StanceConfig(
        stance=Stance.REVIEWER,
        display_name="Code Reviewer",
        emoji="📋",
        description="Critical code review. Finds bugs, suggests improvements.",
        system_prompt_addon="""\
You are in CODE REVIEW mode. Be thorough but constructive.

Behavioral rules for this mode:
- Read the code carefully before commenting
- Categorize findings: 🐛 bug, ⚠️ concern, 💡 suggestion, ✅ looks good
- Prioritize: security issues > bugs > performance > style
- For each issue, explain WHY it's a problem and HOW to fix it
- Acknowledge what's done well, not just problems
- Check for: error handling, edge cases, input validation, resource cleanup
- Look for missing tests and suggest what to test
- Be specific — quote the problematic code, show the fix
""",
        temperature_modifier=-0.1,
        preferred_tools=["file_read", "search"],
        response_style="detailed",
        auto_plan=False,
        triggered_by=[TaskIntent.CODE_REVIEW],
    ),

    Stance.TEACHER: StanceConfig(
        stance=Stance.TEACHER,
        display_name="Teacher",
        emoji="📚",
        description="Explains concepts and teaches. Uses examples and analogies.",
        system_prompt_addon="""\
You are in TEACHER mode. Help the user understand, don't just give answers.

Behavioral rules for this mode:
- Start with a high-level explanation, then go deeper
- Use concrete examples from the user's actual codebase when possible
- Analogies help — relate new concepts to things the user already knows
- If the concept is complex, break it into numbered steps
- Ask "Does that make sense?" at natural breakpoints
- Show both the RIGHT way and the WRONG way (and why)
- Use code examples to illustrate concepts
- Link to the actual source code in the project when relevant
""",
        temperature_modifier=0.15,
        preferred_tools=["file_read", "search"],
        response_style="socratic",
        auto_plan=False,
        triggered_by=[TaskIntent.EXPLANATION],
    ),

    Stance.EXPLORER: StanceConfig(
        stance=Stance.EXPLORER,
        display_name="Explorer",
        emoji="🧭",
        description="Investigate and understand unfamiliar code. Map the territory.",
        system_prompt_addon="""\
You are in EXPLORER mode. Help the user understand an unfamiliar codebase.

Behavioral rules for this mode:
- Start broad: file structure, entry points, key components
- Map relationships: what calls what, data flow, control flow
- Identify patterns: what framework, what conventions, what architecture
- Read config files first (they reveal project structure)
- Summarize your findings in a structured way
- Create a mental map the user can reference later
- Highlight anything unusual, confusing, or noteworthy
""",
        temperature_modifier=0.1,
        preferred_tools=["file_list", "file_read", "search"],
        response_style="detailed",
        auto_plan=True,
        triggered_by=[TaskIntent.GENERAL],
    ),

    Stance.DEFAULT: StanceConfig(
        stance=Stance.DEFAULT,
        display_name="General",
        emoji="💬",
        description="Balanced general-purpose mode.",
        system_prompt_addon="",
        temperature_modifier=0.0,
        preferred_tools=[],
        response_style="concise",
        auto_plan=True,
        triggered_by=[],
    ),
}


# ---------------------------------------------------------------------------
# StanceManager
# ---------------------------------------------------------------------------

class StanceManager:
    """Manages conversation stance detection and switching.

    Can be used in auto mode (detects stance from intent) or manual
    mode (user picks with /stance command).
    """

    def __init__(self):
        self._current: Stance = Stance.DEFAULT
        self._configs = dict(_STANCE_CONFIGS)
        self._auto_detect: bool = True
        self._history: List[Stance] = []

    @property
    def current(self) -> Stance:
        return self._current

    @property
    def current_config(self) -> StanceConfig:
        return self._configs[self._current]

    def set_stance(self, stance: Stance) -> StanceConfig:
        """Manually set the conversation stance."""
        self._current = stance
        self._history.append(stance)
        return self._configs[stance]

    def set_auto_detect(self, enabled: bool) -> None:
        """Enable/disable automatic stance detection."""
        self._auto_detect = enabled

    def detect_from_intent(self, intent: TaskIntent) -> Stance:
        """Detect the best stance for a given task intent.

        Returns the matched stance (or DEFAULT if none match).
        Also updates the current stance if auto-detect is enabled.
        """
        for stance, config in self._configs.items():
            if intent in config.triggered_by:
                if self._auto_detect:
                    self._current = stance
                    self._history.append(stance)
                return stance
        return Stance.DEFAULT

    def get_prompt_modifier(self, stance: Optional[Stance] = None) -> str:
        """Get the system prompt addon for a stance."""
        s = stance or self._current
        return self._configs[s].system_prompt_addon

    def get_temperature_modifier(self, stance: Optional[Stance] = None) -> float:
        """Get the temperature adjustment for a stance."""
        s = stance or self._current
        return self._configs[s].temperature_modifier

    def list_stances(self) -> List[Dict[str, str]]:
        """List all available stances."""
        return [
            {
                "name": config.stance.value,
                "display": f"{config.emoji} {config.display_name}",
                "description": config.description,
                "active": config.stance == self._current,
            }
            for config in self._configs.values()
        ]

    def add_custom_stance(self, config: StanceConfig) -> None:
        """Register a custom stance."""
        self._configs[config.stance] = config

    def stats(self) -> Dict[str, Any]:
        """Get stance usage statistics."""
        from collections import Counter
        counts = Counter(s.value for s in self._history)
        return {
            "current": self._current.value,
            "auto_detect": self._auto_detect,
            "history_length": len(self._history),
            "usage": dict(counts),
        }
