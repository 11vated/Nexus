"""Agent verification loop - the feedback mechanism for SWE-bench."""
import subprocess
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    VERIFIED = "verified"
    SYNTAX_ERROR = "syntax_error"
    TEST_FAILURE = "test_failure"
    RUNTIME_ERROR = "runtime_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class VerificationResult:
    status: VerificationStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    attempts: int = 1


class CodeVerifier:
    """Verify code changes with execution feedback."""
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.cwd()
        self.max_attempts = 3
    
    def write_and_verify(self, file_path: Path, content: str) -> VerificationResult:
        """Write file and verify with syntax check + tests."""
        file_path = Path(file_path)
        
        # Write the file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        
        # 1. Syntax check
        syntax_result = self._check_syntax(file_path)
        if syntax_result:
            return VerificationResult(
                status=VerificationStatus.SYNTAX_ERROR,
                message=f"Syntax error: {syntax_result}"
            )
        
        # 2. Run unit tests
        test_result = self._run_tests(file_path.parent)
        if test_result:
            return VerificationResult(
                status=VerificationStatus.TEST_FAILURE,
                message=f"Test failure: {test_result}"
            )
        
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            message="Code verified successfully"
        )
    
    def _check_syntax(self, file_path: Path) -> Optional[str]:
        """Check syntax of file."""
        suffix = file_path.suffix
        
        if suffix == ".py":
            return self._check_python_syntax(file_path)
        elif suffix in (".ts", ".tsx", ".js", ".jsx"):
            return self._check_js_ts_syntax(file_path)
        elif suffix == ".rs":
            return self._check_rust_syntax(file_path)
        
        return None
    
    def _check_python_syntax(self, file_path: Path) -> Optional[str]:
        """Check Python syntax."""
        try:
            result = subprocess.run(
                ["python", "-m", "py_compile", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return result.stderr
        except subprocess.TimeoutExpired:
            return "Syntax check timed out"
        except FileNotFoundError:
            return "Python not found"
        
        return None
    
    def _check_js_ts_syntax(self, file_path: Path) -> Optional[str]:
        """Check JS/TS syntax (requires Node)."""
        try:
            # Use tsc --noEmit if available, otherwise use node --check
            if file_path.suffix in (".ts", ".tsx"):
                check_cmd = ["npx", "tsc", "--noEmit", "--skipLibCheck"]
            else:
                check_cmd = ["node", "--check"]
            
            result = subprocess.run(
                check_cmd + [str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=file_path.parent
            )
            if result.returncode != 0:
                return result.stderr
        except subprocess.TimeoutExpired:
            return "Syntax check timed out"
        except FileNotFoundError:
            pass  # Node not available, skip
        
        return None
    
    def _check_rust_syntax(self, file_path: Path) -> Optional[str]:
        """Check Rust syntax."""
        try:
            result = subprocess.run(
                ["rustc", "--emit=metadata", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return None
    
    def _run_tests(self, test_dir: Path) -> Optional[str]:
        """Run tests in directory."""
        test_dir = Path(test_dir)
        
        # Check for test files
        has_pytest = (test_dir / "test_*.py").exists() or (test_dir / "*_test.py").exists()
        has_npm = (test_dir / "package.json").exists()
        
        if has_pytest:
            return self._run_pytest(test_dir)
        elif has_npm:
            return self._run_npm_tests(test_dir)
        
        return None
    
    def _run_pytest(self, test_dir: Path) -> Optional[str]:
        """Run pytest."""
        try:
            result = subprocess.run(
                ["pytest", "--maxfail=1", "--tb=short", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=test_dir
            )
            if result.returncode != 0:
                return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return "Test execution timed out"
        except FileNotFoundError:
            pass
        
        return None
    
    def _run_npm_tests(self, test_dir: Path) -> Optional[str]:
        """Run npm tests."""
        try:
            result = subprocess.run(
                ["npm", "test", "--", "--maxfail=1"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=test_dir
            )
            if result.returncode != 0:
                return result.stdout + result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return None
    
    def verify_with_output(self, file_path: Path, content: str, 
                          expected_output: str = None) -> VerificationResult:
        """Write, verify, and optionally run to check output."""
        # First do basic verification
        result = self.write_and_verify(file_path, content)
        
        if result.status != VerificationStatus.VERIFIED:
            return result
        
        # Try to run and capture output
        output_result = self._capture_output(file_path)
        
        if expected_output and output_result:
            if expected_output.strip() in output_result.strip():
                return result
            return VerificationResult(
                status=VerificationStatus.RUNTIME_ERROR,
                message=f"Output mismatch. Expected: {expected_output}, Got: {output_result[:200]}"
            )
        
        return result
    
    def _capture_output(self, file_path: Path) -> Optional[str]:
        """Capture stdout/stderr from running the file."""
        suffix = file_path.suffix
        
        try:
            if suffix == ".py":
                result = subprocess.run(
                    ["python", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=file_path.parent
                )
                return result.stdout + result.stderr
            elif suffix == ".js":
                result = subprocess.run(
                    ["node", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=file_path.parent
                )
                return result.stdout + result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return None


class IterativeAgent:
    """Agent with verification loop - implements SWE-bench workflow."""
    
    def __init__(self, verifier: CodeVerifier = None):
        self.verifier = verifier or CodeVerifier()
        self.max_iterations = 5
    
    def run_with_verification(
        self,
        task: str,
        write_fn
    ) -> VerificationResult:
        """Run task with verification loop."""
        attempts = 0
        
        while attempts < self.max_iterations:
            attempts += 1
            logger.info(f"Attempt {attempts}/{self.max_iterations}: {task}")
            
            # Developer creates/modifies code
            result = write_fn(attempt=attempts)
            
            if isinstance(result, tuple):
                file_path, content = result
            else:
                # Assume the callback already wrote the file
                file_path = None
                content = None
            
            # If we have file path, verify it
            if file_path and content:
                verify_result = self.verifier.write_and_verify(file_path, content)
                
                if verify_result.status == VerificationStatus.VERIFIED:
                    logger.info(f"Verified on attempt {attempts}")
                    verify_result.attempts = attempts
                    return verify_result
                
                logger.warning(f"Verification failed: {verify_result.message}")
            
            # Small delay before retry
            time.sleep(0.5)
        
        return VerificationResult(
            status=VerificationStatus.UNKNOWN_ERROR,
            message=f"Failed after {self.max_iterations} attempts",
            attempts=attempts
        )


# Global verifier instance
code_verifier = CodeVerifier()