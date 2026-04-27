import yaml
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from core.brain import AdvancedAgent


def load_config(config_path="config/agent.yaml"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_dir, config_path)
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Config not found: {config_file}")
    
    with open(config_file) as f:
        return yaml.safe_load(f)


def main():
    config = load_config()
    
    print("=" * 60)
    print("AUTONOMOUS DEVElOPER AGENT - ADVANCED")
    print("=" * 60)
    print(f"Model: {config.get('model', {}).get('name', 'N/A')}")
    print(f"Max iterations: {config.get('loop', {}).get('max_iterations', 'N/A')}")
    print(f"Vector memory: {config.get('memory', {}).get('vector_enabled', False)}")
    print(f"Sandbox: {config.get('sandbox', {}).get('enabled', False)}")
    print(f"Sequential thinking: {config.get('thinking', {}).get('enabled', False)}")
    print(f"TDD: {config.get('tdd', {}).get('enabled', False)}")
    print("=" * 60)
    
    use_tdd = "--tdd" in sys.argv
    use_github = "--github" in sys.argv
    
    if len(sys.argv) > 1:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        task = " ".join(args) if args else ""
    else:
        print("\nEnter task (or 'quit' to exit):")
        task = input("> ").strip()
    
    if task.lower() in ["quit", "exit", "q"]:
        print("Goodbye!")
        return
    
    if not task:
        print("Error: No task provided")
        sys.exit(1)
    
    print(f"\n[TASK] {task}")
    if use_tdd:
        print("[MODE] Test-Driven Development")
    if use_github:
        print("[MODE] GitHub Integration")
    
    agent = AdvancedAgent(config)
    
    if use_github:
        repo = input("GitHub repo (owner/repo): ").strip()
        result = agent.run_with_github(task, repo)
    else:
        result = agent.run(task, use_tdd=use_tdd)
    
    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {result.get('status', 'unknown')}")
    print("=" * 60)


if __name__ == "__main__":
    main()