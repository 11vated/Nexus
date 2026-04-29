"""Interactive TUI dashboard for the Nexus agent.

Provides a full-screen Rich-based dashboard that shows:
- Agent state and progress
- Live step execution
- Tool registry
- Memory stats
- Goal input

Use: nexus tui
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.spinner import Spinner
from rich.align import Align
from rich.columns import Columns
from rich.prompt import Prompt

from nexus.agent.loop import AgentLoop
from nexus.agent.models import AgentConfig, AgentState, Step
from nexus.tools import create_default_tools

STATE_STYLES = {
    "idle": ("⏸ IDLE", "dim"),
    "planning": ("🧠 PLANNING", "bold yellow"),
    "acting": ("⚡ ACTING", "bold cyan"),
    "observing": ("👁 OBSERVING", "bold blue"),
    "reflecting": ("🔍 REFLECTING", "bold magenta"),
    "correcting": ("🔧 CORRECTING", "bold yellow"),
    "done": ("✅ DONE", "bold green"),
    "error": ("❌ ERROR", "bold red"),
}


class NexusDashboard:
    """Full-screen interactive agent dashboard.

    Layout:
    ┌─────────────────────────────────────┐
    │  NEXUS — state banner               │
    ├──────────────────┬──────────────────┤
    │  Steps (main)    │  Info sidebar    │
    │                  │  - Tools         │
    │                  │  - Memory        │
    │                  │  - Config        │
    ├──────────────────┴──────────────────┤
    │  Current step detail / input        │
    └─────────────────────────────────────┘
    """

    def __init__(
        self,
        workspace: str = ".",
        config: Optional[AgentConfig] = None,
    ):
        self.console = Console()
        self.workspace = str(Path(workspace).resolve())
        self.config = config or AgentConfig(workspace_path=self.workspace)
        self.agent: Optional[AgentLoop] = None
        self.step_log: List[Dict[str, Any]] = []
        self.current_state = "idle"
        self.current_goal = ""
        self.start_time: Optional[float] = None
        self.result: Optional[Dict[str, Any]] = None
        self._tool_names: List[str] = []

    def _make_layout(self) -> Layout:
        """Create the dashboard layout structure."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=5),
        )
        layout["body"].split_row(
            Layout(name="steps", ratio=3),
            Layout(name="sidebar", ratio=1, minimum_size=28),
        )
        return layout

    def _render_header(self) -> Panel:
        """Render the top status bar."""
        state_text, state_style = STATE_STYLES.get(
            self.current_state, ("? UNKNOWN", "dim")
        )
        elapsed = f" · {time.time() - self.start_time:.0f}s" if self.start_time else ""
        goal_display = self.current_goal[:80] if self.current_goal else "No goal set"

        header = Text.assemble(
            ("  NEXUS  ", "bold white on blue"),
            ("  ", ""),
            (state_text, state_style),
            (elapsed, "dim"),
            ("  │  ", "dim"),
            (goal_display, "italic"),
        )
        return Panel(header, style="blue", height=3)

    def _render_steps(self) -> Panel:
        """Render the main steps panel."""
        if not self.step_log:
            content = Align.center(
                Text("No steps yet — enter a goal to start", style="dim"),
                vertical="middle",
            )
            return Panel(content, title="Steps", border_style="cyan")

        table = Table(show_header=True, expand=True, show_lines=False)
        table.add_column("#", style="dim", width=3)
        table.add_column("Action", ratio=3)
        table.add_column("Tool", style="cyan", width=12)
        table.add_column("", width=2)
        table.add_column("Time", style="dim", width=7)

        for i, s in enumerate(self.step_log[-20:], 1):  # Show last 20
            icon = "✓" if s["success"] else "✗"
            style = "green" if s["success"] else "red"
            action = s["action"][:55] + ("…" if len(s["action"]) > 55 else "")
            ms = f"{s['duration_ms']:.0f}ms" if s.get("duration_ms") else ""
            table.add_row(str(i), action, s.get("tool", ""), f"[{style}]{icon}[/{style}]", ms)

        return Panel(table, title=f"Steps ({len(self.step_log)})", border_style="cyan")

    def _render_sidebar(self) -> Panel:
        """Render the info sidebar."""
        sections = []

        # Tools section
        tools_text = Text()
        tools_text.append("Tools\n", style="bold cyan")
        for t in self._tool_names[:10]:
            tools_text.append(f"  • {t}\n", style="dim")
        sections.append(tools_text)

        # Memory section
        mem_text = Text()
        mem_text.append("\nMemory\n", style="bold magenta")
        if self.agent:
            mem_text.append(f"  Short-term: {self.agent.short_term.size} entries\n", style="dim")
            if self.agent.long_term:
                mem_text.append(f"  Long-term:  {self.agent.long_term.count} docs\n", style="dim")
        sections.append(mem_text)

        # Stats section
        if self.step_log:
            stats_text = Text()
            stats_text.append("\nStats\n", style="bold yellow")
            ok = sum(1 for s in self.step_log if s["success"])
            total = len(self.step_log)
            stats_text.append(f"  Passed: {ok}/{total}\n", style="dim")
            if self.start_time:
                stats_text.append(f"  Time:   {time.time() - self.start_time:.0f}s\n", style="dim")
            sections.append(stats_text)

        # Config section
        config_text = Text()
        config_text.append("\nConfig\n", style="bold blue")
        config_text.append(f"  Plan: {self.config.planning_model}\n", style="dim")
        config_text.append(f"  Code: {self.config.coding_model}\n", style="dim")
        config_text.append(f"  Max:  {self.config.max_iterations} iters\n", style="dim")
        sections.append(config_text)

        return Panel(Group(*sections), title="Info", border_style="blue")

    def _render_footer(self) -> Panel:
        """Render the bottom detail / status panel."""
        if self.result:
            success = self.result.get("success", False)
            style = "green" if success else "red"
            icon = "✅" if success else "❌"
            text = (
                f"{icon} {'SUCCESS' if success else 'FAILED'} — "
                f"{self.result.get('steps_successful', 0)}/{self.result.get('steps_total', 0)} steps, "
                f"{self.result.get('duration_seconds', 0)}s"
            )
            return Panel(text, title="Result", border_style=style)

        if self.step_log:
            last = self.step_log[-1]
            detail = last.get("result", "")[:200]
            icon = "✓" if last["success"] else "✗"
            return Panel(
                f"[{'green' if last['success'] else 'red'}]{icon}[/] {last['action']}\n{detail}",
                title="Latest Step",
                border_style="cyan",
            )

        return Panel(
            "[dim]Waiting for input…[/dim]\n"
            "[dim]Enter a goal like:[/dim] Build a Flask API with /health endpoint",
            title="Ready",
            border_style="dim",
        )

    def _render(self) -> Layout:
        """Render the full dashboard."""
        layout = self._make_layout()
        layout["header"].update(self._render_header())
        layout["steps"].update(self._render_steps())
        layout["sidebar"].update(self._render_sidebar())
        layout["footer"].update(self._render_footer())
        return layout

    async def run_goal(self, goal: str) -> Dict[str, Any]:
        """Run a goal with the live dashboard."""
        self.current_goal = goal
        self.start_time = time.time()
        self.step_log.clear()
        self.result = None

        # Create agent
        self.agent = AgentLoop(self.config)
        tools = create_default_tools(workspace=self.workspace)
        self.agent.register_tools(tools)
        self._tool_names = list(tools.keys())

        # Wire callbacks
        def on_step(step: Step, state: AgentState):
            self.step_log.append({
                "action": step.action,
                "tool": step.tool_name,
                "success": step.success,
                "duration_ms": step.duration_ms,
                "result": step.result,
            })

        def on_state(state: AgentState):
            self.current_state = state.value

        self.agent.on_step(on_step)
        self.agent.on_state_change(on_state)

        # Run with live display
        with Live(self._render(), console=self.console, refresh_per_second=4, screen=True) as live:
            task = asyncio.create_task(self.agent.run(goal))

            while not task.done():
                live.update(self._render())
                await asyncio.sleep(0.25)

            self.result = await task
            live.update(self._render())
            await asyncio.sleep(1)  # Hold final state briefly

        return self.result

    def run_interactive(self) -> None:
        """Run the interactive TUI loop — prompt for goals repeatedly."""
        self.console.clear()
        self.console.print(Panel(
            "[bold cyan]Welcome to Nexus![/bold cyan]\n\n"
            "Enter a goal to start the agent. Type [bold]quit[/bold] to exit.\n"
            "The agent will plan, execute, and reflect autonomously.",
            title="🚀 Nexus TUI",
            border_style="cyan",
        ))

        # Show tools
        tools = create_default_tools(workspace=self.workspace)
        self._tool_names = list(tools.keys())
        self.console.print(f"\n[dim]Workspace:[/dim] {self.workspace}")
        self.console.print(f"[dim]Tools:[/dim] {', '.join(self._tool_names)}")
        self.console.print(f"[dim]Models:[/dim] {self.config.planning_model} (plan), {self.config.coding_model} (code)\n")

        while True:
            try:
                goal = Prompt.ask("[bold cyan]Goal[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                break

            goal = goal.strip()
            if not goal or goal.lower() in ("quit", "exit", "q"):
                break

            try:
                result = asyncio.run(self.run_goal(goal))
                self.console.print()
                if result.get("success"):
                    self.console.print("[bold green]✅ Goal completed successfully![/bold green]\n")
                else:
                    self.console.print("[bold red]❌ Goal failed.[/bold red]\n")
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted.[/yellow]\n")
            except Exception as e:
                self.console.print(f"\n[red]Error: {e}[/red]\n")

        self.console.print("\n[dim]Goodbye![/dim]")
