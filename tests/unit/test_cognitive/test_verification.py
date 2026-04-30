"""Tests for Design-Aware Verification."""
import pytest
from nexus.cognitive.verification import (
    DesignVerifier, DesignConstraint, VerificationReport,
    ConstraintViolation, ConstraintSeverity, ConstraintCategory,
    VerificationResult, BUILTIN_CONSTRAINTS,
)


class TestConstraintViolation:
    def test_to_dict(self):
        v = ConstraintViolation(
            constraint_id="no-print", message="Found print",
            file_path="src/main.py", line_number=42,
            severity=ConstraintSeverity.WARNING,
        )
        d = v.to_dict()
        assert d["constraint_id"] == "no-print"
        assert d["severity"] == "warning"
        assert d["line_number"] == 42


class TestDesignConstraint:
    def test_pattern_violation(self):
        c = DesignConstraint(
            id="no-print", name="No print",
            pattern=r'\bprint\s*\(', file_glob="*.py",
            severity=ConstraintSeverity.WARNING,
        )
        violations = c.check("x = 1\nprint('debug')\ny = 2", "test.py")
        assert len(violations) == 1
        assert violations[0].line_number == 2

    def test_pattern_no_violation(self):
        c = DesignConstraint(
            id="no-print", name="No print",
            pattern=r'\bprint\s*\(', file_glob="*.py",
        )
        violations = c.check("logging.info('clean code')", "test.py")
        assert len(violations) == 0

    def test_anti_pattern_violation(self):
        c = DesignConstraint(
            id="need-docstring", name="Needs docstring",
            anti_pattern=r'"""', file_glob="*.py",
        )
        violations = c.check("def foo(): pass", "test.py")
        assert len(violations) == 1

    def test_anti_pattern_passes(self):
        c = DesignConstraint(
            id="need-docstring", name="Needs docstring",
            anti_pattern=r'"""', file_glob="*.py",
        )
        violations = c.check('"""Module doc."""\ndef foo(): pass', "test.py")
        assert len(violations) == 0

    def test_predicate_check(self):
        c = DesignConstraint(
            id="max-lines", name="Max 5 lines",
            predicate=lambda content, meta: len(content.split('\n')) <= 5,
            file_glob="*.py",
            severity=ConstraintSeverity.ERROR,
        )
        short = "a\nb\nc"
        long = "\n".join(f"line {i}" for i in range(10))
        assert c.check(short, "short.py") == []
        assert len(c.check(long, "long.py")) == 1

    def test_predicate_error_handled(self):
        c = DesignConstraint(
            id="bad", name="Bad predicate",
            predicate=lambda content, meta: 1 / 0,
            file_glob="*.py",
        )
        violations = c.check("anything", "test.py")
        assert len(violations) == 1
        assert violations[0].severity == ConstraintSeverity.INFO

    def test_disabled_constraint(self):
        c = DesignConstraint(
            id="disabled", pattern=r'print', enabled=False,
        )
        assert c.check("print('hi')", "test.py") == []

    def test_file_glob_filtering(self):
        c = DesignConstraint(
            id="py-only", pattern=r'TODO', file_glob="*.py",
        )
        assert len(c.check("# TODO", "test.py")) == 1
        assert len(c.check("# TODO", "test.js")) == 0

    def test_multiple_violations(self):
        c = DesignConstraint(
            id="no-print", pattern=r'\bprint\s*\(',
            file_glob="*.py",
        )
        code = "print('a')\nprint('b')\nprint('c')"
        violations = c.check(code, "test.py")
        assert len(violations) == 3


class TestVerificationReport:
    def test_empty_report_passes(self):
        r = VerificationReport()
        assert r.passed
        assert r.error_count == 0
        assert r.warning_count == 0

    def test_warning_only_passes(self):
        r = VerificationReport(violations=[
            ConstraintViolation(severity=ConstraintSeverity.WARNING),
        ])
        assert r.passed

    def test_error_fails(self):
        r = VerificationReport(violations=[
            ConstraintViolation(severity=ConstraintSeverity.ERROR),
        ])
        assert not r.passed
        assert r.error_count == 1

    def test_critical_fails(self):
        r = VerificationReport(violations=[
            ConstraintViolation(severity=ConstraintSeverity.CRITICAL),
        ])
        assert not r.passed

    def test_by_severity(self):
        r = VerificationReport(violations=[
            ConstraintViolation(severity=ConstraintSeverity.WARNING),
            ConstraintViolation(severity=ConstraintSeverity.ERROR),
            ConstraintViolation(severity=ConstraintSeverity.WARNING),
        ])
        assert len(r.by_severity(ConstraintSeverity.WARNING)) == 2
        assert len(r.by_severity(ConstraintSeverity.ERROR)) == 1

    def test_by_file(self):
        r = VerificationReport(violations=[
            ConstraintViolation(file_path="a.py"),
            ConstraintViolation(file_path="b.py"),
            ConstraintViolation(file_path="a.py"),
        ])
        assert len(r.by_file("a.py")) == 2

    def test_summary(self):
        r = VerificationReport(
            files_checked=3, constraints_run=5,
            violations=[
                ConstraintViolation(severity=ConstraintSeverity.ERROR, message="bad"),
            ],
        )
        s = r.summary()
        assert "FAILED" in s
        assert "3 files" in s
        assert "1 errors" in s

    def test_to_dict(self):
        r = VerificationReport(files_checked=2, constraints_run=3)
        d = r.to_dict()
        assert d["passed"]
        assert d["files_checked"] == 2


class TestDesignVerifier:
    def test_empty_verifier(self):
        v = DesignVerifier()
        report = v.verify({"test.py": "print('hello')"})
        assert report.passed
        assert report.constraints_run == 0

    def test_add_and_verify(self):
        v = DesignVerifier()
        v.add(DesignConstraint(
            id="no-print", name="No print",
            pattern=r'\bprint\s*\(', file_glob="*.py",
            severity=ConstraintSeverity.WARNING,
        ))
        report = v.verify({"src/main.py": "print('debug')"})
        assert report.warning_count == 1
        assert report.passed  # Warnings don't fail

    def test_error_constraint_fails(self):
        v = DesignVerifier()
        v.add(DesignConstraint(
            id="no-star", name="No star imports",
            pattern=r'from\s+\S+\s+import\s+\*', file_glob="*.py",
            severity=ConstraintSeverity.ERROR,
        ))
        report = v.verify({"main.py": "from os import *"})
        assert not report.passed

    def test_multiple_files(self):
        v = DesignVerifier()
        v.add(DesignConstraint(
            id="no-print", pattern=r'\bprint\s*\(', file_glob="*.py",
            severity=ConstraintSeverity.WARNING,
        ))
        report = v.verify({
            "a.py": "print('a')",
            "b.py": "logging.info('b')",
            "c.py": "print('c1')\nprint('c2')",
        })
        assert report.files_checked == 3
        assert report.warning_count == 3  # a: 1, c: 2

    def test_remove_constraint(self):
        v = DesignVerifier()
        v.add(DesignConstraint(id="c1", pattern=r'x'))
        assert v.remove("c1") is not None
        assert v.remove("c1") is None

    def test_get_constraint(self):
        v = DesignVerifier()
        v.add(DesignConstraint(id="c1", name="Test"))
        assert v.get("c1").name == "Test"
        assert v.get("nope") is None

    def test_verify_diff(self):
        v = DesignVerifier()
        v.add(DesignConstraint(
            id="no-print", pattern=r'\bprint\s*\(', file_glob="*.py",
            severity=ConstraintSeverity.WARNING,
        ))
        diff = [
            "--- a/src/main.py",
            "+++ b/src/main.py",
            "@@ -1,3 +1,5 @@",
            " import logging",
            "+print('debug')",
            " def main():",
            "+    print('more debug')",
            "     logging.info('ok')",
        ]
        report = v.verify_diff(diff, "src/main.py")
        assert report.warning_count == 2

    def test_load_builtin(self):
        v = DesignVerifier()
        count = v.load_builtin()
        assert count == len(BUILTIN_CONSTRAINTS)
        assert len(v.constraints) == count

    def test_load_builtin_by_category(self):
        v = DesignVerifier()
        count = v.load_builtin(category=ConstraintCategory.SECURITY)
        assert count >= 1
        assert all(c.category == ConstraintCategory.SECURITY for c in v.constraints)

    def test_builtin_no_print(self):
        v = DesignVerifier()
        v.load_builtin()
        report = v.verify({"app.py": '"""App."""\nprint("debug")\n'})
        prints = [v for v in report.violations if v.constraint_id == "no-print"]
        assert len(prints) == 1

    def test_builtin_no_star_import(self):
        v = DesignVerifier()
        v.load_builtin()
        report = v.verify({"app.py": '"""App."""\nfrom os import *\n'})
        stars = [v for v in report.violations if v.constraint_id == "no-star-import"]
        assert len(stars) == 1
        assert stars[0].severity == ConstraintSeverity.ERROR

    def test_builtin_no_hardcoded_secrets(self):
        v = DesignVerifier()
        v.load_builtin()
        report = v.verify({"config.py": '"""Config."""\nAPI_KEY = "sk-abc123def456"\n'})
        secrets = [v for v in report.violations if v.constraint_id == "no-hardcoded-secrets"]
        assert len(secrets) == 1
        assert secrets[0].severity == ConstraintSeverity.CRITICAL
