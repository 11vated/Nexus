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
    print("LOCAL AUTONOMOUS AGENT")
    print("=" * 60)
    print(f"Model: {config.get('model', {}).get('name', 'N/A')}")
    print(f"Max iterations: {config.get('loop', {}).get('max_iterations', 'N/A')}")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        print("\nEnter task (or 'quit' to exit):")
        task = input("> ").strip()
    
    if task.lower() in ["quit", "exit", "q"]:
        print("Goodbye!")
        return
    
    if not task:
        print("Error: No task provided")
        sys.exit(1)
    
    agent = AdvancedAgent(config)
    result = agent.run(task)
    
    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()