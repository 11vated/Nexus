"""Unit tests for logging utilities."""
import pytest
import logging
import sys
from io import StringIO

from nexus.utils.logging_utils import get_logger, LogContext


class TestGetLogger:
    """Test logger creation."""

    def test_get_logger_creates_child(self):
        """Test get_logger creates child logger."""
        logger = get_logger("test")
        
        assert logger.name == "nexus.test"
        assert isinstance(logger, logging.Logger)

    def test_get_logger_different_names(self):
        """Test logger with different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        assert logger1.name == "nexus.module1"
        assert logger2.name == "nexus.module2"


class TestLogContext:
    """Test log context manager."""

    def test_context_success(self, caplog):
        """Test context logs on success."""
        logger = get_logger("test")
        
        with caplog.at_level(logging.INFO):
            with LogContext(logger, operation="test_op", user="test_user"):
                pass  # Do nothing, just log
        
        assert "Operation completed" in caplog.text
        assert "test_op" in caplog.text
        assert "test_user" in caplog.text

    def test_context_failure(self, caplog):
        """Test context logs on failure."""
        logger = get_logger("test")
        
        with caplog.at_level(logging.ERROR):
            try:
                with LogContext(logger, operation="failing_op"):
                    raise ValueError("test error")
            except ValueError:
                pass  # Ignore the error
        
        assert "Operation failed" in caplog.text
        assert "failing_op" in caplog.text
        assert "test error" in caplog.text