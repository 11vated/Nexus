import yaml
import os
import sys

AGENT_MODES = {
    "basic": "Simple 1-agent loop",
    "mini-swe": "Mini-SWE-agent pattern (74% SWE-bench)",
    "multi": "Manager→Planner→Programmer→Reviewer"
}


def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_dir, "config", "agent.yaml")
    if os.path.exists(config_file):
        with open(config_file) as f:
            return yaml.safe_load(f)
    return {}


def run_basic(args):
    from core.brain import AdvancedAgent
    config = load_config()
    task = " ".join(args)
    agent = AdvancedAgent(config)
    result = agent.run(task)
    print(f"\nResult: {result.get('status')}")
    return result


def run_mini_swe(args):
    from core.mini_swe_agent import run_mini_swe
    task = " ".join(args)
    result = run_mini_swe(task)
    print(f"\nResult: {result.get('status')}")
    return result


def run_multi(args):
    from core.multi_agent import run_full_orchestrator
    task = " ".join(args)
    result = run_full_orchestrator(task)
    print(f"\nStatus: {result.get('status')}")
    return result


def main():
    if len(sys.argv) < 2:
        print("""
AUTONOMOUS AGENT - Multiple Architectures

Usage: python run_agent.py <mode> [task]

Modes:
  basic      - Simple REACT loop (default)
  mini-swe   - Mini-SWE-agent pattern (same as 74% SWE-bench)
  multi     - Manager→Planner→Programmer→Reviewer

Examples:
  python run_agent.py basic "create flask app"
  python run_agent.py mini-swe "fix bug in app.py"
  python run_agent.py multi "build rest api"
""")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    args = sys.argv[2:]
    
    if not args:
        args = ["hello world"]
    
    if mode == "basic":
        return run_basic(args)
    elif mode == "mini-swe":
        return run_mini_swe(args)
    elif mode == "multi":
        return run_multi(args)
    else:
        print(f"Unknown mode: {mode}")
        print(f"Available: {list(AGENT_MODES.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()