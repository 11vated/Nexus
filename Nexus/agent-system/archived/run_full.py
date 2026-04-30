import yaml
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.brain import AdvancedAgent
from workflows.evolve_mcp import create_self_improving_agent
from workflows.swarm import create_swarm, create_parallel_system
from workflows.research import create_researcher
from workflows.benchmark import SWEBenchEvaluator, QualityMetrics


def load_config(config_path="config/agent.yaml"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_dir, config_path)
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Config not found: {config_file}")
    
    with open(config_file) as f:
        return yaml.safe_load(f)


def run_normal(args):
    config = load_config()
    task = " ".join(args)
    
    print(f"[RUN] Task: {task}")
    
    agent = AdvancedAgent(config)
    result = agent.run(task)
    
    print(f"\nResult: {result.get('status')}")
    return result


def run_swarm(args):
    task = " ".join(args)
    print(f"[SWARM] Task: {task}")
    
    swarm = create_swarm()
    result = swarm.dispatch_hierarchical(task)
    
    print(f"\nSwarm Result: {result.get('plan', {}).get('subtasks', [])}")
    return result


def run_research(args):
    query = " ".join(args)
    print(f"[RESEARCH] Query: {query}")
    
    from workflows.research import create_researcher
    researcher = create_researcher()
    result = researcher.research_task(query)
    
    print(f"\nBest Library: {result.get('best_libraries', {}).get('recommended')}")
    return result


def run_evolve(args):
    args_str = " ".join(args)
    print(f"[EVOLVE] Optimizing: {args_str}")
    
    evolver = create_self_improving_agent()
    result = evolver.run_evolution_cycle(
        test_tasks=[{"task": args_str}],
        test_cases=[["compiles", "runs", "tests pass"]]
    )
    
    print(f"\nEvolved Config: {result.get('evolved_config')}")
    return result


def run_benchmark(args):
    model = args[0] if args else "ollama/qwen2.5-coder:14b"
    tasks = int(args[1]) if len(args) > 1 else 5
    
    print(f"[BENCHMARK] Model: {model}, Tasks: {tasks}")
    
    config = {"model": {"name": model}}
    agent = AdvancedAgent(config)
    
    swe = SWEBenchEvaluator(model=model)
    result = swe.evaluate(agent, num_tasks=tasks)
    
    print(f"\nScore: {result.get('score_percent', 0):.1f}%")
    return result


def main():
    import sys
    
    config = load_config()
    
    print("=" * 60)
    print("AUTONOMOUS DEVELOPER AGENT - FULL FEATURE SET")
    print("=" * 60)
    print(f"Model: {config.get('model', {}).get('name', 'N/A')}")
    print("Features:")
    print("  - REACT agent loop")
    print("  - Vector memory (ChromaDB)")
    print("  - Docker sandboxing")
    print("  - TDD workflow")
    print("  - Sequential thinking")
    print("  - Multi-agent swarm")
    print("  - Self-improvement (Evolve-MCP)")
    print("  - Web research")
    print("  - SWE-bench evaluation")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("""
Usage: python run_full.py <command> [args]

Commands:
  run [task]           - Run agent on task
  swarm [task]         - Run multi-agent swarm
  research [query]    - Web research task
  evolve [config]     - Self-improvement cycle
  benchmark [model]   - Run SWE-bench

Examples:
  python run_full.py run "Create Flask app"
  python run_full.py swarm "Build REST API with auth"
  python run_full.py research "best Python async library"
  python run_full.py benchmark "ollama/qwen2.5-coder:14b" 10
""")
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    commands = {
        "run": run_normal,
        "swarm": run_swarm,
        "research": run_research,
        "evolve": run_evolve,
        "benchmark": run_benchmark
    }
    
    if command not in commands:
        print(f"Unknown command: {command}")
        sys.exit(1)
    
    commands[command](args)


if __name__ == "__main__":
    main()