"""Nexus CLI - Command line interface for Nexus AI Workstation."""
import sys
import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from nexus.config.settings import config
from nexus.utils.subprocess_utils import run_command, run_ollama
from nexus.security.sanitizer import validate_model_name

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Nexus - Ultimate AI Agent Workstation."""
    pass


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


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()