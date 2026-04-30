"""LLM client for Ollama interaction."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp

from nexus.agent.models import AgentConfig
from nexus.utils.retry_utils import async_retry_on_exception, async_with_timeout

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when Ollama communication fails."""
    pass


class OllamaClient:
    """Async client for Ollama API.

    Wraps Ollama's REST API with retry logic, streaming support,
    and structured JSON extraction from responses.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.base_url = self.config.ollama_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self, model: Optional[str] = None) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._get_timeout_for_model(model))
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _get_timeout_for_model(self, model: Optional[str] = None) -> int:
        """Get timeout based on model type for optimal performance."""
        model = model or self.config.coding_model
        model_lower = model.lower()
        if "coder" in model_lower or "code" in model_lower:
            return getattr(self.config, 'coding_timeout', self.config.llm_timeout)
        if "deepseek" in model_lower or "r1" in model_lower:
            return getattr(self.config, 'planning_timeout', self.config.llm_timeout)
        if "review" in model_lower:
            return getattr(self.config, 'review_timeout', self.config.llm_timeout)
        return self.config.llm_timeout

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a completion from Ollama.

        Args:
            prompt: The user prompt.
            model: Model name (defaults to coding_model from config).
            system: Optional system prompt.
            temperature: Sampling temperature override.
            max_tokens: Max tokens override.

        Returns:
            The generated text response.
        """
        return await self._generate_with_retry(
            prompt=prompt,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @async_retry_on_exception(
        exceptions=(OllamaError, aiohttp.ClientError),
        max_attempts=3,
        min_wait=1,
        max_wait=10,
    )
    async def _generate_with_retry(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Internal generate with tenacity retry decorator."""
        model = model or self.config.coding_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        timeout = self._get_timeout_for_model(model)

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        session = await self._get_session(model)
        url = f"{self.base_url}/api/generate"

        try:
            resp = await asyncio.wait_for(
                session.post(url, json=payload),
                timeout=timeout,
            )
            async with resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise OllamaError(
                        f"Ollama returned {resp.status}: {body[:200]}"
                    )
                data = await resp.json()
                return data.get("response", "")
        except asyncio.TimeoutError:
            raise OllamaError(f"Ollama request timed out after {timeout}s")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Chat completion with message history.

        Args:
            messages: List of {role, content} message dicts.
            model: Model name override.
            temperature: Temperature override.

        Returns:
            The assistant's response text.
        """
        return await self._chat_with_retry(
            messages=messages,
            model=model,
            temperature=temperature,
        )

    @async_retry_on_exception(
        exceptions=(OllamaError, aiohttp.ClientError),
        max_attempts=3,
        min_wait=1,
        max_wait=10,
    )
    async def _chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Internal chat with tenacity retry decorator."""
        model = model or self.config.coding_model
        temperature = temperature if temperature is not None else self.config.temperature
        timeout = self._get_timeout_for_model(model)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        session = await self._get_session(model)
        url = f"{self.base_url}/api/chat"

        try:
            resp = await asyncio.wait_for(
                session.post(url, json=payload),
                timeout=timeout,
            )
            async with resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise OllamaError(
                        f"Ollama chat returned {resp.status}: {body[:200]}"
                    )
                data = await resp.json()
                return data.get("message", {}).get("content", "")
        except asyncio.TimeoutError:
            raise OllamaError(f"Ollama chat request timed out after {timeout}s")

    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream a generation token by token.

        Yields individual tokens as they arrive from Ollama.
        """
        model = model or self.config.coding_model

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": self.config.temperature,
            },
        }
        if system:
            payload["system"] = system

        session = await self._get_session(model)
        url = f"{self.base_url}/api/generate"

        async with session.post(url, json=payload) as resp:
            async for line in resp.content:
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

    async def list_models(self) -> List[Dict[str, Any]]:
        """List locally available Ollama models."""
        session = await self._get_session(self.config.coding_model)
        try:
            async with session.get(f"{self.base_url}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("models", [])
        except aiohttp.ClientError:
            pass
        return []

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream a chat completion token by token.

        Like chat(), but yields tokens as they arrive rather than
        waiting for the complete response.  Used by ChatSession for
        live terminal display.

        Args:
            messages: List of {role, content} message dicts.
            model: Model name override.

        Yields:
            Individual text tokens.
        """
        model = model or self.config.coding_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self.config.temperature,
            },
        }

        session = await self._get_session(model)
        url = f"{self.base_url}/api/chat"

        async with session.post(url, json=payload) as resp:
            async for line in resp.content:
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

    async def is_available(self) -> bool:
        """Check if Ollama is running and responsive."""
        try:
            session = await self._get_session(self.config.coding_model)
            async with session.get(self.base_url) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, Exception):
            return False


def extract_json(text: str) -> Optional[Any]:
    """Extract JSON from LLM output that may contain markdown or explanation.

    Handles common patterns:
    - ```json ... ```
    - Raw JSON objects/arrays
    - JSON embedded in explanation text
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code blocks
    for marker in ("```json", "```"):
        if marker in text:
            start = text.find(marker) + len(marker)
            end = text.find("```", start)
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

    # Try finding JSON object
    for open_char, close_char in [("{", "}"), ("[", "]")]:
        start = text.find(open_char)
        if start == -1:
            continue
        # Find matching close bracket (handle nesting)
        depth = 0
        for i in range(start, len(text)):
            if text[i] == open_char:
                depth += 1
            elif text[i] == close_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break

    return None
