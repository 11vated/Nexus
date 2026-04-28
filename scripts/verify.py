"""
Final verification checklist for Nexus.
Run this to verify the system meets production standards.
"""

import sys
import subprocess
import importlib
from pathlib import Path
from typing import List, Dict


class VerificationResult:
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message


def check_python_version() -> VerificationResult:
    """Check Python version is 3.10+."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        return VerificationResult("Python version", True, f"Python {version.major}.{version.minor}")
    return VerificationResult("Python version", False, f"Python {version.major}.{version.minor} (need 3.10+)")


def check_dependencies() -> VerificationResult:
    """Check required dependencies are installed."""
    required = ["pydantic", "rich", "click", "pytest"]
    missing = []
    
    for dep in required:
        try:
            importlib.import_module(dep)
        except ImportError:
            missing.append(dep)
    
    if not missing:
        return VerificationResult("Dependencies", True, "All required packages installed")
    return VerificationResult("Dependencies", False, f"Missing: {', '.join(missing)}")


def check_security_mod() -> VerificationResult:
    """Check security module imports."""
    try:
        from nexus.security import validate_model_name, safe_path_join
        return VerificationResult("Security module", True, "Security utilities available")
    except ImportError as e:
        return VerificationResult("Security module", False, str(e))


def check_config_mod() -> VerificationResult:
    """Check config module."""
    try:
        from nexus.config import config
        return VerificationResult("Config module", True, "Config loaded")
    except ImportError as e:
        return VerificationResult("Config module", False, str(e))


def check_utils_mod() -> VerificationResult:
    """Check utils module."""
    try:
        from nexus.utils import Cache, AsyncUtils, Metrics
        return VerificationResult("Utils module", True, "Utilities available")
    except ImportError as e:
        return VerificationResult("Utils module", False, str(e))


def check_api_mod() -> VerificationResult:
    """Check API module."""
    try:
        from nexus.api import health_checker
        return VerificationResult("API module", True, "Health checker available")
    except ImportError as e:
        return VerificationResult("API module", False, str(e))


def check_shell_true_issues() -> VerificationResult:
    """Check for remaining shell=True issues."""
    issues = []
    agent_system = Path("agent-system")
    
    if agent_system.exists():
        for py_file in agent_system.rglob("*.py"):
            try:
                content = py_file.read_text()
                if "shell=True" in content and "secure" not in content:
                    rel_path = py_file.relative_to(Path.cwd())
                    issues.append(str(rel_path))
            except Exception:
                pass
    
    if not issues:
        return VerificationResult("Security - shell=True", True, "No unsafe shell=True found")
    return VerificationResult("Security - shell=True", False, f"Found in: {', '.join(issues[:3])}")


def check_gitignore() -> VerificationResult:
    """Check .gitignore has proper entries."""
    gitignore_path = Path(".gitignore")
    
    if not gitignore_path.exists():
        return VerificationResult(".gitignore", False, "File not found")
    
    content = gitignore_path.read_text()
    required = [".env", "__pycache__", "*.pyc"]
    
    missing = [item for item in required if item not in content]
    
    if not missing:
        return VerificationResult(".gitignore", True, "Properly configured")
    return VerificationResult(".gitignore", False, f"Missing: {', '.join(missing)}")


def check_dockerfile() -> VerificationResult:
    """Check Dockerfile exists."""
    if Path("Dockerfile").exists():
        return VerificationResult("Dockerfile", True, "Found")
    return VerificationResult("Dockerfile", False, "Not found")


def check_docker_compose() -> VerificationResult:
    """Check docker-compose.yml exists."""
    if Path("docker-compose.yml").exists():
        return VerificationResult("docker-compose", True, "Found")
    return VerificationResult("docker-compose", False, "Not found")


def check_ci_config() -> VerificationResult:
    """Check CI workflow exists."""
    ci_path = Path(".github/workflows/ci.yml")
    if ci_path.exists():
        return VerificationResult("CI config", True, "Found")
    return VerificationResult("CI config", False, "Not found")


def run_all_checks() -> Dict[str, VerificationResult]:
    """Run all verification checks."""
    checks = [
        check_python_version,
        check_dependencies,
        check_security_mod,
        check_config_mod,
        check_utils_mod,
        check_api_mod,
        check_shell_true_issues,
        check_gitignore,
        check_dockerfile,
        check_docker_compose,
        check_ci_config,
    ]
    
    results = {}
    for check in checks:
        try:
            results[check.__name__] = check()
        except Exception as e:
            results[check.__name__] = VerificationResult(check.__name__, False, str(e))
    
    return results


def print_results(results: Dict[str, VerificationResult]):
    """Print verification results."""
    print("\n" + "=" * 60)
    print("Nexus Production Readiness Verification")
    print("=" * 60 + "\n")
    
    passed = 0
    failed = 0
    
    for name, result in results.items():
        status = "✓" if result.passed else "✗"
        print(f"{status} {result.name}: {result.message}")
        
        if result.passed:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-" * 60)
    print(f"Total: {passed + failed} | Passed: {passed} | Failed: {failed}")
    print("-" * 60)
    
    if failed == 0:
        print("\n✓ All checks passed! System is production-ready.")
    else:
        print("\n✗ Some checks failed. Please address the issues above.")
    
    return failed == 0


if __name__ == "__main__":
    results = run_all_checks()
    success = print_results(results)
    sys.exit(0 if success else 1)