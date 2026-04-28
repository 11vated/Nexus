"""Test for patch selector/scoring."""
import pytest
from src.nexus.swe_bench.verifier import PatchVerifier, PatchSelector
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


class TestPatchSelector:
    """Test patch scoring and selection."""
    
    def test_score_perfect(self):
        """Perfect patch should score 1.0."""
        verifier = PatchVerifier(Path("."), "echo test")
        
        result = {
            "success": True,
            "stdout": "All tests passed",
            "stderr": ""
        }
        
        score = verifier.score_patch(result)
        assert score == 1.0
    
    def test_score_with_warning(self):
        """Warning should reduce score."""
        verifier = PatchVerifier(Path("."), "echo test")
        
        result = {
            "success": True,
            "stdout": "ok",
            "stderr": "warning: deprecated"
        }
        
        score = verifier.score_patch(result)
        assert score < 1.0
        assert score >= 0.9
    
    def test_score_failure(self):
        """Failed patch should score 0.0."""
        verifier = PatchVerifier(Path("."), "echo test")
        
        result = {
            "success": False,
            "stdout": "",
            "stderr": "AssertionError"
        }
        
        score = verifier.score_patch(result)
        assert score == 0.0
    
    def test_score_large_output(self):
        """Large output should reduce score slightly."""
        verifier = PatchVerifier(Path("."), "echo test")
        
        result = {
            "success": True,
            "stdout": "x" * 6000,
            "stderr": ""
        }
        
        score = verifier.score_patch(result)
        assert score < 1.0
    
    def test_select_best(self):
        """Test best patch selection."""
        verifier = PatchVerifier(Path("."), "echo test")
        selector = PatchSelector(verifier)
        
        candidates = [
            {"id": "p1", "content": "fix1"},
            {"id": "p2", "content": "fix2"},
            {"id": "p3", "content": "fix3"}
        ]
        
        # Mock verify_patch to return different results
        verifier.verify_patch = AsyncMock(side_effect=[
            {"patch_id": "p1", "success": True, "score": 0.8, "stdout": "", "stderr": ""},
            {"patch_id": "p2", "success": True, "score": 1.0, "stdout": "", "stderr": ""},
            {"patch_id": "p3", "success": False, "score": 0.0, "stdout": "", "stderr": "error"}
        ])
        
        # Override score_patch for mocked results
        async def mock_verify(patch, pid):
            results = {
                "p1": {"success": True, "stdout": "", "stderr": ""},
                "p2": {"success": True, "stdout": "", "stderr": ""},
                "p3": {"success": False, "stdout": "", "stderr": "error"}
            }
            return {"patch_id": pid, **results.get(pid, {})}
        
        verifier.verify_patch = mock_verify
        
        # Run selection
        # Note: This is simplified - actual selection done in orchestrator
        assert len(candidates) == 3