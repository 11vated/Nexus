"""Generate multiple candidate patches for SWE-bench issues."""
import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional

from ..gateway.client import GatewayClient


logger = logging.getLogger(__name__)


class PatchGenerator:
    """Generate candidate patches with different temperatures and strategies."""
    
    def __init__(
        self,
        gateway_client: GatewayClient,
        model_name: str,
        num_patches: int = 8,
        base_temp: float = 0.3,
        max_temp: float = 0.7
    ):
        self.gateway = gateway_client
        self.model = model_name
        self.num_patches = num_patches
        self.base_temp = base_temp
        self.max_temp = max_temp
    
    async def generate_patches(
        self,
        issue_text: str,
        code_context: str = None,
        file_structure: str = None
    ) -> List[Dict[str, Any]]:
        """Generate num_patches candidate patches with varied temperatures."""
        patches = []
        
        base_prompt = self._build_base_prompt(issue_text, code_context, file_structure)
        
        for i in range(self.num_patches):
            temp = self.base_temp + (i / self.num_patches) * (self.max_temp - self.base_temp)
            prompt = self._apply_strategy(base_prompt, i)
            
            try:
                response = await self.gateway.chat_completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temp,
                    max_tokens=2000
                )
                
                patches.append({
                    "id": f"patch_{i+1}",
                    "content": response.content,
                    "temperature": temp,
                    "strategy": self._get_strategy_name(i),
                    "score": 0.0,
                    "verified": False
                })
                
            except Exception as e:
                logger.warning(f"Failed to generate patch {i+1}: {e}")
                patches.append({
                    "id": f"patch_{i+1}",
                    "content": "",
                    "temperature": temp,
                    "strategy": self._get_strategy_name(i),
                    "score": 0.0,
                    "verified": False,
                    "error": str(e)
                })
        
        return [p for p in patches if p["content"]]
    
    def _build_base_prompt(
        self,
        issue_text: str,
        code_context: str,
        file_structure: str
    ) -> str:
        """Build the base prompt for patch generation."""
        context_section = ""
        if code_context:
            context_section = f"\nRelevant code:\n{code_context}\n"
        
        structure_section = ""
        if file_structure:
            structure_section = f"\nRepository structure:\n{file_structure}\n"
        
        return f"""You are an expert software engineer.
Issue to fix:
{issue_text}
{context_section}{structure_section}
Generate a unified diff patch to fix this issue. Output only the patch:
```diff
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
+added line
-removed line
```
Or in code format:
```python
# fixed code
```"""
    
    def _apply_strategy(self, base_prompt: str, index: int) -> str:
        """Apply a generation strategy for diversity."""
        strategies = [
            "",  # Baseline
            "\n\nThink step by step about the root cause.",
            "\n\nConsider edge cases and potential side effects.",
            "\n\nSimplify the solution as much as possible.",
            "\n\nOptimize for performance.",
            "\n\nUse a different approach than you might normally consider.",
            "\n\nWrite the minimal fix that solves this specific issue.",
            "\n\nConsider alternative implementations."
        ]
        
        strategy = strategies[index % len(strategies)]
        return base_prompt + strategy
    
    def _get_strategy_name(self, index: int) -> str:
        """Get strategy name for diversity tracking."""
        names = [
            "baseline",
            "step_by_step",
            "edge_cases",
            "simplified",
            "optimized",
            "different_approach",
            "minimal",
            "alternative"
        ]
        return names[index % len(names)]


async def create_patch_generator(
    gateway_client: GatewayClient,
    model_name: str = "qwen2.5-coder:14b",
    num_patches: int = 8
) -> PatchGenerator:
    """Factory function for patch generator."""
    return PatchGenerator(
        gateway_client=gateway_client,
        model_name=model_name,
        num_patches=num_patches
    )