"""Design-Aware Verification — verifying beyond functional correctness.

Traditional verification asks "does it work?" Design-aware verification
also asks "does it fit?" — checking that code changes respect existing
architectural constraints, patterns, and design principles.

This module provides:
- DesignConstraint: Declarative rules (naming conventions, dependency
  restrictions, pattern requirements, complexity limits)
- DesignVerifier: Runs constraints against code changes and produces
  structured VerificationReport with pass/warn/fail outcomes
- Built-in constraint library for common patterns
- Custom constraint support via callable predicates
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import re
import time


class ConstraintSeverity(Enum):
    """How critical a constraint violation is."""
    INFO = "info"           # Informational only
    WARNING = "warning"     # Should be addressed, not blocking
    ERROR = "error"         # Must be fixed before merge
    CRITICAL = "critical"   # Architectural violation, requires discussion


class ConstraintCategory(Enum):
    """What aspect of design the constraint covers."""
    NAMING = "naming"               # Naming conventions
    DEPENDENCY = "dependency"       # Import/dependency rules
    PATTERN = "pattern"             # Design pattern compliance
    COMPLEXITY = "complexity"       # Complexity thresholds
    LAYERING = "layering"           # Architecture layer violations
    TESTING = "testing"             # Test coverage/quality requirements
    DOCUMENTATION = "documentation" # Docstring/comment requirements
    SECURITY = "security"           # Security-sensitive patterns
    PERFORMANCE = "performance"     # Performance-related constraints
    CUSTOM = "custom"               # User-defined


class VerificationResult(Enum):
    """Outcome of a single constraint check."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"       # Constraint not applicable to this change


@dataclass
class ConstraintViolation:
    """A specific violation found during verification."""
    constraint_id: str = ""
    message: str = ""
    file_path: str = ""
    line_number: int = 0
    severity: ConstraintSeverity = ConstraintSeverity.WARNING
    suggestion: str = ""    # How to fix it
    context: str = ""       # Surrounding code/context

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
            "context": self.context,
        }


@dataclass
class DesignConstraint:
    """A design rule that code must satisfy.

    Constraints can be:
    - Pattern-based: regex checks on file content
    - Predicate-based: callable that receives file content + metadata
    - Dependency-based: import/dependency restrictions
    """
    id: str = ""
    name: str = ""
    description: str = ""
    category: ConstraintCategory = ConstraintCategory.CUSTOM
    severity: ConstraintSeverity = ConstraintSeverity.WARNING
    # Pattern matching
    file_glob: str = "*.py"             # Which files to check
    pattern: Optional[str] = None       # Regex to search for (violation if found)
    anti_pattern: Optional[str] = None  # Regex that MUST be present
    # Predicate
    predicate: Optional[Callable] = None  # callable(content, metadata) -> bool
    # Metadata
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    suggestion: str = ""                # Default fix suggestion

    def check(self, content: str, file_path: str = "",
              metadata: Optional[Dict[str, Any]] = None) -> List[ConstraintViolation]:
        """Run this constraint against file content."""
        if not self.enabled:
            return []

        violations = []
        meta = metadata or {}

        # Check if file matches glob
        if self.file_glob and not _glob_match(file_path, self.file_glob):
            return []

        # Pattern check: violation if pattern IS found
        if self.pattern:
            for match in re.finditer(self.pattern, content, re.MULTILINE):
                line_num = content[:match.start()].count('\n') + 1
                violations.append(ConstraintViolation(
                    constraint_id=self.id,
                    message=f"{self.name}: forbidden pattern found",
                    file_path=file_path,
                    line_number=line_num,
                    severity=self.severity,
                    suggestion=self.suggestion,
                    context=_extract_context(content, line_num),
                ))

        # Anti-pattern check: violation if pattern NOT found
        if self.anti_pattern and not re.search(self.anti_pattern, content):
            violations.append(ConstraintViolation(
                constraint_id=self.id,
                message=f"{self.name}: required pattern not found",
                file_path=file_path,
                severity=self.severity,
                suggestion=self.suggestion,
            ))

        # Predicate check
        if self.predicate:
            try:
                ok = self.predicate(content, meta)
                if not ok:
                    violations.append(ConstraintViolation(
                        constraint_id=self.id,
                        message=f"{self.name}: predicate check failed",
                        file_path=file_path,
                        severity=self.severity,
                        suggestion=self.suggestion,
                    ))
            except Exception as e:
                violations.append(ConstraintViolation(
                    constraint_id=self.id,
                    message=f"{self.name}: predicate error: {e}",
                    file_path=file_path,
                    severity=ConstraintSeverity.INFO,
                ))

        return violations


@dataclass
class VerificationReport:
    """Structured report from a verification run."""
    timestamp: float = field(default_factory=time.time)
    files_checked: int = 0
    constraints_run: int = 0
    violations: List[ConstraintViolation] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def passed(self) -> bool:
        """True if no ERROR or CRITICAL violations."""
        return not any(
            v.severity in (ConstraintSeverity.ERROR, ConstraintSeverity.CRITICAL)
            for v in self.violations
        )

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations
                   if v.severity in (ConstraintSeverity.ERROR, ConstraintSeverity.CRITICAL))

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations
                   if v.severity == ConstraintSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for v in self.violations
                   if v.severity == ConstraintSeverity.INFO)

    def by_severity(self, severity: ConstraintSeverity) -> List[ConstraintViolation]:
        return [v for v in self.violations if v.severity == severity]

    def by_file(self, file_path: str) -> List[ConstraintViolation]:
        return [v for v in self.violations if v.file_path == file_path]

    def summary(self) -> str:
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        lines = [
            f"Verification {status}",
            f"  {self.files_checked} files, {self.constraints_run} constraints",
            f"  {self.error_count} errors, {self.warning_count} warnings, {self.info_count} info",
        ]
        if not self.passed:
            lines.append("  Blocking violations:")
            for v in self.by_severity(ConstraintSeverity.ERROR) + self.by_severity(ConstraintSeverity.CRITICAL):
                loc = f"{v.file_path}:{v.line_number}" if v.line_number else v.file_path
                lines.append(f"    • [{v.severity.value}] {loc}: {v.message}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "files_checked": self.files_checked,
            "constraints_run": self.constraints_run,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "violations": [v.to_dict() for v in self.violations],
            "duration_s": round(self.duration_s, 3),
        }


class DesignVerifier:
    """Runs design constraints against code changes.

    Usage:
        verifier = DesignVerifier()

        # Add constraints
        verifier.add(DesignConstraint(
            id="no-print", name="No print statements",
            pattern=r"\\bprint\\(",
            severity=ConstraintSeverity.WARNING,
            suggestion="Use logging instead of print()",
        ))

        # Verify files
        report = verifier.verify({
            "src/auth.py": "import logging\\ndef auth(): print('debug')",
            "src/cache.py": "import logging\\ndef cache(): logging.info('ok')",
        })

        print(report.summary())
    """

    def __init__(self):
        self._constraints: Dict[str, DesignConstraint] = {}

    def add(self, constraint: DesignConstraint) -> None:
        """Register a design constraint."""
        self._constraints[constraint.id] = constraint

    def remove(self, constraint_id: str) -> Optional[DesignConstraint]:
        """Remove a constraint by ID."""
        return self._constraints.pop(constraint_id, None)

    def get(self, constraint_id: str) -> Optional[DesignConstraint]:
        return self._constraints.get(constraint_id)

    @property
    def constraints(self) -> List[DesignConstraint]:
        return list(self._constraints.values())

    def verify(self, files: Dict[str, str],
               metadata: Optional[Dict[str, Any]] = None) -> VerificationReport:
        """Verify a set of files against all enabled constraints.

        Args:
            files: mapping of file_path -> file_content
            metadata: optional context (e.g., PR info, commit message)

        Returns:
            VerificationReport with all violations found
        """
        start = time.time()
        report = VerificationReport()
        report.files_checked = len(files)

        active = [c for c in self._constraints.values() if c.enabled]
        report.constraints_run = len(active)

        for file_path, content in files.items():
            for constraint in active:
                violations = constraint.check(content, file_path, metadata)
                report.violations.extend(violations)

        report.duration_s = time.time() - start
        return report

    def verify_diff(self, diff_lines: List[str],
                    file_path: str = "",
                    metadata: Optional[Dict[str, Any]] = None) -> VerificationReport:
        """Verify only the added lines from a diff.

        Extracts lines starting with '+' (excluding +++ header) and
        runs constraints only against those lines.
        """
        added_lines = []
        for line in diff_lines:
            if line.startswith('+') and not line.startswith('+++'):
                added_lines.append(line[1:])  # Strip the '+'

        added_content = '\n'.join(added_lines)
        return self.verify({file_path: added_content}, metadata)

    def load_builtin(self, category: Optional[ConstraintCategory] = None) -> int:
        """Load built-in constraints. Returns count loaded."""
        loaded = 0
        for constraint in BUILTIN_CONSTRAINTS:
            if category and constraint.category != category:
                continue
            self.add(constraint)
            loaded += 1
        return loaded


# ─── Built-in Constraints ──────────────────────────────────────────

def _max_function_length(content: str, meta: dict) -> bool:
    """Check that no function exceeds 50 lines."""
    max_lines = meta.get("max_function_lines", 50)
    in_func = False
    func_start = 0
    indent_level = 0
    for i, line in enumerate(content.split('\n'), 1):
        stripped = line.lstrip()
        if stripped.startswith('def ') or stripped.startswith('async def '):
            if in_func and (i - func_start) > max_lines:
                return False
            in_func = True
            func_start = i
            indent_level = len(line) - len(stripped)
        elif in_func and stripped and not line.startswith(' ' * (indent_level + 1)):
            if stripped and not stripped.startswith('#') and not stripped.startswith('@'):
                if (i - func_start) > max_lines:
                    return False
                in_func = False
    if in_func:
        lines_count = len(content.split('\n')) - func_start + 1
        if lines_count > max_lines:
            return False
    return True


def _has_module_docstring(content: str, meta: dict) -> bool:
    """Check that the file has a module-level docstring."""
    stripped = content.lstrip()
    return stripped.startswith('"""') or stripped.startswith("'''") or stripped.startswith('#')


BUILTIN_CONSTRAINTS = [
    DesignConstraint(
        id="no-print", name="No print() in production code",
        description="Use logging instead of print() for observability",
        category=ConstraintCategory.PATTERN,
        severity=ConstraintSeverity.WARNING,
        pattern=r'\bprint\s*\(',
        file_glob="*.py",
        suggestion="Replace print() with logging.debug/info/warning",
        tags=["quality", "logging"],
    ),
    DesignConstraint(
        id="no-star-import", name="No wildcard imports",
        description="Wildcard imports pollute namespace and hide dependencies",
        category=ConstraintCategory.DEPENDENCY,
        severity=ConstraintSeverity.ERROR,
        pattern=r'^from\s+\S+\s+import\s+\*',
        file_glob="*.py",
        suggestion="Import specific names: from module import Class, function",
        tags=["quality", "imports"],
    ),
    DesignConstraint(
        id="no-bare-except", name="No bare except clauses",
        description="Bare except catches SystemExit and KeyboardInterrupt",
        category=ConstraintCategory.PATTERN,
        severity=ConstraintSeverity.ERROR,
        pattern=r'except\s*:',
        file_glob="*.py",
        suggestion="Use 'except Exception:' or a specific exception type",
        tags=["quality", "error-handling"],
    ),
    DesignConstraint(
        id="no-hardcoded-secrets", name="No hardcoded secrets",
        description="Secrets should come from environment or config",
        category=ConstraintCategory.SECURITY,
        severity=ConstraintSeverity.CRITICAL,
        pattern=r'(?i)(api_key|secret|password|token)\s*=\s*["\'][^"\']{8,}["\']',
        file_glob="*.py",
        suggestion="Use os.environ or a secrets manager",
        tags=["security"],
    ),
    DesignConstraint(
        id="module-docstring", name="Module docstring required",
        description="Every Python module should have a docstring",
        category=ConstraintCategory.DOCUMENTATION,
        severity=ConstraintSeverity.INFO,
        predicate=_has_module_docstring,
        file_glob="*.py",
        suggestion="Add a module-level docstring (triple-quoted string at top of file)",
        tags=["documentation"],
    ),
    DesignConstraint(
        id="max-function-length", name="Function length limit",
        description="Functions should not exceed 50 lines",
        category=ConstraintCategory.COMPLEXITY,
        severity=ConstraintSeverity.WARNING,
        predicate=_max_function_length,
        file_glob="*.py",
        suggestion="Extract helper functions or simplify logic",
        tags=["complexity"],
    ),
    DesignConstraint(
        id="no-todo-fixme", name="No TODO/FIXME in production",
        description="TODOs should be tracked as issues, not code comments",
        category=ConstraintCategory.DOCUMENTATION,
        severity=ConstraintSeverity.INFO,
        pattern=r'#\s*(TODO|FIXME|HACK|XXX)',
        file_glob="*.py",
        suggestion="Create an issue tracker entry instead",
        tags=["quality", "documentation"],
    ),
    DesignConstraint(
        id="no-mutable-default", name="No mutable default arguments",
        description="Mutable defaults (list, dict) are shared across calls",
        category=ConstraintCategory.PATTERN,
        severity=ConstraintSeverity.WARNING,
        pattern=r'def\s+\w+\([^)]*(?:=\s*\[\]|=\s*\{\})',
        file_glob="*.py",
        suggestion="Use None as default, then create inside: if arg is None: arg = []",
        tags=["quality", "python"],
    ),
]


# ─── Utilities ──────────────────────────────────────────────────────

def _glob_match(path: str, pattern: str) -> bool:
    """Simple glob matching for file paths."""
    import fnmatch
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.split('/')[-1], pattern)


def _extract_context(content: str, line_num: int, context_lines: int = 2) -> str:
    """Extract lines around a specific line number."""
    lines = content.split('\n')
    start = max(0, line_num - context_lines - 1)
    end = min(len(lines), line_num + context_lines)
    return '\n'.join(f"{'>' if i+1 == line_num else ' '} {lines[i]}" for i in range(start, end))
