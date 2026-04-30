"""UI outcome verification - verifies rendered UI fits terminal."""
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from io import StringIO
import json


@dataclass
class UIIssue:
    """Issue found in UI verification."""
    issue_type: str  # overflow, missing_element, alignment, truncation
    line: Optional[int] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    element: Optional[str] = None
    severity: str = "error"


@dataclass
class UIVerificationResult:
    """Result of UI verification."""
    passed: bool
    issues: List[UIIssue]
    terminal_size: Tuple[int, int]
    render_time_ms: float = 0


class UIOutcomeVerifier:
    """Verify UI renders correctly in terminal."""
    
    def __init__(self, terminal_width: int = 80, terminal_height: int = 24):
        self.terminal_width = terminal_width
        self.terminal_height = terminal_height
        self.console = Console(
            width=terminal_width,
            height=terminal_height,
            force_terminal=True,
            no_color=False
        )
    
    def verify_layout(self, layout_elements: Dict[str, Any]) -> UIVerificationResult:
        """Verify layout fits in terminal."""
        import time
        start = time.time()
        
        issues = []
        
        # Check total width doesn't exceed terminal
        total_width = 0
        for name, element in layout_elements.items():
            width = element.get("width", 0)
            padding = element.get("padding", 0)
            total_width += width + padding
        
        if total_width > self.terminal_width:
            issues.append(UIIssue(
                issue_type="overflow",
                expected=f"max {self.terminal_width}",
                actual=str(total_width),
                severity="error"
            ))
        
        # Check for missing required elements
        required = ["header", "main_content", "footer"]
        for req in required:
            if req not in layout_elements:
                issues.append(UIIssue(
                    issue_type="missing_element",
                    element=req,
                    severity="error"
                ))
        
        render_time = (time.time() - start) * 1000
        
        return UIVerificationResult(
            passed=len([i for i in issues if i.severity == "error"]) == 0,
            issues=issues,
            terminal_size=(self.terminal_width, self.terminal_height),
            render_time_ms=render_time
        )
    
    def verify_panel(self, content: str, panel_title: str = None) -> UIVerificationResult:
        """Verify a panel renders correctly."""
        issues = []
        
        # Check content lines don't overflow
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            if len(line) > self.terminal_width - 2:  # Account for panel borders
                issues.append(UIIssue(
                    issue_type="overflow",
                    line=i,
                    expected=str(self.terminal_width - 2),
                    actual=str(len(line)),
                    severity="warning"
                ))
        
        return UIVerificationResult(
            passed=len(issues) == 0,
            issues=issues,
            terminal_size=(self.terminal_width, self.terminal_height)
        )
    
    def export_ascii(self, content: str) -> str:
        """Export rendered content as ASCII for agent to see."""
        with self.console.capture() as capture:
            self.console.print(content)
        
        return capture.get()
    
    def render_to_text(self, elements: Dict[str, Any]) -> str:
        """Render layout elements to plain text."""
        output = []
        
        # Header
        if "header" in elements:
            header = elements["header"]
            output.append(self._center_text(header.get("title", "Header"), "="))
        
        # Agent pane
        if "agents" in elements:
            agents = elements["agents"]
            output.append("\n[Agents]")
            for name, status in agents.items():
                output.append(f"  {name}: {status}")
        
        # Logs
        if "logs" in elements:
            logs = elements["logs"][-10:]  # Last 10 lines
            output.append("\n[Logs]")
            for log in logs:
                output.append(f"  {log}")
        
        # Models
        if "models" in elements:
            models = elements["models"]
            output.append("\n[Models]")
            for name, status in models.items():
                output.append(f"  {name}: {status}")
        
        # Footer
        if "footer" in elements:
            footer = elements["footer"]
            output.append("\n" + self._center_text(footer.get("text", ""), "-"))
        
        return "\n".join(output)
    
    def _center_text(self, text: str, char: str = "-") -> str:
        """Center text with fill character."""
        width = self.terminal_width
        if len(text) >= width:
            return text
        
        padding = (width - len(text)) // 2
        return char * padding + text + char * (width - len(text) - padding)
    
    def check_element_alignment(self, elements: List[Dict]) -> List[UIIssue]:
        """Check if elements are properly aligned."""
        issues = []
        
        # Find left edge of all elements
        left_edges = {}
        for elem in elements:
            name = elem.get("name", "unknown")
            x = elem.get("x", 0)
            left_edges[name] = x
        
        # Check if any elements overlap
        positions = sorted(left_edges.items(), key=lambda x: x[1])
        
        for i in range(len(positions) - 1):
            current = positions[i]
            next_elem = positions[i + 1]
            
            # This is simplified - real implementation would check widths
            if next_elem[1] <= current[1] + 20:  # Assuming max width of 20
                issues.append(UIIssue(
                    issue_type="alignment",
                    element=next_elem[0],
                    expected=f"x > {current[1] + 20}",
                    actual=f"x = {next_elem[1]}",
                    severity="warning"
                ))
        
        return issues
    
    def generate_report(self, result: UIVerificationResult) -> Dict:
        """Generate JSON report of verification."""
        report = {
            "pass": result.passed,
            "terminal_size": {
                "width": result.terminal_size[0],
                "height": result.terminal_size[1]
            },
            "render_time_ms": result.render_time_ms,
            "issues": []
        }
        
        for issue in result.issues:
            issue_dict = {"type": issue.issue_type, "severity": issue.severity}
            if issue.line:
                issue_dict["line"] = issue.line
            if issue.expected:
                issue_dict["expected"] = issue.expected
            if issue.actual:
                issue_dict["actual"] = issue.actual
            if issue.element:
                issue_dict["element"] = issue.element
            report["issues"].append(issue_dict)
        
        return report
    
    def print_report(self, result: UIVerificationResult):
        """Print human-readable report."""
        print("\n" + "=" * 50)
        print("UI Verification Report")
        print("=" * 50)
        
        status = "✓ PASSED" if result.passed else "✗ FAILED"
        print(f"Status: {status}")
        print(f"Terminal: {result.terminal_size[0]}x{result.terminal_size[1]}")
        print(f"Render time: {result.render_time_ms:.1f}ms")
        
        if result.issues:
            print(f"\nIssues ({len(result.issues)}):")
            for issue in result.issues:
                print(f"  - [{issue.severity}] {issue.issue_type}", end="")
                if issue.element:
                    print(f" - {issue.element}", end="")
                print()
                if issue.expected and issue.actual:
                    print(f"    Expected: {issue.expected}")
                    print(f"    Actual: {issue.actual}")
        
        print("=" * 50 + "\n")


# CLI tool for outcome verification
def main():
    """CLI for UI verification."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify UI layout")
    parser.add_argument("--width", type=int, default=80, help="Terminal width")
    parser.add_argument("--height", type=int, default=24, help="Terminal height")
    parser.add_argument("--check", type=str, help="Check specific element")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    
    args = parser.parse_args()
    
    verifier = UIOutcomeVerifier(args.width, args.height)
    
    # Example verification
    test_elements = {
        "header": {"title": "Nexus AI Workstation"},
        "agents": {"Sprint": "idle", "Architect": "active"},
        "logs": ["[INFO] System started", "[INFO] Models loaded"],
        "models": {"qwen": "ready", "deepseek": "ready"},
        "footer": {"text": "Commands: help | quit"}
    }
    
    result = verifier.verify_layout(test_elements)
    
    if args.format == "json":
        report = verifier.generate_report(result)
        print(json.dumps(report, indent=2))
    else:
        verifier.print_report(result)


if __name__ == "__main__":
    main()