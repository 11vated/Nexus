"""Tool Result Validation — validate tool outputs before returning to LLM.

Prevents garbage-in-garbage-out by checking tool results against expected
schemas, patterns, and constraints before they reach the LLM.

Validators:
- SchemaValidator: Check result structure (for JSON tools)
- PatternValidator: Regex-based content validation
- SizeValidator: Enforce size limits
- ContentValidator: Check for expected content markers
- CompositeValidator: Chain multiple validators
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    validator_name: str
    message: str = ""
    suggestions: List[str] = field(default_factory=list)


class BaseValidator(ABC):
    """Base class for tool result validators."""

    name: str = "base_validator"

    @abstractmethod
    def validate(self, result: str, **kwargs: Any) -> ValidationResult:
        """Validate a tool result.

        Args:
            result: Tool output string.
            **kwargs: Additional context (tool_name, args, etc.).

        Returns:
            ValidationResult with pass/fail status.
        """
        ...


class SchemaValidator(BaseValidator):
    """Validates that a JSON result matches an expected schema.

    Simple schema validation — checks for required keys and types.
    """

    name = "schema"

    def __init__(self, required_keys: Optional[List[str]] = None,
                 type_hints: Optional[Dict[str, str]] = None):
        self.required_keys = required_keys or []
        self.type_hints = type_hints or {}  # key -> expected type name

    def validate(self, result: str, **kwargs: Any) -> ValidationResult:
        result = result.strip()

        # Try to extract JSON from result
        json_str = self._extract_json(result)
        if not json_str:
            if self.required_keys:
                return ValidationResult(
                    passed=False, validator_name=self.name,
                    message="Result is not valid JSON",
                    suggestions=["Ensure tool returns a JSON object"],
                )
            return ValidationResult(
                passed=True, validator_name=self.name,
                message="No JSON validation required (no required keys)",
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            return ValidationResult(
                passed=False, validator_name=self.name,
                message=f"Invalid JSON: {exc}",
                suggestions=["Fix JSON syntax", "Escape special characters"],
            )

        if not isinstance(data, dict):
            return ValidationResult(
                passed=False, validator_name=self.name,
                message="Expected a JSON object, got something else",
            )

        # Check required keys
        missing = [k for k in self.required_keys if k not in data]
        if missing:
            return ValidationResult(
                passed=False, validator_name=self.name,
                message=f"Missing required keys: {missing}",
                suggestions=[f"Add key: {k}" for k in missing],
            )

        # Check types
        type_errors = []
        for key, expected_type_name in self.type_hints.items():
            if key in data:
                if not self._check_type(data[key], expected_type_name):
                    type_errors.append(
                        f"Key '{key}' expected {expected_type_name}, got {type(data[key]).__name__}"
                    )

        if type_errors:
            return ValidationResult(
                passed=False, validator_name=self.name,
                message="Type mismatches: " + "; ".join(type_errors),
                suggestions=type_errors,
            )

        return ValidationResult(
            passed=True, validator_name=self.name,
            message="Schema validation passed",
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """Try to extract a JSON object from text that may contain markdown."""
        # Try direct parse
        stripped = text.strip()
        if stripped.startswith("{"):
            return stripped

        # Try to extract from code block
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1)

        # Try to find { ... } block
        start = text.find("{")
        if start >= 0:
            end = text.rfind("}")
            if end > start:
                return text[start:end + 1]

        return None

    @staticmethod
    def _check_type(value: Any, type_name: str) -> bool:
        """Check if value matches expected type name."""
        type_map = {
            "str": str, "string": str,
            "int": int, "integer": int,
            "float": (int, float), "number": (int, float),
            "bool": bool, "boolean": bool,
            "list": list, "array": list,
            "dict": dict, "object": dict,
        }
        expected = type_map.get(type_name.lower())
        if expected is None:
            return True  # Unknown type — skip check
        return isinstance(value, expected)


class PatternValidator(BaseValidator):
    """Validates that result matches expected regex patterns."""

    name = "pattern"

    def __init__(self, patterns: Optional[List[Pattern]] = None,
                 must_not_match: Optional[List[Pattern]] = None):
        self.patterns = patterns or []
        self.must_not_match = must_not_match or []

    def validate(self, result: str, **kwargs: Any) -> ValidationResult:
        # Check required patterns
        for pattern in self.patterns:
            if not pattern.search(result):
                return ValidationResult(
                    passed=False, validator_name=self.name,
                    message=f"Expected pattern not found: {pattern.pattern}",
                )

        # Check forbidden patterns
        for pattern in self.must_not_match:
            if pattern.search(result):
                return ValidationResult(
                    passed=False, validator_name=self.name,
                    message=f"Forbidden pattern found: {pattern.pattern}",
                    suggestions=["Sanitize output", "Check tool configuration"],
                )

        return ValidationResult(
            passed=True, validator_name=self.name,
            message="Pattern validation passed",
        )


class SizeValidator(BaseValidator):
    """Validates result size constraints."""

    name = "size"

    def __init__(self, max_chars: int = 50000, max_lines: int = 10000,
                 min_chars: int = 0):
        self.max_chars = max_chars
        self.max_lines = max_lines
        self.min_chars = min_chars

    def validate(self, result: str, **kwargs: Any) -> ValidationResult:
        if len(result) < self.min_chars:
            return ValidationResult(
                passed=False, validator_name=self.name,
                message=f"Result too short: {len(result)} chars (min: {self.min_chars})",
                suggestions=["Check tool input", "Verify data source"],
            )

        if len(result) > self.max_chars:
            return ValidationResult(
                passed=False, validator_name=self.name,
                message=f"Result too large: {len(result)} chars (max: {self.max_chars})",
                suggestions=["Increase max_chars limit", "Use pagination"],
            )

        line_count = result.count("\n") + 1
        if line_count > self.max_lines:
            return ValidationResult(
                passed=False, validator_name=self.name,
                message=f"Too many lines: {line_count} (max: {self.max_lines})",
                suggestions=["Truncate output", "Use filtering"],
            )

        return ValidationResult(
            passed=True, validator_name=self.name,
            message="Size validation passed",
        )


class ContentValidator(BaseValidator):
    """Validates that result contains expected content markers.

    Useful for verifying that tools produced meaningful output, not
    just empty results or generic error messages.
    """

    name = "content"

    def __init__(self,
                 must_contain: Optional[List[str]] = None,
                 must_not_contain: Optional[List[str]] = None,
                 allow_empty: bool = False):
        self.must_contain = must_contain or []
        self.must_not_contain = must_not_contain or []
        self.allow_empty = allow_empty

    def validate(self, result: str, **kwargs: Any) -> ValidationResult:
        if not result.strip() and not self.allow_empty:
            return ValidationResult(
                passed=False, validator_name=self.name,
                message="Empty result",
                suggestions=["Check tool configuration", "Verify input data"],
            )

        result_lower = result.lower()

        for marker in self.must_contain:
            if marker.lower() not in result_lower:
                return ValidationResult(
                    passed=False, validator_name=self.name,
                    message=f"Expected content not found: '{marker}'",
                )

        for marker in self.must_not_contain:
            if marker.lower() in result_lower:
                return ValidationResult(
                    passed=False, validator_name=self.name,
                    message=f"Forbidden content found: '{marker}'",
                )

        return ValidationResult(
            passed=True, validator_name=self.name,
            message="Content validation passed",
        )


class CompositeValidator(BaseValidator):
    """Runs multiple validators in sequence.

    Stops at the first failure (fail-fast) or runs all (collect-all)
    depending on configuration.
    """

    name = "composite"

    def __init__(self, validators: Optional[List[BaseValidator]] = None,
                 fail_fast: bool = True):
        self.validators = validators or []
        self.fail_fast = fail_fast

    def add(self, validator: BaseValidator) -> None:
        """Add a validator to the chain."""
        self.validators.append(validator)

    def validate(self, result: str, **kwargs: Any) -> ValidationResult:
        all_results = []

        for validator in self.validators:
            vresult = validator.validate(result, **kwargs)
            all_results.append(vresult)

            if not vresult.passed and self.fail_fast:
                return ValidationResult(
                    passed=False,
                    validator_name=f"composite[{vresult.validator_name}]",
                    message=vresult.message,
                    suggestions=vresult.suggestions,
                )

        if all(r.passed for r in all_results):
            return ValidationResult(
                passed=True, validator_name=self.name,
                message="All validators passed",
            )

        # Collect all failures
        failures = [r for r in all_results if not r.passed]
        return ValidationResult(
            passed=False,
            validator_name=self.name,
            message=f"{len(failures)} validation failures: " +
                    "; ".join(f"{r.validator_name}: {r.message}" for r in failures),
            suggestions=[s for r in failures for s in r.suggestions],
        )


class ToolValidationManager:
    """Manages validators for all tools.

    Pre-configures validators for common tools and allows custom validators.
    """

    def __init__(self):
        self._validators: Dict[str, CompositeValidator] = {}
        self._register_default_validators()

    def _register_default_validators(self) -> None:
        """Register default validators for common tools."""
        # File read validator
        file_read_val = CompositeValidator(fail_fast=True)
        file_read_val.add(SizeValidator(max_chars=500000))
        file_read_val.add(ContentValidator(
            must_not_contain=["Traceback (most recent call last)"],
            allow_empty=True,
        ))
        self._validators["file_read"] = file_read_val

        # File write validator
        file_write_val = CompositeValidator(fail_fast=True)
        file_write_val.add(PatternValidator(
            patterns=[re.compile(r"written\s+\d+", re.IGNORECASE)],
        ))
        self._validators["file_write"] = file_write_val

        # Search validator
        search_val = CompositeValidator(fail_fast=False)
        search_val.add(SizeValidator(max_chars=100000))
        search_val.add(ContentValidator(allow_empty=True))
        self._validators["search"] = search_val

    def get_validator(self, tool_name: str) -> Optional[CompositeValidator]:
        """Get the validator for a tool."""
        return self._validators.get(tool_name)

    def add_validator(self, tool_name: str, validator: CompositeValidator) -> None:
        """Register a custom validator for a tool."""
        self._validators[tool_name] = validator

    def validate_result(self, tool_name: str, result: str,
                        **kwargs: Any) -> ValidationResult:
        """Validate a tool result.

        Args:
            tool_name: Name of the tool that produced the result.
            result: Tool output.
            **kwargs: Additional context.

        Returns:
            ValidationResult with pass/fail and suggestions.
        """
        validator = self.get_validator(tool_name)
        if not validator:
            return ValidationResult(
                passed=True, validator_name="none",
                message="No validator registered for this tool",
            )

        return validator.validate(result, tool_name=tool_name, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """Get validation manager statistics."""
        return {
            "registered_validators": list(self._validators.keys()),
            "validator_count": len(self._validators),
        }
