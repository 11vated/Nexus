"""Tests for SWE-bench orchestrator, patch generator, and verifier."""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from nexus.swe_bench.orchestrator import (
    SWEBenchOrchestrator, SWEBenchResult, ResolutionStatus
)
from nexus.swe_bench.patch_generator import PatchGenerator
from nexus.swe_bench.verifier import PatchVerifier, PatchSelector


class MockResponse:
    def __init__(self, content: str):
        self.content = content


class MockGatewayClient:
    def __init__(self):
        self.chat_completion = AsyncMock()

    async def close(self):
        pass


@pytest.fixture
def mock_gateway():
    return MockGatewayClient()


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        (repo / "app.py").write_text("def hello():\n    return 'hello'")
        (repo / "test_app.py").write_text("def test_hello():\n    assert hello() == 'hello'")
        yield repo


class TestPatchGenerator:
    def test_init(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "qwen2.5-coder:14b", num_patches=4)
        assert gen.num_patches == 4
        assert gen.base_temp == 0.3
        assert gen.max_temp == 0.7

    def test_temperature_calculation(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "model", num_patches=4, base_temp=0.2, max_temp=0.6)
        temps = []
        for i in range(4):
            temp = gen.base_temp + (i / gen.num_patches) * (gen.max_temp - gen.base_temp)
            temps.append(temp)
        assert temps[0] == pytest.approx(0.2)
        assert temps[-1] == pytest.approx(0.5)

    def test_strategy_application(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "model")
        base = "Fix the bug."
        result = gen._apply_strategy(base, 0)
        assert result == base + ""
        result = gen._apply_strategy(base, 1)
        assert "step by step" in result

    def test_strategy_names(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "model")
        assert gen._get_strategy_name(0) == "baseline"
        assert gen._get_strategy_name(1) == "step_by_step"
        assert gen._get_strategy_name(7) == "alternative"
        assert gen._get_strategy_name(8) == "baseline"  # wraps around

    def test_build_prompt(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "model")
        prompt = gen._build_base_prompt("fix bug", "code here", "structure here")
        assert "fix bug" in prompt
        assert "code here" in prompt
        assert "structure here" in prompt
        assert "unified diff" in prompt

    def test_build_prompt_no_context(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "model")
        prompt = gen._build_base_prompt("fix bug", None, None)
        assert "Relevant code:" not in prompt
        assert "Repository structure:" not in prompt

    @pytest.mark.asyncio
    async def test_generate_patches_success(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "model", num_patches=3)
        mock_gateway.chat_completion.side_effect = [
            MockResponse("patch 1"),
            MockResponse("patch 2"),
            MockResponse("patch 3"),
        ]
        patches = await gen.generate_patches("fix bug", "code", "structure")
        assert len(patches) == 3
        assert patches[0]["id"] == "patch_1"
        assert patches[0]["content"] == "patch 1"
        assert patches[1]["strategy"] == "step_by_step"

    @pytest.mark.asyncio
    async def test_generate_patches_partial_failure(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "model", num_patches=3)
        mock_gateway.chat_completion.side_effect = [
            MockResponse("patch 1"),
            Exception("timeout"),
            MockResponse("patch 3"),
        ]
        patches = await gen.generate_patches("fix bug")
        assert len(patches) == 2  # empty patch 2 filtered out

    @pytest.mark.asyncio
    async def test_generate_patches_all_failure(self, mock_gateway):
        gen = PatchGenerator(mock_gateway, "model", num_patches=2)
        mock_gateway.chat_completion.side_effect = [
            Exception("error1"),
            Exception("error2"),
        ]
        patches = await gen.generate_patches("fix bug")
        assert len(patches) == 0


class TestPatchVerifier:
    def test_init(self, temp_repo):
        verifier = PatchVerifier(temp_repo, "pytest", timeout=60)
        assert verifier.repo_path == temp_repo
        assert verifier.test_command == "pytest"
        assert verifier.timeout == 60

    def test_error_result(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        result = verifier._error_result("p1", "diff", "failed", "apply_failed")
        assert result["patch_id"] == "p1"
        assert result["success"] is False
        assert result["score"] == 0.0
        assert result["error"] == "apply_failed"

    def test_score_patch_passes(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        result = {"success": True, "stderr": "", "stdout": "", "error": None}
        assert verifier.score_patch(result) == 1.0

    def test_score_patch_warnings(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        result = {"success": True, "stderr": "warning: unused", "stdout": "", "error": None}
        assert verifier.score_patch(result) == 0.9

    def test_score_patch_large_output(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        result = {"success": True, "stderr": "", "stdout": "x" * 6000, "error": None}
        assert verifier.score_patch(result) == 0.95

    def test_score_patch_error(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        result = {"success": True, "stderr": "", "stdout": "", "error": "timeout"}
        assert verifier.score_patch(result) == 0.8

    def test_score_patch_failed(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        result = {"success": False}
        assert verifier.score_patch(result) == 0.0

    def test_apply_code_block_no_block(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        result = verifier._apply_code_block("not a code block", temp_repo)
        assert result["success"] is False
        assert "No code block found" in result["error"]

    def test_apply_code_block(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        patch_text = '```python\n# file: app.py\ndef new(): pass\n```'
        result = verifier._apply_code_block(patch_text, temp_repo)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_run_tests_timeout(self, temp_repo):
        verifier = PatchVerifier(temp_repo, "timeout 30 > NUL", timeout=1)
        result = await verifier._run_tests(temp_repo)
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_run_tests_invalid_command(self, temp_repo):
        verifier = PatchVerifier(temp_repo, "nonexistent_command_xyz", timeout=5)
        result = await verifier._run_tests(temp_repo)
        assert result["passed"] is False


class TestPatchSelector:
    @pytest.mark.asyncio
    async def test_select_best(self, temp_repo):
        verifier = PatchVerifier(temp_repo, "pytest")
        selector = PatchSelector(verifier)
        
        patches = [
            {"id": "p1", "content": "patch1"},
            {"id": "p2", "content": "patch2"},
        ]
        
        # Mock verify_patch to return predefined results
        with patch.object(verifier, 'verify_patch', new_callable=AsyncMock) as mock_verify:
            mock_verify.side_effect = [
                {"patch_id": "p1", "success": True, "stderr": "", "stdout": "", "error": None},
                {"patch_id": "p2", "success": True, "stderr": "", "stdout": "", "error": None},
            ]
            result = await selector.select_best(patches)
            assert "candidates" in result
            assert "best" in result
            assert "passed_count" in result
            assert result["passed_count"] == 2

    @pytest.mark.asyncio
    async def test_select_best_empty(self, temp_repo):
        verifier = PatchVerifier(temp_repo)
        selector = PatchSelector(verifier)
        result = await selector.select_best([])
        assert result["best"] is None
        assert result["passed_count"] == 0


class TestSWEBenchOrchestrator:
    def test_init(self, mock_gateway):
        orch = SWEBenchOrchestrator(mock_gateway, "qwen2.5-coder:14b")
        assert orch.model == "qwen2.5-coder:14b"
        assert orch.num_patches == 8

    @pytest.mark.asyncio
    async def test_resolve_no_patches(self, mock_gateway, temp_repo):
        orch = SWEBenchOrchestrator(mock_gateway, "model", num_patches=2)
        
        with patch('nexus.swe_bench.orchestrator.PatchGenerator.generate_patches', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = []
            result = await orch.resolve_issue("fix bug", temp_repo)
            assert result.status == ResolutionStatus.FAILED
            assert result.details[0]["error"] == "No patches generated"

    @pytest.mark.asyncio
    async def test_resolve_result(self, mock_gateway, temp_repo):
        orch = SWEBenchOrchestrator(mock_gateway, "model", num_patches=2)
        
        with patch('nexus.swe_bench.orchestrator.PatchGenerator.generate_patches', new_callable=AsyncMock) as mock_gen, \
             patch('nexus.swe_bench.verifier.PatchVerifier.verify_patch', new_callable=AsyncMock) as mock_verify, \
             patch('nexus.swe_bench.verifier.PatchSelector.select_best', new_callable=AsyncMock) as mock_select:
            
            mock_gen.return_value = [{"id": "p1", "content": "diff"}]
            mock_verify.return_value = {"patch_id": "p1", "success": True, "stderr": "", "stdout": "", "error": None}
            mock_select.return_value = {
                "candidates": [{"patch_id": "p1", "score": 0.9, "patch": "diff"}],
                "best": {"patch_id": "p1", "score": 0.9, "patch": "diff"},
                "passed_count": 1
            }
            
            result = await orch.resolve_issue("fix bug", temp_repo)
            assert result.best_patch == "diff"
            assert result.best_score == 0.9
            assert result.candidates_tested == 1
            assert result.passed_count == 1

    def test_resolution_status_enum(self):
        assert ResolutionStatus.PENDING.value == "pending"
        assert ResolutionStatus.PASSED.value == "passed"
        assert ResolutionStatus.FAILED.value == "failed"
        assert ResolutionStatus.PARTIAL.value == "partial"
        assert ResolutionStatus.IN_PROGRESS.value == "in_progress"

    def test_swe_bench_result_defaults(self, temp_repo):
        result = SWEBenchResult(issue="test", repo_path=temp_repo)
        assert result.status == ResolutionStatus.PENDING
        assert result.best_patch is None
        assert result.best_score == 0.0
        assert result.candidates_tested == 0
        assert result.details == []
