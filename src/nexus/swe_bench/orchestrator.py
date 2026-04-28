"""SWE-bench orchestrator for multi-patch generation and verification."""
import asyncio
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..core.patch_verification import CandidatePatch, PatchStatus, VerificationScore
from ..gateway.client import GatewayClient


logger = logging.getLogger(__name__)


class TestResult(Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class PatchTestResult:
    """Result of testing a patch."""
    patch: str
    result: TestResult
    score: float
    stdout: str
    stderr: str
    returncode: int
    error: Optional[str] = None


@dataclass
class SWEBenchResult:
    """Result of SWE-bench resolution."""
    issue: str
    repo_path: Path
    best_patch: Optional[str] = None
    best_score: float = 0.0
    candidates_tested: int = 0
    passed: bool = False
    details: List[PatchTestResult] = field(default_factory=list)


class SWEBenchOrchestrator:
    """Orchestrate SWE-bench issue resolution."""
    
    def __init__(
        self,
        gateway_client: GatewayClient,
        model_name: str,
        workspace: Path = None,
        num_patches: int = 8,
        base_temp: float = 0.3,
        max_temp: float = 0.7
    ):
        self.gateway = gateway_client
        self.model = model_name
        self.workspace = workspace or Path.cwd()
        self.num_patches = num_patches
        self.base_temp = base_temp
        self.max_temp = max_temp
    
    async def resolve_issue(
        self,
        issue_text: str,
        repo_path: Path,
        test_command: str = "pytest",
        context: str = None
    ) -> SWEBenchResult:
        """Resolve a SWE-bench issue."""
        logger.info(f"Resolving issue: {issue_text[:100]}...")
        
        # Generate candidate patches
        patches = await self._generate_patches(issue_text, context)
        
        # Test each patch
        results = []
        for i, patch in enumerate(patches):
            logger.info(f"Testing patch {i+1}/{len(patches)}...")
            test_result = await self._test_patch(patch, repo_path, test_command)
            results.append(test_result)
            
            # Score the patch
            score = self._score_patch(test_result)
            test_result.score = score
        
        # Select best
        results.sort(key=lambda x: x.score, reverse=True)
        best = results[0] if results else None
        
        return SWEBenchResult(
            issue=issue_text[:200],
            repo_path=repo_path,
            best_patch=best.patch if best else None,
            best_score=best.score if best else 0.0,
            candidates_tested=len(patches),
            passed=best.score > 0.5 if best else False,
            details=results
        )
    
    async def _generate_patches(
        self,
        issue_text: str,
        context: str = None
    ) -> List[str]:
        """Generate candidate patches."""
        base_prompt = f"""You are an expert software engineer.
Fix this issue:

{issue_text}

{context or ''}

Generate a unified diff patch to fix this issue. Output only the patch in this format:
```python
# your code here
```
Or as a git diff:
```diff
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
+added line
"""
        
        patches = []
        
        for i in range(self.num_patches):
            temp = self.base_temp + (i / self.num_patches) * (self.max_temp - self.base_temp)
            
            prompt = base_prompt
            if i > 0:
                variations = [
                    "",
                    "\nThink step by step.",
                    "\nConsider edge cases.",
                    "\nSimplify the solution.",
                    "\nOptimize for performance.",
                    "\nUse a different approach.",
                    "\nWrite minimal fix.",
                    "\nConsider alternatives."
                ]
                prompt = base_prompt + variations[i % len(variations)]
            
            try:
                resp = await self.gateway.chat_completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temp,
                    max_tokens=2000
                )
                patches.append(resp.content)
            except Exception as e:
                logger.warning(f"Failed to generate patch {i}: {e}")
                patches.append("")
        
        return [p for p in patches if p.strip()]
    
    async def _test_patch(
        self,
        patch: str,
        repo_path: Path,
        test_command: str
    ) -> PatchTestResult:
        """Test a patch in a sandbox."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_path = Path(tmpdir) / "repo"
            
            try:
                shutil.copytree(repo_path, sandbox_path)
            except Exception as e:
                return PatchTestResult(
                    patch=patch,
                    result=TestResult.ERROR,
                    score=0.0,
                    stdout="",
                    stderr="",
                    returncode=-1,
                    error=f"Failed to copy repo: {e}"
                )
            
            # Try to apply patch
            patch_file = sandbox_path / ".patch"
            patch_file.write_text(patch)
            
            proc = subprocess.run(
                ["git", "apply", "--index", "patch"],
                cwd=sandbox_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if proc.returncode != 0:
                return PatchTestResult(
                    patch=patch,
                    result=TestResult.ERROR,
                    score=0.0,
                    stdout="",
                    stderr=proc.stderr,
                    returncode=proc.returncode,
                    error="Patch apply failed"
                )
            
            # Run tests
            try:
                proc = subprocess.run(
                    test_command.split(),
                    cwd=sandbox_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    shell=True
                )
                
                if proc.returncode == 0:
                    result = TestResult.PASSED
                else:
                    result = TestResult.FAILED
                    
            except subprocess.TimeoutExpired:
                result = TestResult.TIMEOUT
                proc = None
            except Exception as e:
                result = TestResult.ERROR
                proc = None
            
            return PatchTestResult(
                patch=patch,
                result=result,
                score=0.0,
                stdout=proc.stdout if proc else "",
                stderr=proc.stderr if proc else "",
                returncode=proc.returncode if proc else -1
            )
    
    def _score_patch(self, test_result: PatchTestResult) -> float:
        """Score a patch test result."""
        if test_result.result == TestResult.PASSED:
            base = 1.0
        elif test_result.result == TestResult.FAILED:
            base = 0.0
        else:
            base = 0.0
        
        # Penalize warnings
        if "warning" in test_result.stderr.lower():
            base -= 0.1
        
        # Penalize large output
        if len(test_result.stdout) > 5000:
            base -= 0.05
        
        return max(0.0, base)


async def create_orchestrator(
    model_name: str = "qwen2.5-coder:14b",
    base_url: str = "http://localhost:4000",
    workspace: Path = None
) -> SWEBenchOrchestrator:
    """Create SWE-bench orchestrator."""
    gateway = GatewayClient(base_url)
    return SWEBenchOrchestrator(
        gateway_client=gateway,
        model_name=model_name,
        workspace=workspace
    )