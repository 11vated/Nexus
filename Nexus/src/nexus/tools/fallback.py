"""Tool Fallback Chains — resilient tool execution with automatic retries and fallbacks.

When a tool fails, this module provides structured fallback strategies:
1. Retry with backoff for transient failures
2. Try alternative tools for the same semantic goal
3. Degrade gracefully with informative error messages

Fallback chains are defined as ordered lists of (tool_name, args_transform) pairs.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Categories of tool failures."""
    TRANSIENT = "transient"          # Network timeout, rate limit — retryable
    PERMISSION = "permission"        # Access denied — try alternative auth/path
    NOT_FOUND = "not_found"          # Resource missing — try different path
    VALIDATION = "validation"        # Input/output invalid — retry with fixed input
    FATAL = "fatal"                  # Cannot recover — report to user


@dataclass
class FallbackAttempt:
    """Record of a single fallback attempt."""
    tool_name: str
    success: bool
    error: str = ""
    duration: float = 0.0


@dataclass
class FallbackResult:
    """Result of a fallback chain execution."""
    success: bool
    result: str = ""
    attempts: List[FallbackAttempt] = field(default_factory=list)
    failure_type: Optional[FailureType] = None


def classify_failure(error: str) -> FailureType:
    """Classify a tool failure by analyzing the error message.

    Args:
        error: Error message from tool execution.

    Returns:
        The most likely failure category.
    """
    error_lower = error.lower()

    if any(kw in error_lower for kw in ["timeout", "timed out", "connection", "rate limit", "too many"]):
        return FailureType.TRANSIENT
    if any(kw in error_lower for kw in ["permission", "denied", "forbidden", "unauthorized"]):
        return FailureType.PERMISSION
    if any(kw in error_lower for kw in ["not found", "no such file", "does not exist", "missing"]):
        return FailureType.NOT_FOUND
    if any(kw in error_lower for kw in ["invalid", "malformed", "schema", "validation"]):
        return FailureType.VALIDATION
    return FailureType.FATAL


class ToolFallbackChain:
    """Manages a fallback chain for a specific semantic operation.

    A fallback chain is an ordered list of strategies to try when the primary
    tool fails. Each strategy is a (tool_name, args_transform) pair.

    Example — file write fallback:
        chain = ToolFallbackChain("file_write")
        chain.add_fallback("file_write", {"mode": "append"})  # Try append mode
        chain.add_fallback("shell", lambda args: {"command": f"echo '{args.get('content', '')}' > {args.get('path', '')}"})
    """

    def __init__(self, primary_tool: str):
        self.primary_tool = primary_tool
        self._fallbacks: List[Tuple[str, Callable[[Dict], Dict]]] = []
        self._retry_count = 3
        self._retry_delay = 1.0  # seconds

    def set_retry_policy(self, count: int = 3, delay: float = 1.0) -> None:
        """Configure retry policy for transient failures.

        Args:
            count: Number of retries.
            delay: Base delay between retries (doubles each retry).
        """
        self._retry_count = count
        self._retry_delay = delay

    def add_fallback(self, tool_name: str,
                     args_transform: Optional[Callable[[Dict], Dict]] = None) -> None:
        """Add a fallback strategy.

        Args:
            tool_name: Name of the alternative tool to try.
            args_transform: Function to transform original args for this tool.
                           If None, passes args unchanged.
        """
        if args_transform is None:
            args_transform = lambda x: x  # noqa: E731
        self._fallbacks.append((tool_name, args_transform))

    async def execute(self, tool: BaseTool, args: Dict[str, Any],
                      available_tools: Dict[str, BaseTool]) -> FallbackResult:
        """Execute the tool with fallback chain.

        Args:
            tool: Primary tool to execute.
            args: Arguments for the tool.
            available_tools: All available tools for fallback.

        Returns:
            FallbackResult with success status and attempt history.
        """
        result = FallbackResult(success=False)

        # ── Primary attempt with retries ──────────────────────────────
        last_error = ""
        for attempt_i in range(self._retry_count + 1):
            start = time.time()
            try:
                output = await tool.execute(**args)
                duration = time.time() - start

                if output.startswith("Error:"):
                    last_error = output
                    ftype = classify_failure(output)
                    result.failure_type = ftype
                    result.attempts.append(FallbackAttempt(
                        tool_name=tool.name, success=False,
                        error=output, duration=duration,
                    ))
                    if attempt_i < self._retry_count and ftype == FailureType.TRANSIENT:
                        delay = self._retry_delay * (2 ** attempt_i)
                        logger.warning(
                            "Transient failure on %s (attempt %d/%d), retrying in %.1fs",
                            tool.name, attempt_i + 1, self._retry_count, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    break

                # Success
                result.success = True
                result.result = output
                result.attempts.append(FallbackAttempt(
                    tool_name=tool.name, success=True, duration=duration,
                ))
                return result

            except Exception as exc:
                last_error = str(exc)
                duration = time.time() - start
                if attempt_i < self._retry_count:
                    ftype = classify_failure(last_error)
                    if ftype == FailureType.TRANSIENT:
                        delay = self._retry_delay * (2 ** attempt_i)
                        await asyncio.sleep(delay)
                        continue
                result.attempts.append(FallbackAttempt(
                    tool_name=tool.name, success=False,
                    error=last_error, duration=duration,
                ))
                result.failure_type = classify_failure(last_error)

        # ── Fallback chain ────────────────────────────────────────────
        if result.failure_type == FailureType.FATAL:
            # Fatal errors — don't try fallbacks that will likely also fail
            return result

        for fallback_name, transform in self._fallbacks:
            fallback_tool = available_tools.get(fallback_name)
            if not fallback_tool:
                logger.debug("Fallback tool not available: %s", fallback_name)
                continue

            transformed_args = transform(args)
            start = time.time()

            try:
                output = await fallback_tool.execute(**transformed_args)
                duration = time.time() - start

                result.attempts.append(FallbackAttempt(
                    tool_name=fallback_name, success=not output.startswith("Error:"),
                    error=output if output.startswith("Error:") else "",
                    duration=duration,
                ))

                if not output.startswith("Error:"):
                    result.success = True
                    result.result = output
                    logger.info(
                        "Fallback succeeded: %s → %s", tool.name, fallback_name,
                    )
                    return result

            except Exception as exc:
                duration = time.time() - start
                error_msg = str(exc)
                result.attempts.append(FallbackAttempt(
                    tool_name=fallback_name, success=False,
                    error=error_msg, duration=duration,
                ))
                logger.warning("Fallback %s failed: %s", fallback_name, error_msg)

        # All fallbacks exhausted
        result.result = f"All fallbacks exhausted for {tool.name}. Last error: {last_error}"
        logger.error("All fallbacks exhausted for tool %s", tool.name)
        return result


class FallbackManager:
    """Manages fallback chains for all tools.

    Pre-configures common fallback chains and allows custom chains to be added.
    """

    def __init__(self):
        self._chains: Dict[str, ToolFallbackChain] = {}
        self._register_default_chains()

    def _register_default_chains(self) -> None:
        """Register default fallback chains for common tools."""
        # File write fallbacks
        file_write_chain = ToolFallbackChain("file_write")
        file_write_chain.set_retry_policy(count=2, delay=0.5)
        file_write_chain.add_fallback("shell", lambda args: {
            "command": f"cat > {args.get('path', '')} << 'NEXUS_EOF'\n{args.get('content', '')}\nNEXUS_EOF",
        })
        self._chains["file_write"] = file_write_chain

        # File read fallbacks
        file_read_chain = ToolFallbackChain("file_read")
        file_read_chain.set_retry_policy(count=1, delay=0.3)
        file_read_chain.add_fallback("shell", lambda args: {
            "command": f"cat {args.get('path', '')}",
        })
        self._chains["file_read"] = file_read_chain

        # Shell command fallbacks
        shell_chain = ToolFallbackChain("shell")
        shell_chain.set_retry_policy(count=2, delay=1.0)
        self._chains["shell"] = shell_chain

        # Search fallbacks
        search_chain = ToolFallbackChain("search")
        search_chain.set_retry_policy(count=1, delay=0.5)
        search_chain.add_fallback("shell", lambda args: {
            "command": f"grep -r {args.get('query', '')} {args.get('path', '.')}",
        })
        self._chains["search"] = search_chain

    def get_chain(self, tool_name: str) -> Optional[ToolFallbackChain]:
        """Get the fallback chain for a tool.

        Args:
            tool_name: Tool name.

        Returns:
            Fallback chain, or None if not registered.
        """
        return self._chains.get(tool_name)

    def add_chain(self, tool_name: str, chain: ToolFallbackChain) -> None:
        """Register a custom fallback chain.

        Args:
            tool_name: Tool name.
            chain: Fallback chain instance.
        """
        self._chains[tool_name] = chain

    async def execute_with_fallback(self, tool_name: str,
                                     args: Dict[str, Any],
                                     available_tools: Dict[str, BaseTool]) -> FallbackResult:
        """Execute a tool with its fallback chain.

        Args:
            tool_name: Tool to execute.
            args: Tool arguments.
            available_tools: All available tools.

        Returns:
            FallbackResult with success status and attempt history.
        """
        tool = available_tools.get(tool_name)
        if not tool:
            return FallbackResult(
                success=False,
                result=f"Tool not found: {tool_name}",
                failure_type=FailureType.NOT_FOUND,
            )

        chain = self.get_chain(tool_name)
        if not chain:
            # No fallback chain — execute directly
            try:
                output = await tool.execute(**args)
                return FallbackResult(
                    success=not output.startswith("Error:"),
                    result=output,
                    attempts=[FallbackAttempt(tool_name=tool_name, success=True)],
                )
            except Exception as exc:
                return FallbackResult(
                    success=False,
                    result=str(exc),
                    failure_type=classify_failure(str(exc)),
                    attempts=[FallbackAttempt(
                        tool_name=tool_name, success=False, error=str(exc),
                    )],
                )

        return await chain.execute(tool, args, available_tools)

    def get_stats(self) -> Dict[str, Any]:
        """Get fallback manager statistics."""
        return {
            "registered_chains": list(self._chains.keys()),
            "chain_count": len(self._chains),
        }
