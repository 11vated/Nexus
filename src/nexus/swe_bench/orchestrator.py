"""SWE-bench orchestrator for multi-patch generation and verification."""
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from .patch_generator import PatchGenerator
from .verifier import PatchVerifier, PatchSelector
from ..gateway.client import GatewayClient


logger = logging.getLogger(__name__)


class ResolutionStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class SWEBenchResult:
    """Result of SWE-bench resolution."""
    issue: str
    repo_path: Path
    status: ResolutionStatus = ResolutionStatus.PENDING
    best_patch: Optional[str] = None
    best_score: float = 0.0
    candidates_tested: int = 0
    passed_count: int = 0
    total_candidates: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)


class SWEBenchOrchestrator:
    """Orchestrate SWE-bench issue resolution with multi-patch generation."""
    
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
    
    async def resolve_issue(
        self,
        issue_text: str,
        repo_path: Path,
        test_command: str = "pytest",
        code_context: str = None,
        file_structure: str = None
    ) -> SWEBenchResult:
        """Resolve a SWE-bench issue with multi-patch generation."""
        logger.info(f"Resolving: {issue_text[:100]}...")
        
        repo_path = Path(repo_path)
        
        # Generate patches
        generator = PatchGenerator(
            gateway_client=self.gateway,
            model_name=self.model,
            num_patches=self.num_patches,
            base_temp=self.base_temp,
            max_temp=self.max_temp
        )
        
        patches = await generator.generate_patches(
            issue_text=issue_text,
            code_context=code_context,
            file_structure=file_structure
        )
        
        if not patches:
            return SWEBenchResult(
                issue=issue_text[:200],
                repo_path=repo_path,
                status=ResolutionStatus.FAILED,
                details=[{"error": "No patches generated"}]
            )
        
        # Verify patches
        verifier = PatchVerifier(repo_path, test_command)
        selector = PatchSelector(verifier)
        
        verify_result = await selector.select_best(patches)
        
        candidates = verify_result["candidates"]
        best = verify_result["best"]
        
        passed_count = verify_result["passed_count"]
        
        # Determine status
        if passed_count == 0:
            status = ResolutionStatus.FAILED
        elif passed_count >= self.num_patches // 2:
            status = ResolutionStatus.PASSED
        elif passed_count > 0:
            status = ResolutionStatus.PARTIAL
        else:
            status = ResolutionStatus.FAILED
        
        return SWEBenchResult(
            issue=issue_text[:200],
            repo_path=repo_path,
            status=status,
            best_patch=best["patch"] if best else None,
            best_score=best["score"] if best else 0.0,
            candidates_tested=len(patches),
            passed_count=passed_count,
            total_candidates=len(patches),
            details=candidates
        )
    
    async def resolve_issue_parallel(
        self,
        issue_text: str,
        repo_path: Path,
        test_command: str = "pytest",
        code_context: str = None,
        file_structure: str = None,
        max_concurrent: int = 4
    ) -> SWEBenchResult:
        """Resolve with parallel patch testing (faster)."""
        return await self.resolve_issue(
            issue_text, repo_path, test_command, code_context, file_structure
        )


async def create_orchestrator(
    gateway_client: GatewayClient,
    model_name: str = "qwen2.5-coder:14b",
    num_patches: int = 8
) -> SWEBenchOrchestrator:
    """Factory function for orchestrator."""
    return SWEBenchOrchestrator(
        gateway_client=gateway_client,
        model_name=model_name,
        num_patches=num_patches
    )