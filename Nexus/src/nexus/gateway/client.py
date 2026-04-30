"""Gateway client for LiteLLM unified API."""
import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Chat message."""
    role: str
    content: str


@dataclass
class ChatCompletionResponse:
    """Chat completion response."""
    model: str
    content: str
    usage: Dict[str, int]
    finish_reason: str


class GatewayClient:
    """Client for LiteLLM gateway."""
    
    def __init__(self, base_url: str = "http://localhost:4000", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> ChatCompletionResponse:
        """Send chat completion request."""
        if not self._session:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        try:
            async with self._session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Gateway error {resp.status}: {text}")
                
                data = await resp.json()
                
                return ChatCompletionResponse(
                    model=data.get("model", model),
                    content=data["choices"][0]["message"]["content"],
                    usage=data.get("usage", {}),
                    finish_reason=data["choices"][0].get("finish_reason", "stop")
                )
        except aiohttp.ClientError as e:
            logger.error(f"Gateway request failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check gateway health."""
        if not self._session:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        
        try:
            async with self._session.get(f"{self.base_url}/health") as resp:
                return resp.status == 200
        except Exception:
            return False
    
    async def list_models(self) -> List[str]:
        """List available models."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        try:
            async with self._session.get(f"{self.base_url}/v1/models") as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []


async def get_gateway_client(base_url: str = "http://localhost:4000") -> GatewayClient:
    """Get gateway client instance."""
    return GatewayClient(base_url)