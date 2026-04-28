"""Verify patches - apply, test, and score."""
import asyncio
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from .patch_generator import PatchGenerator


logger = logging.getLogger(__name__)


class PatchVerifier:
    """Verify patches by applying and running tests."""
    
    def __init__(
        self,
        repo_path: Path,
        test_command: str = "pytest",
        timeout: int = 120
    ):
        self.repo_path = Path(repo_path)
        self.test_command = test_command
        self.timeout = timeout
    
    async def verify_patch(
        self,
        patch: str,
        patch_id: str = "unknown"
    ) -> Dict[str, Any]:
        """Apply patch and run tests, return result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_path = Path(tmpdir) / "repo"
            
            try:
                shutil.copytree(self.repo_path, sandbox_path)
            except Exception as e:
                return self._error_result(patch_id, patch, f"Copy failed: {e}", "error")
            
            # Write patch to file
            patch_file = sandbox_path / "fix.patch"
            patch_file.write_text(patch)
            
            # Try to apply patch
            apply_result = self._apply_patch(patch, sandbox_path)
            if not apply_result["success"]:
                return self._error_result(patch_id, patch, apply_result["error"], "apply_failed")
            
            # Run tests
            test_result = await self._run_tests(sandbox_path)
            
            return {
                "patch_id": patch_id,
                "patch": patch,
                "success": test_result["passed"],
                "returncode": test_result["returncode"],
                "stdout": test_result["stdout"],
                "stderr": test_result["stderr"],
                "score": 0.0,
                "error": test_result.get("error")
            }
    
    def _apply_patch(self, patch: str, repo_copy: Path) -> Dict[str, Any]:
        """Apply a git-style patch."""
        patch_file = repo_copy / "fix.patch"
        patch_file.write_text(patch)
        
        # Try git apply first
        proc = subprocess.run(
            ["git", "apply", "--index", "fix.patch"],
            cwd=repo_copy,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if proc.returncode == 0:
            return {"success": True}
        
        # Try direct apply for code blocks
        if "```python" in patch:
            return self._apply_code_block(patch, repo_copy)
        
        return {"success": False, "error": proc.stderr or "Could not apply patch"}
    
    def _apply_code_block(self, patch: str, repo_copy: Path) -> Dict[str, Any]:
        """Apply a code block patch (not git diff)."""
        import re
        
        # Extract code blocks
        code_blocks = re.findall(r"```python\s*(.*?)```", patch, re.DOTALL)
        
        if not code_blocks:
            return {"success": False, "error": "No code block found"}
        
        # Try to find and update the target file
        for i, code in enumerate(code_blocks):
            lines = code.strip().split("\n")
            if "# file:" in code.lower() or "file:" in code.lower():
                file_match = re.search(r'file:\s*"?([^"\s]+)"?', code, re.IGNORECASE)
                if file_match:
                    target = repo_copy / file_match.group(1)
                    target.write_text(code)
                    
        return {"success": True}
    
    async def _run_tests(self, repo_copy: Path) -> Dict[str, Any]:
        """Run test command in sandbox."""
        try:
            proc = await asyncio.create_subprocess_shell(
                self.test_command,
                cwd=repo_copy,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout
                )
                
                passed = proc.returncode == 0
                return {
                    "passed": passed,
                    "returncode": proc.returncode,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else ""
                }
                
            except asyncio.TimeoutExpired:
                proc.kill()
                await proc.communicate()
                return {
                    "passed": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": "Test timeout",
                    "error": "timeout"
                }
                
        except Exception as e:
            return {
                "passed": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "error": str(e)
            }
    
    def _error_result(
        self,
        patch_id: str,
        patch: str,
        error: str,
        error_type: str
    ) -> Dict[str, Any]:
        """Generate error result."""
        return {
            "patch_id": patch_id,
            "patch": patch,
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": error,
            "score": 0.0,
            "error": error_type
        }
    
    def score_patch(self, verify_result: Dict[str, Any]) -> float:
        """Score a verified patch."""
        if not verify_result.get("success", False):
            return 0.0
        
        score = 1.0
        
        # Penalize warnings
        stderr = verify_result.get("stderr", "")
        if "warning" in stderr.lower():
            score -= 0.1
        
        # Penalize large output
        stdout = verify_result.get("stdout", "")
        if len(stdout) > 5000:
            score -= 0.05
        
        # Penalize errors
        if verify_result.get("error"):
            score -= 0.2
        
        return max(0.0, score)


class PatchSelector:
    """Select the best patch from verified candidates."""
    
    def __init__(self, verifier: PatchVerifier):
        self.verifier = verifier
    
    async def select_best(
        self,
        patches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify all patches and select the best."""
        verified = []
        
        for patch in patches:
            result = await self.verifier.verify_patch(
                patch["content"],
                patch["id"]
            )
            result["score"] = self.verifier.score_patch(result)
            verified.append(result)
        
        # Sort by score
        verified.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "candidates": verified,
            "best": verified[0] if verified else None,
            "passed_count": sum(1 for v in verified if v["score"] > 0.5)
        }


async def create_verifier(
    repo_path: Path,
    test_command: str = "pytest"
) -> PatchVerifier:
    """Factory function for verifier."""
    return PatchVerifier(repo_path, test_command)