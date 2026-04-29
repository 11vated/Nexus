"""Structured logging configuration for Nexus."""
import logging
import sys
from pathlib import Path
from typing import Any


def setup_logging(
    level: str = "INFO",
    log_dir: Path = None,
    json_format: bool = False
) -> logging.Logger:
    """Configure structured logging for Nexus."""
    logger = logging.getLogger("nexus")
    logger.setLevel(getattr(logging, level.upper()))
    
    logger.handlers.clear()
    
    formatter: logging.Formatter
    if json_format:
        try:
            from pythonjsonlogger import jsonlogger
            formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s',
                reserved_attrs=['msg', 'args']
            )
        except ImportError:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "nexus.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "nexus") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(f"nexus.{name}")


class LogContext:
    """Context manager for adding structured context to logs."""
    
    def __init__(self, logger: logging.Logger, **context: Any):
        self.logger = logger
        self.context = context
        self._old_factory = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        ctx_str = " ".join(f"{k}={v}" for k, v in self.context.items())
        if exc_type:
            self.logger.error(
                f"Operation failed [{ctx_str}] error={exc_val}",
                extra={**self.context, "error": str(exc_val)},
                exc_info=True
            )
        else:
            self.logger.info(
                f"Operation completed [{ctx_str}]",
                extra=self.context
            )
        return False