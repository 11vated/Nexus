"""Multi-patch generator for SWE-bench superiority."""
import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum


logger = logging.getLogger(__name__)


class PatchStatus(Enum):
    PENDING = "pending"
    GENERATED = "generated"
    VERIFIED = "verified"
    FAILED = "failed"
    SELECTED = "selected"


@dataclass
class CandidatePatch:
    """A candidate patch for verification."""
    id: str
    content: str
    status: PatchStatus = PatchStatus.PENDING
    score: float = 0.0
    syntax_valid: bool = False
    tests_passed: bool = False
    test_output: str = ""
    side_effects: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class VerificationScore:
    """Score breakdown for a patch."""
    test_pass_rate: float = 0.0
    syntax_score: float = 0.0
    side_effect_score: float = 0.0
    security_score: float = 0.0
    total: float = 0.0


class MultiPatchGenerator:
    """Generate multiple candidate patches for selection."""
    
    def __init__(
        self,
        model_callback: Callable,
        base_temperature: float = 0.3,
        max_temperature: float = 0.7,
        num_candidates: int = 8
    ):
        self.model_callback = model_callback
        self.base_temperature = base_temperature
        self.max_temperature = max_temperature
        self.num_candidates = num_candidates
    
    async def generate_patches(
        self,
        issue_description: str,
        code_context: str = None
    ) -> List[CandidatePatch]:
        """Generate multiple candidate patches."""
        patches = []
        
        prompts = self._build_generation_prompts(issue_description, code_context)
        
        for i, prompt in enumerate(prompts):
            temp = self.base_temperature + (i / self.num_candidates) * (self.max_temperature - self.base_temperature)
            
            try:
                response = await self.model_callback(
                    prompt=prompt,
                    temperature=temp,
                    max_tokens=2000
                )
                
                patch = CandidatePatch(
                    id=f"candidate_{i+1}",
                    content=response,
                    status=PatchStatus.GENERATED
                )
                patches.append(patch)
                
            except Exception as e:
                logger.warning(f"Failed to generate patch {i+1}: {e}")
                patches.append(CandidatePatch(
                    id=f"candidate_{i+1}",
                    content="",
                    status=PatchStatus.FAILED,
                    error=str(e)
                ))
        
        return patches
    
    def _build_generation_prompts(
        self,
        issue_description: str,
        code_context: str = None
    ) -> List[str]:
        """Build different prompts for diversity."""
        base = f"""You are an expert software engineer. Fix this issue:

{issue_description}

{code_context or ''}

Provide a complete patch in unified diff format:

```python
# Your fix here
```
"""
        
        variations = [
            base,  # Baseline
            base + "\n\nThink step by step and explain your reasoning first.",
            base + "\n\nConsider edge cases and potential side effects.",
            base + "\n\nSimplify the solution as much as possible.",
            base + "\n\nOptimize for performance.",
            base + "\n\nUse a different approach than you might normally consider.",
            base + "\n\nWrite the minimal fix that solves this specific issue.",
            base + "\n\nConsider alternative implementations."
        ]
        
        return variations[:self.num_candidates]


class PatchVerifier:
    """Verify patches for selection."""
    
    def __init__(
        self,
        test_runner: Callable = None,
        syntax_checker: Callable = None
    ):
        self.test_runner = test_runner
        self.syntax_checker = syntax_checker
    
    async def verify_patch(
        self,
        patch: CandidatePatch,
        test_command: str = "pytest"
    ) -> VerificationScore:
        """Verify a patch and return score."""
        score = VerificationScore(
            syntax_score=0.2,  # Default
            test_pass_rate=0.0,
            side_effect_score=0.2,
            security_score=0.2,
            total=0.6
        )
        
        # Syntax check
        if self.syntax_checker:
            syntax_valid = await self._check_syntax(patch.content)
            patch.syntax_valid = syntax_valid
            score.syntax_score = 0.2 if syntax_valid else 0.0
        
        # Tests check
        if self.test_runner and patch.content:
            test_result = await self._run_tests(patch, test_command)
            patch.tests_passed = test_result["passed"]
            patch.test_output = test_result["output"]
            
            if test_result["total"] > 0:
                score.test_pass_rate = test_result["passed"] / test_result["total"]
        
        # Side effects check
        side_effects = await self._check_side_effects(patch.content)
        patch.side_effects = side_effects
        score.side_effect_score = 0.2 if not side_effects else 0.0
        
        # Security check (basic)
        if not await self._check_security(patch.content):
            score.security_score = 0.0
        
        # Calculate total
        score.total = (
            score.syntax_score +
            score.test_pass_rate * 0.4 +
            score.side_effect_score +
            score.security_score
        )
        
        patch.score = score.total
        patch.status = PatchStatus.VERIFIED if score.total >= 0.6 else PatchStatus.FAILED
        
        return score
    
    async def _check_syntax(self, content: str) -> bool:
        """Check if code is syntactically valid."""
        import ast
        
        try:
            ast.parse(content)
            return True
        except SyntaxError:
            return False
    
    async def _run_tests(self, patch: CandidatePatch, test_command: str) -> Dict[str, Any]:
        """Run tests for a patch."""
        # This would apply the patch and run tests in sandbox
        # Simplified for now
        return {
            "passed": 0,
            "total": 0,
            "output": ""
        }
    
    async def _check_side_effects(self, content: str) -> List[str]:
        """Check for unwanted side effects."""
        side_effects = []
        
        # Check for dangerous operations
        dangerous_patterns = [
            "rm -rf",
            "del /",
            "format c:",
            "__import__('os').system"
        ]
        
        for pattern in dangerous_patterns:
            if pattern in content.lower():
                side_effects.append(f"Dangerous pattern: {pattern}")
        
        # Check for large deletions
        lines = content.split("\n")
        deletions = [l for l in lines if l.startswith("-") and len(l) > 50]
        if len(deletions) > 10:
            side_effects.append(f"Large deletion: {len(deletions)} lines removed")
        
        return side_effects
    
    async def _check_security(self, content: str) -> bool:
        """Basic security check."""
        dangerous = ["eval(", "exec(", "os.system", "subprocess.call(['rm'"]
        return not any(d in content for d in dangerous)


class HybridVerifier:
    """Hybrid verification combining test execution and LLM judgment."""
    
    def __init__(
        self,
        test_runner: Callable,
        llm_judge: Callable
    ):
        self.test_runner = test_runner
        self.llm_judge = llm_judge
    
    async def verify_with_llm_judgment(
        self,
        patch: CandidatePatch,
        original_code: str,
        issue_description: str
    ) -> float:
        """Use LLM to judge semantic correctness."""
        # First run tests
        test_result = await self._run_tests(patch)
        
        # Then ask LLM to judge
        judge_prompt = f"""Evaluate this patch for correctness:

Issue: {issue_description}

Original code:
{original_code[:1000]}

Patch:
{patch.content[:1000]}

Test results: {test_result['output'][:500]}

Is this patch correct? Does it solve the issue without introducing bugs?
Provide a score from 0.0 to 1.0 and brief explanation."""

        try:
            judgment = await self.llm_judge(prompt=judge_prompt)
            
            # Parse score from response
            if "1.0" in judgment or "perfect" in judgment.lower():
                return 1.0
            elif "0." in judgment:
                try:
                    score_part = judgment[judgment.find("0."):judgment.find("0.")+3]
                    return float(score_part)
                except:
                    return 0.5
            else:
                return 0.5
        except:
            return test_result["passed"] / max(test_result["total"], 1)
    
    async def _run_tests(self, patch: CandidatePatch) -> Dict[str, Any]:
        """Run tests (simplified)."""
        return {"passed": 0, "total": 1, "output": ""}


class BestPatchSelector:
    """Select the best patch from candidates."""
    
    def __init__(self, verifier: PatchVerifier = None):
        self.verifier = verifier or PatchVerifier()
    
    async def select_best(
        self,
        patches: List[CandidatePatch],
        test_command: str = "pytest"
    ) -> Optional[CandidatePatch]:
        """Select the best patch from verified candidates."""
        best = None
        best_score = -1
        
        for patch in patches:
            if patch.status == PatchStatus.PENDING:
                await self.verifier.verify_patch(patch, test_command)
            
            if patch.score > best_score and patch.status == PatchStatus.VERIFIED:
                best_score = patch.score
                best = patch
        
        if best:
            best.status = PatchStatus.SELECTED
        
        return best
    
    async def select_with_fallback(
        self,
        patches: List[CandidatePatch],
        test_command: str = "pytest"
    ) -> Optional[CandidatePatch]:
        """Select best with fallback to highest-scoring verified, then highest-temperature generated."""
        # First try to select by score
        selected = await self.select_best(patches, test_command)
        if selected:
            return selected
        
        # Fallback: highest temperature patch
        sorted_patches = sorted(
            [p for p in patches if p.content],
            key=lambda p: p.content.length()
        )
        
        return sorted_patches[0] if sorted_patches else None