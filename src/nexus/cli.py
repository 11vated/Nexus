"""Nexus CLI - Command line interface for Nexus AI Workstation."""
import sys
import asyncio
import json
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.spinner import Spinner
from rich.columns import Columns
from rich import print as rprint

from nexus.config.settings import config
from nexus.utils.subprocess_utils import run_command, run_ollama
from nexus.security.sanitizer import validate_model_name

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATE_ICONS = {
    "idle": "⏸",
    "planning": "🧠",
    "acting": "⚡",
    "observing": "👁",
    "reflecting": "🔍",
    "correcting": "🔧",
    "done": "✅",
    "error": "❌",
}


def _build_progress_table(steps, current_state, goal, elapsed):
    """Build a Rich table showing agent progress."""
    table = Table(
        title=f"Nexus Agent — {STATE_ICONS.get(current_state, '?')} {current_state.upper()}",
        title_style="bold cyan",
        show_lines=True,
        expand=True,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Action", ratio=3)
    table.add_column("Tool", style="cyan", width=14)
    table.add_column("Status", width=8, justify="center")
    table.add_column("Time", style="dim", width=8)

    for i, s in enumerate(steps, 1):
        icon = "✓" if s["success"] else "✗"
        style = "green" if s["success"] else "red"
        action = s["action"][:60] + ("…" if len(s["action"]) > 60 else "")
        ms = f"{s['duration_ms']:.0f}ms" if s.get("duration_ms") else ""
        table.add_row(str(i), action, s.get("tool", ""), f"[{style}]{icon}[/{style}]", ms)

    # Footer row with stats
    if steps:
        ok = sum(1 for s in steps if s["success"])
        table.add_row(
            "",
            f"[dim]{ok}/{len(steps)} steps succeeded · {elapsed:.0f}s elapsed[/dim]",
            "",
            "",
            "",
        )

    return table


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Nexus - Ultimate AI Agent Workstation."""
    pass


# ---------------------------------------------------------------------------
#  nexus run "goal"  —  the main agent entry point
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("goal")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Workspace directory")
@click.option("--model", "-m", default=None, help="Ollama model for planning (e.g. deepseek-r1:7b)")
@click.option("--coding-model", "-c", default=None, help="Ollama model for coding (e.g. qwen2.5-coder:14b)")
@click.option("--max-iterations", "-n", default=25, help="Max agent loop iterations")
@click.option("--no-reflect", is_flag=True, help="Disable reflection after each step")
@click.option("--verbose", "-v", is_flag=True, help="Show full tool output")
@click.option("--json-output", is_flag=True, help="Output final result as JSON")
def run(goal, workspace, model, coding_model, max_iterations, no_reflect, verbose, json_output):
    """Run the autonomous agent on a goal.

    \b
    Examples:
        nexus run "Build a Flask API with /health endpoint"
        nexus run "Fix the failing tests in tests/" --workspace ./my-project
        nexus run "Refactor utils.py to reduce duplication" -m deepseek-r1:14b
    """
    asyncio.run(_run_agent(
        goal=goal,
        workspace=workspace,
        model=model,
        coding_model=coding_model,
        max_iterations=max_iterations,
        reflection=not no_reflect,
        verbose=verbose,
        json_output=json_output,
    ))


async def _run_agent(
    goal: str,
    workspace: str,
    model: str | None,
    coding_model: str | None,
    max_iterations: int,
    reflection: bool,
    verbose: bool,
    json_output: bool,
):
    """Async implementation of the agent runner."""
    from nexus.agent.loop import AgentLoop
    from nexus.agent.models import AgentConfig, AgentState
    from nexus.tools import create_default_tools

    # Build config
    agent_config = AgentConfig(
        workspace_path=str(Path(workspace).resolve()),
        max_iterations=max_iterations,
        reflection_enabled=reflection,
        ollama_url=config.ollama_url,
    )
    if model:
        agent_config.planning_model = model
        agent_config.review_model = model
    if coding_model:
        agent_config.coding_model = coding_model

    # Create agent
    agent = AgentLoop(agent_config)
    tools = create_default_tools(workspace=str(Path(workspace).resolve()))
    agent.register_tools(tools)

    # Set up live display
    step_log: list[dict] = []
    current_state = "idle"
    start_time = time.time()

    def on_step(step, state):
        step_log.append({
            "action": step.action,
            "tool": step.tool_name,
            "success": step.success,
            "duration_ms": step.duration_ms,
            "result": step.result,
        })

    def on_state(state):
        nonlocal current_state
        current_state = state.value

    agent.on_step(on_step)
    agent.on_state_change(on_state)

    # Banner
    if not json_output:
        console.print()
        console.print(Panel(
            f"[bold cyan]Goal:[/bold cyan] {goal}\n"
            f"[dim]Workspace:[/dim] {Path(workspace).resolve()}\n"
            f"[dim]Planning model:[/dim] {agent_config.planning_model}\n"
            f"[dim]Coding model:[/dim] {agent_config.coding_model}\n"
            f"[dim]Max iterations:[/dim] {max_iterations}",
            title="🚀 Nexus Agent",
            border_style="cyan",
        ))
        console.print()

    # Run with live progress
    if json_output:
        result = await agent.run(goal)
        console.print_json(json.dumps(result, indent=2))
    else:
        with Live(console=console, refresh_per_second=4) as live:
            async def _run_with_display():
                return await agent.run(goal)

            # Start the agent in background
            task = asyncio.create_task(_run_with_display())

            while not task.done():
                elapsed = time.time() - start_time
                if step_log:
                    display = _build_progress_table(step_log, current_state, goal, elapsed)
                else:
                    display = Panel(
                        f"[cyan]{STATE_ICONS.get(current_state, '?')} {current_state.upper()}[/cyan]  "
                        f"[dim]{elapsed:.0f}s[/dim]",
                        title="🚀 Nexus Agent",
                        border_style="cyan",
                    )
                live.update(display)
                await asyncio.sleep(0.25)

            # Final display
            result = await task
            elapsed = time.time() - start_time
            if step_log:
                live.update(_build_progress_table(step_log, result.get("final_state", "done"), goal, elapsed))

        # Summary
        console.print()
        success = result.get("success", False)
        icon = "✅" if success else "❌"
        style = "green" if success else "red"
        console.print(Panel(
            f"[{style} bold]{icon} {'SUCCESS' if success else 'FAILED'}[/{style} bold]\n\n"
            f"Steps: {result.get('steps_successful', 0)}/{result.get('steps_total', 0)} succeeded\n"
            f"Iterations: {result.get('iterations', 0)}\n"
            f"Duration: {result.get('duration_seconds', 0)}s",
            title="Result",
            border_style=style,
        ))

        # Verbose: show full step details
        if verbose and step_log:
            console.print("\n[bold]Step Details:[/bold]")
            for i, s in enumerate(step_log, 1):
                icon = "✓" if s["success"] else "✗"
                style = "green" if s["success"] else "red"
                console.print(f"\n[{style}]{icon} Step {i}: {s['action']}[/{style}]")
                console.print(f"  Tool: {s['tool']}")
                if s.get("result"):
                    result_text = s["result"][:500]
                    console.print(f"  Result: {result_text}")


@cli.group()
def model():
    """Model management commands."""
    pass


@model.command("list")
def model_list():
    """List available Ollama models."""
    try:
        result = run_ollama("list")
        console.print(result)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", err=True)
        sys.exit(1)


@model.command("run")
@click.argument("prompt")
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--timeout", "-t", default=120, help="Timeout in seconds")
def model_run(prompt, model, timeout):
    """Run a prompt with a model."""
    if model:
        try:
            model = validate_model_name(model)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}", err=True)
            sys.exit(1)
    else:
        model = config.default_model
    
    console.print(f"[cyan]Using model:[/cyan] {model}")
    
    try:
        result = run_ollama("run", model=model, prompt=prompt, timeout=timeout)
        console.print(result)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", err=True)
        sys.exit(1)


@model.command("pull")
@click.argument("model")
def model_pull(model):
    """Pull a model from Ollama."""
    try:
        model = validate_model_name(model)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}", err=True)
        sys.exit(1)
    
    console.print(f"[cyan]Pulling model:[/cyan] {model}")
    
    try:
        result = run_ollama("pull", model=model)
        console.print(result)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", err=True)
        sys.exit(1)


@cli.group()
def tool():
    """Tool management commands."""
    pass


@tool.command("list")
def tool_list():
    """List available tools and their status."""
    table = Table(title="Nexus Tools")
    
    table.add_column("Tool", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Status", style="green")
    
    tools = [
        ("opencode", "AI-native IDE with MCP support", "Available" if config.opencode_path else "Not found"),
        ("aider", "Terminal-first AI pair programmer", "Available" if config.aider_path else "Not found"),
        ("goose", "Autonomous CLI agent", "Available" if config.goose_path else "Not found"),
        ("ollama", "Local LLM runtime", "Running" if _check_ollama() else "Not running"),
    ]
    
    for name, desc, status in tools:
        table.add_row(name, desc, status)
    
    console.print(table)


def _check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        run_ollama("list", timeout=5)
        return True
    except Exception:
        return False


@tool.command("status")
def tool_status():
    """Show detailed status of all tools."""
    console.print("[bold]Nexus Status[/bold]\n")
    
    # Workspace
    console.print(f"[cyan]Workspace:[/cyan] {config.workspace_root}")
    console.print(f"[cyan]Logs:[/cyan] {config.logs_dir}\n")
    
    # Ollama
    ollama_running = _check_ollama()
    status = "[green]Running[/green]" if ollama_running else "[red]Not running[/red]"
    console.print(f"[cyan]Ollama:[/cyan] {status}")
    console.print(f"[cyan]URL:[/cyan] {config.ollama_url}\n")
    
    # Default model
    console.print(f"[cyan]Default Model:[/cyan] {config.default_model}")
    console.print(f"[cyan]Timeout:[/cyan] {config.model_timeout_seconds}s\n")
    
    # Models
    if ollama_running:
        try:
            result = run_ollama("list")
            console.print("[cyan]Available Models:[/cyan]")
            console.print(result)
        except Exception as e:
            console.print(f"[red]Error listing models:[/red] {e}")


@cli.group()
def workspace():
    """Workspace management commands."""
    pass


@workspace.command("init")
@click.option("--path", "-p", default=None, help="Workspace path")
def workspace_init(path):
    """Initialize a workspace."""
    workspace_path = Path(path) if path else config.workspace_root
    
    if workspace_path.exists():
        console.print(f"[yellow]Workspace already exists:[/yellow] {workspace_path}")
        return
    
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # Create basic structure
    (workspace_path / "src").mkdir()
    (workspace_path / "tests").mkdir()
    (workspace_path / "docs").mkdir()
    
    console.print(f"[green]Initialized workspace:[/green] {workspace_path}")


@workspace.command("clean")
@click.confirmation_option(prompt="Clean workspace? This will remove all generated files.")
def workspace_clean():
    """Clean workspace files."""
    import shutil
    
    workspace_path = config.workspace_root
    
    if not workspace_path.exists():
        console.print("[yellow]Workspace does not exist[/yellow]")
        return
    
    # Keep directory structure
    for item in workspace_path.iterdir():
        if item.name in ("src", "tests", "docs"):
            shutil.rmtree(item)
            item.mkdir()
    
    console.print("[green]Workspace cleaned[/green]")


@cli.group()
def config_cmd():
    """Configuration management commands."""
    pass


@config_cmd.command("show")
def config_show():
    """Show current configuration."""
    table = Table(title="Nexus Configuration")
    
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    
    settings = [
        ("workspace_root", str(config.workspace_root)),
        ("ollama_url", config.ollama_url),
        ("default_model", config.default_model),
        ("model_timeout", f"{config.model_timeout_seconds}s"),
        ("log_level", config.log_level),
        ("max_concurrent_tools", str(config.max_concurrent_tools)),
    ]
    
    for name, value in settings:
        table.add_row(name, value)
    
    console.print(table)


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a configuration value."""
    console.print(f"[yellow]Configuration changes require .env file editing[/yellow]")
    console.print(f"To set {key}={value}, add to .env file:")


@cli.command()
@click.argument("issue_file", type=click.Path(exists=True))
@click.option("--repo", "-r", type=click.Path(exists=True), help="Repository path")
@click.option("--test-cmd", "-t", default="pytest", help="Test command")
@click.option("--model", "-m", default="qwen2.5-coder:14b", help="Model to use")
@click.option("--patches", "-p", default=8, help="Number of patches to generate")
@click.option("--gateway", "-g", default="http://localhost:4000", help="Gateway URL")
def swebench(issue_file, repo, test_cmd, model, patches, gateway):
    """Run SWE-bench resolution on an issue."""
    asyncio.run(_swebench_async(issue_file, repo, test_cmd, model, patches, gateway))


async def _swebench_async(issue_file, repo, test_cmd, model, num_patches, gateway_url):
    """Async SWE-bench runner."""
    from nexus.swe_bench.orchestrator import SWEBenchOrchestrator
    from nexus.gateway.client import GatewayClient

    issue_text = Path(issue_file).read_text()
    repo_path = Path(repo) if repo else Path.cwd()

    console.print(f"[cyan]Running SWE-bench with {num_patches} patches...[/cyan]")

    async with GatewayClient(base_url=gateway_url) as gateway:
        orch = SWEBenchOrchestrator(
            gateway_client=gateway,
            model_name=model,
            workspace=repo_path.parent,
            num_patches=num_patches
        )

        result = await orch.resolve_issue(issue_text, repo_path, test_cmd)

        console.print(f"\n[bold]Results:[/bold]")
        console.print(f"Patches tested: {result.candidates_tested}")
        console.print(f"Best score: {result.best_score:.2f}")
        console.print(f"Passed: {'[green]Yes[/green]' if result.passed else '[red]No[/red]'}")

        if result.best_patch:
            console.print(f"\n[bold green]Best Patch:[/bold green]\n{result.best_patch[:500]}")


# ---------------------------------------------------------------------------
#  nexus agent — agent inspection / diagnostics
# ---------------------------------------------------------------------------

@cli.group()
def agent():
    """Agent configuration and diagnostics."""
    pass


@agent.command("tools")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Workspace directory")
def agent_tools(workspace):
    """List all tools the agent can use."""
    from nexus.tools import create_default_tools

    tools = create_default_tools(workspace=str(Path(workspace).resolve()))
    table = Table(title="Agent Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Aliases", style="dim")

    for name, tool in sorted(tools.items()):
        desc = getattr(tool, "description", "—")
        aliases = ", ".join(getattr(tool, "aliases", []) or [])
        table.add_row(name, desc, aliases or "—")

    console.print(table)


@agent.command("config")
@click.option("--model", "-m", default=None, help="Override planning model")
def agent_config(model):
    """Show the agent's runtime configuration."""
    from nexus.agent.models import AgentConfig

    cfg = AgentConfig()
    if model:
        cfg.planning_model = model

    table = Table(title="Agent Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    for field_name in [
        "planning_model",
        "coding_model",
        "review_model",
        "fast_model",
        "max_iterations",
        "max_retries",
        "quality_threshold",
        "llm_timeout",
        "tool_timeout",
        "ollama_url",
        "temperature",
        "max_tokens",
        "workspace_path",
        "reflection_enabled",
        "memory_enabled",
        "sandbox_enabled",
    ]:
        table.add_row(field_name, str(getattr(cfg, field_name, "—")))

    console.print(table)


@agent.command("check")
def agent_check():
    """Pre-flight check: verify Ollama is reachable and a model is available."""
    from nexus.agent.models import AgentConfig

    cfg = AgentConfig()
    console.print(f"[cyan]Checking Ollama at[/cyan] {cfg.ollama_url} …")

    import urllib.request
    try:
        req = urllib.request.Request(f"{cfg.ollama_url}/api/tags")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        if models:
            console.print(f"[green]✓ Ollama reachable — {len(models)} models available:[/green]")
            for m in models:
                tag = " ← planning" if m == cfg.planning_model else ""
                tag += " ← coding" if m == cfg.coding_model else ""
                console.print(f"  • {m}{tag}")
        else:
            console.print("[yellow]⚠ Ollama is running but no models pulled. Run:[/yellow]")
            console.print(f"  ollama pull {cfg.planning_model}")
    except Exception as e:
        console.print(f"[red]✗ Cannot reach Ollama:[/red] {e}")
        console.print("  Make sure Ollama is running:  ollama serve")


# ---------------------------------------------------------------------------
#  nexus tui — interactive dashboard
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Workspace directory")
@click.option("--model", "-m", default=None, help="Override planning model")
@click.option("--coding-model", "-c", default=None, help="Override coding model")
def tui(workspace, model, coding_model):
    """Launch the interactive TUI dashboard.

    \b
    Full-screen Rich dashboard that shows agent state, steps, tools,
    memory, and config. Enter goals interactively.

    \b
    Example:
        nexus tui
        nexus tui --workspace ./my-project
    """
    from nexus.tui.dashboard import NexusDashboard
    from nexus.agent.models import AgentConfig

    agent_config = AgentConfig(
        workspace_path=str(Path(workspace).resolve()),
        ollama_url=config.ollama_url,
    )
    if model:
        agent_config.planning_model = model
        agent_config.review_model = model
    if coding_model:
        agent_config.coding_model = coding_model

    dashboard = NexusDashboard(workspace=workspace, config=agent_config)
    dashboard.run_interactive()


# ---------------------------------------------------------------------------
#  nexus mcp — Model Context Protocol server
# ---------------------------------------------------------------------------

@cli.group()
def mcp():
    """MCP server — expose Nexus tools to external clients."""
    pass


@mcp.command("serve")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Workspace directory")
@click.option("--transport", "-t", type=click.Choice(["stdio", "http"]), default="stdio", help="Transport mode")
@click.option("--port", "-p", default=3100, help="HTTP port (only for http transport)")
def mcp_serve(workspace, transport, port):
    """Start the MCP server.

    \b
    stdio mode (default): for Claude Desktop, Cursor, etc.
    http mode: for network clients at http://localhost:3100

    \b
    Claude Desktop config (~/.config/claude/claude_desktop_config.json):
    {
        "mcpServers": {
            "nexus": {
                "command": "nexus",
                "args": ["mcp", "serve", "-w", "/path/to/project"]
            }
        }
    }
    """
    from nexus.mcp.server import NexusMCPServer

    server = NexusMCPServer(workspace=workspace)

    if transport == "stdio":
        asyncio.run(server.serve_stdio())
    else:
        asyncio.run(server.serve_http(port=port))


@mcp.command("tools")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Workspace directory")
def mcp_tools(workspace):
    """List tools that the MCP server exposes."""
    from nexus.mcp.server import NexusMCPServer

    server = NexusMCPServer(workspace=workspace)
    table = Table(title="MCP Tools (exposed to clients)")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Parameters", style="dim")

    seen = set()
    for name, tool in server.tools.items():
        if id(tool) in seen:
            continue
        seen.add(id(tool))
        params = ", ".join(tool.schema.keys()) if tool.schema else "—"
        table.add_row(tool.name, tool.description, params)

    console.print(table)


# ---------------------------------------------------------------------------
#  nexus bench — SWE-bench style issue resolution
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("issue")
@click.option("--repo", "-r", type=click.Path(exists=True), default=".", help="Repository path")
@click.option("--model", "-m", default=None, help="Override model")
@click.option("--patches", "-n", default=8, help="Number of patch candidates to generate")
@click.option("--test-cmd", default="pytest", help="Test command to verify patches")
def bench(issue, repo, model, patches, test_cmd):
    """Run SWE-bench style issue resolution.

    \b
    Generates multiple patch candidates for an issue, tests each one,
    and selects the best passing patch.

    \b
    Example:
        nexus bench "Fix the TypeError in utils.py line 42"
        nexus bench "Add pagination to the /users endpoint" --patches 12
    """
    asyncio.run(_run_bench(issue, repo, model, patches, test_cmd))


async def _run_bench(issue: str, repo: str, model: str | None, num_patches: int, test_cmd: str):
    """Async implementation of SWE-bench runner."""
    from nexus.gateway.client import GatewayClient
    from nexus.swe_bench.orchestrator import SWEBenchOrchestrator, ResolutionStatus

    model_name = model or config.default_model

    console.print(Panel(
        f"[bold cyan]Issue:[/bold cyan] {issue}\n"
        f"[dim]Repo:[/dim] {Path(repo).resolve()}\n"
        f"[dim]Model:[/dim] {model_name}\n"
        f"[dim]Patches:[/dim] {num_patches}\n"
        f"[dim]Test cmd:[/dim] {test_cmd}",
        title="🧪 SWE-bench Runner",
        border_style="cyan",
    ))

    gateway = GatewayClient(config.ollama_url)
    orchestrator = SWEBenchOrchestrator(
        gateway_client=gateway,
        model_name=model_name,
        num_patches=num_patches,
    )

    with console.status("[cyan]Generating and testing patches…[/cyan]"):
        result = await orchestrator.resolve_issue(
            issue_text=issue,
            repo_path=Path(repo).resolve(),
            test_command=test_cmd,
        )

    # Display results
    status_styles = {
        ResolutionStatus.PASSED: ("✅ PASSED", "green"),
        ResolutionStatus.PARTIAL: ("⚠️  PARTIAL", "yellow"),
        ResolutionStatus.FAILED: ("❌ FAILED", "red"),
        ResolutionStatus.PENDING: ("⏳ PENDING", "dim"),
    }
    label, style = status_styles.get(result.status, ("?", "dim"))

    console.print(Panel(
        f"[{style} bold]{label}[/{style} bold]\n\n"
        f"Candidates tested: {result.candidates_tested}\n"
        f"Passed: {result.passed_count}/{result.total_candidates}\n"
        f"Best score: {result.best_score:.2f}",
        title="Result",
        border_style=style,
    ))

    if result.best_patch:
        console.print("\n[bold]Best Patch:[/bold]")
        console.print(result.best_patch)


# ---------------------------------------------------------------------------
#  nexus quickstart — one-command setup
# ---------------------------------------------------------------------------

@cli.command()
def quickstart():
    """Interactive first-run setup — check Ollama, pull models, init workspace."""
    from nexus.agent.models import AgentConfig

    cfg = AgentConfig()
    console.print(Panel(
        "[bold cyan]Welcome to Nexus![/bold cyan]\n\n"
        "Let's make sure everything is set up.",
        title="🚀 Quickstart",
        border_style="cyan",
    ))

    # 1. Check Ollama
    console.print("\n[bold]1. Checking Ollama…[/bold]")
    import urllib.request
    ollama_ok = False
    try:
        req = urllib.request.Request(f"{cfg.ollama_url}/api/tags")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        console.print(f"   [green]✓ Ollama is running ({len(models)} models)[/green]")
        ollama_ok = True
    except Exception:
        console.print("   [red]✗ Ollama not reachable[/red]")
        console.print(f"   Start it with: [cyan]ollama serve[/cyan]")

    # 2. Check required models
    if ollama_ok:
        console.print("\n[bold]2. Checking models…[/bold]")
        needed = {cfg.planning_model, cfg.coding_model}
        for m in needed:
            found = any(m in avail for avail in models) if models else False
            if found:
                console.print(f"   [green]✓ {m}[/green]")
            else:
                console.print(f"   [yellow]⚠ {m} not found — pull with:[/yellow] ollama pull {m}")

    # 3. Workspace
    console.print("\n[bold]3. Workspace…[/bold]")
    ws = Path(cfg.workspace_path).resolve()
    console.print(f"   Path: {ws}")
    console.print(f"   Exists: {'[green]yes[/green]' if ws.exists() else '[yellow]no (will be created)[/yellow]'}")

    console.print("\n[bold green]Ready![/bold green] Run your first task:")
    console.print('  [cyan]nexus run "Build a hello-world Flask app"[/cyan]\n')


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()