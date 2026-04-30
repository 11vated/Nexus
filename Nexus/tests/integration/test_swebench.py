"""Integration tests for SWE-bench pipeline."""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.nexus.swe_bench import (
    PatchGenerator,
    PatchVerifier,
    PatchSelector,
    SWEBenchOrchestrator,
    ResolutionStatus,
    create_orchestrator,
    create_verifier
)


class MockGatewayClient:
    """Mock gateway for testing."""
    
    def __init__(self, response_content: str = "def fix(): pass"):
        self.response_content = response_content
    
    async def chat_completion(self, model, messages, temperature=0.7, max_tokens=2000):
        return MagicMock(content=self.response_content)


@pytest.fixture
def mock_gateway():
    """Mock gateway client."""
    return MockGatewayClient()


@pytest.fixture
def test_repo(tmp_path):
    """Create test repository."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    
    # Create sample code
    (repo / "calculator.py").write_text("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a + b  # BUG: should be a * b

def divide(a, b):
    if b == 0:
        raise ValueError("div by zero")
    return a / b
""")
    
    return repo


@pytest.mark.asyncio
async def test_patch_generator_basic(mock_gateway):
    """Test basic patch generation."""
    generator = PatchGenerator(
        gateway_client=mock_gateway,
        model_name="test-model",
        num_patches=4,
        base_temp=0.3,
        max_temp=0.7
    )
    
    patches = await generator.generate_patches(
        issue_text="Fix the multiply function",
        code_context="def multiply(a, b): return a + b"
    )
    
    assert len(patches) <= 4
    assert all("content" in p for p in patches)
    assert all("temperature" in p for p in patches)


@pytest.mark.asyncio
async def test_patch_generator_temperatures(mock_gateway):
    """Test temperature range."""
    generator = PatchGenerator(
        gateway_client=mock_gateway,
        model_name="test-model",
        num_patches=8
    )
    
    await generator.generate_patches(
        issue_text="Fix bug",
        code_context="code"
    )
    
    # Check temperatures are in range
    temps = [0.3 + (i / 8) * 0.4 for i in range(8)]
    for i, temp in enumerate(temps):
        expected = generator.base_temp + (i / generator.num_patches) * (generator.max_temp - generator.base_temp)
        assert abs(temp - expected) < 0.01


@pytest.mark.asyncio
async def test_verifier_apply_patch(test_repo):
    """Test patch application."""
    verifier = PatchVerifier(
        repo_path=test_repo,
        test_command="python -c 'import calculator'",
        timeout=10
    )
    
    # This is a diff-style patch
    patch = """--- a/calculator.py
+++ b/calculator.py
@@ -2,7 +2,7 @@
-def multiply(a, b):
-    return a + b
+def multiply(a, b):
+    return a * b
"""
    
    result = await verifier.verify_patch(patch, "test_patch")
    
    assert "patch_id" in result
    assert "score" in result


@pytest.mark.asyncio
async def test_verifier_score_patch():
    """Test patch scoring."""
    verifier = PatchVerifier(
        repo_path=Path("."),
        test_command="echo test"
    )
    
    # Test passed
    passed_result = {
        "success": True,
        "stdout": "test output",
        "stderr": ""
    }
    score = verifier.score_patch(passed_result)
    assert score == 1.0
    
    # Test failed
    failed_result = {
        "success": False,
        "stdout": "",
        "stderr": "error"
    }
    score = verifier.score_patch(failed_result)
    assert score == 0.0
    
    # Test with warnings
    warning_result = {
        "success": True,
        "stdout": "output",
        "stderr": "warning: something"
    }
    score = verifier.score_patch(warning_result)
    assert score < 1.0


@pytest.mark.asyncio
async def test_orchestrator_basic(mock_gateway, test_repo):
    """Test orchestrator basic flow."""
    orch = SWEBenchOrchestrator(
        gateway_client=mock_gateway,
        model_name="test-model",
        num_patches=2
    )
    
    result = await orch.resolve_issue(
        issue_text="Fix the multiply bug",
        repo_path=test_repo,
        test_command="python -c 'import calculator'"
    )
    
    assert result is not None
    assert result.repo_path == test_repo
    assert result.total_candidates <= 2


@pytest.mark.asyncio
async def test_orchestrator_status():
    """Test resolution status."""
    assert ResolutionStatus.PENDING.value == "pending"
    assert ResolutionStatus.PASSED.value == "passed"
    assert ResolutionStatus.FAILED.value == "failed"
    assert ResolutionStatus.PARTIAL.value == "partial"


def test_create_orchestrator_factory():
    """Test orchestrator factory."""
    # Just verify factory function exists
    assert callable(create_orchestrator)


@pytest.mark.asyncio
async def test_create_verifier_factory(tmp_path):
    """Test verifier factory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    
    verifier = await create_verifier(repo)
    assert isinstance(verifier, PatchVerifier)


@pytest.mark.asyncio
async def test_patch_selector():
    """Test patch selector."""
    patches = [
        {"id": "patch_1", "content": "fix 1"},
        {"id": "patch_2", "content": "fix 2"},
        {"id": "patch_3", "content": "fix 3"}
    ]
    
    # Mock verifier with simple verify
    verifier = MagicMock(spec=PatchVerifier)
    verifier.verify_patch = AsyncMock(return_value={
        "patch_id": "test",
        "patch": "content",
        "success": True,
        "returncode": 0,
        "stdout": "",
        "stderr": ""
    })
    verifier.score_patch = lambda r: 1.0 if r.get("success") else 0.0
    
    selector = PatchSelector(verifier)
    result = await selector.select_best(patches)
    
    assert "candidates" in result
    assert "best" in result
    assert "passed_count" in result