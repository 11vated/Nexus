"""Tests for Tool Result Validation."""
import re

import pytest

from nexus.tools.validation import (
    BaseValidator,
    CompositeValidator,
    ContentValidator,
    PatternValidator,
    SchemaValidator,
    SizeValidator,
    ToolValidationManager,
    ValidationResult,
)


class TestValidationResult:
    def test_passed(self):
        r = ValidationResult(passed=True, validator_name="test", message="OK")
        assert r.passed
        assert r.message == "OK"
        assert r.suggestions == []

    def test_failed_with_suggestions(self):
        r = ValidationResult(
            passed=False, validator_name="test",
            message="Failed", suggestions=["Try X", "Try Y"],
        )
        assert not r.passed
        assert len(r.suggestions) == 2


class TestSchemaValidator:
    def test_valid_json(self):
        v = SchemaValidator(required_keys=["name", "age"])
        result = v.validate('{"name": "Alice", "age": 30}')
        assert result.passed

    def test_missing_keys(self):
        v = SchemaValidator(required_keys=["name", "email"])
        result = v.validate('{"name": "Alice"}')
        assert not result.passed
        assert "email" in result.message

    def test_type_mismatch(self):
        v = SchemaValidator(type_hints={"age": "int"})
        result = v.validate('{"age": "thirty"}')
        assert not result.passed

    def test_not_json(self):
        v = SchemaValidator(required_keys=["name"])
        result = v.validate("This is not JSON")
        assert not result.passed

    def test_json_in_markdown(self):
        v = SchemaValidator(required_keys=["status"])
        result = v.validate('```\n{"status": "ok"}\n```')
        assert result.passed

    def test_no_required_keys_accepts_anything(self):
        v = SchemaValidator()
        result = v.validate("plain text")
        assert result.passed

    def test_type_checks(self):
        assert SchemaValidator._check_type("hello", "str") is True
        assert SchemaValidator._check_type(42, "int") is True
        assert SchemaValidator._check_type(3.14, "float") is True
        assert SchemaValidator._check_type(True, "bool") is True
        assert SchemaValidator._check_type([1, 2], "list") is True
        assert SchemaValidator._check_type({"a": 1}, "dict") is True
        assert SchemaValidator._check_type("hello", "int") is False

    def test_extract_json_direct(self):
        assert SchemaValidator._extract_json('{"key": "value"}') == '{"key": "value"}'

    def test_extract_json_from_code_block(self):
        text = "Some text\n```json\n{\"a\": 1}\n```"
        extracted = SchemaValidator._extract_json(text)
        assert '{"a": 1}' in extracted

    def test_extract_json_from_braces(self):
        text = "prefix {nested: {a: 1}} suffix"
        extracted = SchemaValidator._extract_json(text)
        assert extracted.startswith("{")


class TestPatternValidator:
    def test_matches(self):
        v = PatternValidator(patterns=[re.compile(r"\d+")])
        result = v.validate("There are 42 items")
        assert result.passed

    def test_does_not_match(self):
        v = PatternValidator(patterns=[re.compile(r"\d+")])
        result = v.validate("No numbers here")
        assert not result.passed

    def test_must_not_match(self):
        v = PatternValidator(must_not_match=[re.compile(r"ERROR")])
        result = v.validate("Something went wrong: ERROR 500")
        assert not result.passed

    def test_passes_all(self):
        v = PatternValidator(
            patterns=[re.compile(r"written", re.IGNORECASE)],
            must_not_match=[re.compile(r"failed")],
        )
        result = v.validate("Written 100 chars to file.txt")
        assert result.passed


class TestSizeValidator:
    def test_within_limits(self):
        v = SizeValidator(max_chars=1000)
        result = v.validate("Hello world")
        assert result.passed

    def test_too_large(self):
        v = SizeValidator(max_chars=10)
        result = v.validate("This is way too long")
        assert not result.passed

    def test_too_short(self):
        v = SizeValidator(min_chars=100)
        result = v.validate("Short")
        assert not result.passed

    def test_too_many_lines(self):
        v = SizeValidator(max_lines=5)
        result = v.validate("a\nb\nc\nd\ne\nf\ng")
        assert not result.passed


class TestContentValidator:
    def test_must_contain(self):
        v = ContentValidator(must_contain=["success"])
        result = v.validate("Operation completed with success")
        assert result.passed

    def test_must_contain_missing(self):
        v = ContentValidator(must_contain=["success"])
        result = v.validate("Operation failed")
        assert not result.passed

    def test_must_not_contain(self):
        v = ContentValidator(must_not_contain=["Traceback"])
        result = v.validate("Traceback (most recent call last)")
        assert not result.passed

    def test_allow_empty(self):
        v = ContentValidator(allow_empty=True)
        result = v.validate("   ")
        assert result.passed

    def test_disallow_empty(self):
        v = ContentValidator(allow_empty=False)
        result = v.validate("   ")
        assert not result.passed


class TestCompositeValidator:
    def test_all_pass(self):
        comp = CompositeValidator(fail_fast=True)
        comp.add(SizeValidator(max_chars=1000))
        comp.add(ContentValidator(must_contain=["ok"]))

        result = comp.validate("Everything is ok")
        assert result.passed

    def test_fail_fast(self):
        comp = CompositeValidator(fail_fast=True)
        comp.add(SizeValidator(max_chars=5))
        comp.add(ContentValidator(must_contain=["ok"]))

        result = comp.validate("This is too long and ok")
        assert not result.passed
        # Should have stopped at size validator

    def test_collect_all(self):
        comp = CompositeValidator(fail_fast=False)
        comp.add(SizeValidator(max_chars=5))
        comp.add(ContentValidator(must_contain=["ok"]))

        result = comp.validate("too long and nope")
        assert not result.passed
        assert "2 validation failures" in result.message


class TestToolValidationManager:
    def test_default_validators(self):
        manager = ToolValidationManager()
        assert manager.get_validator("file_read") is not None
        assert manager.get_validator("file_write") is not None
        assert manager.get_validator("search") is not None

    def test_validate_file_write(self):
        manager = ToolValidationManager()
        result = manager.validate_result("file_write", "Written 100 chars to test.py")
        assert result.passed

    def test_validate_file_write_bad(self):
        manager = ToolValidationManager()
        result = manager.validate_result("file_write", "Error: could not write")
        assert not result.passed

    def test_validate_unknown_tool(self):
        manager = ToolValidationManager()
        result = manager.validate_result("unknown_tool", "anything")
        assert result.passed  # No validator = pass

    def test_get_stats(self):
        manager = ToolValidationManager()
        stats = manager.get_stats()
        assert stats["validator_count"] >= 3
