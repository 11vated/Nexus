"""Self-assessment and reflection for the Nexus agent.

After each step or series of steps, the reflector evaluates quality
and decides whether to continue, retry, or adjust approach.
Inspired by the SelfCorrectingAgent pattern from ultimate_agent.py.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from nexus.agent.llm import OllamaClient, extract_json
from nexus.agent.models import AgentConfig, QualityLevel, Step

logger = logging.getLogger(__name__)

REFLECT_PROMPT = """\
You are a code reviewer and quality assessor. Evaluate this execution step:

Action: {action}
Tool: {tool_name}
Result: {result}
Success: {success}

Original goal: {goal}
Steps completed so far: {step_count}

Assess:
1. Did this step make progress toward the goal?
2. Are there any issues with the result?
3. What should happen next?

Respond with JSON:
{{
  "quality_score": 0-4,
  "made_progress": true/false,
  "issues": ["issue1", "issue2"],
  "suggestion": "what to do next",
  "should_retry": true/false,
  "goal_complete": true/false
}}

Quality scale: 0=rejected, 1=poor, 2=fair, 3=good, 4=excellent
"""

QUALITY_GATE_PROMPT = """\
You are a code quality gate. Examine this code output for issues:

```
{code}
```

Check for:
1. Syntax errors
2. Missing imports
3. Undefined variables
4. Logic errors
5. Security issues (hardcoded secrets, shell injection, etc.)

Respond with JSON:
{{
  "passed": true/false,
  "issues": ["issue1", "issue2"],
  "severity": "none|low|medium|high|critical",
  "fix_suggestion": "how to fix"
}}
"""


class Reflector:
    """Evaluates execution quality and provides feedback.

    The reflector uses a separate LLM call (optionally a different model)
    to critically assess each step and overall progress.
    """

    def __init__(
        self,
        llm: OllamaClient,
        config: Optional[AgentConfig] = None,
    ):
        self.llm = llm
        self.config = config or AgentConfig()

    async def reflect_on_step(
        self,
        step: Step,
        goal: str,
        history: List[Step],
    ) -> Dict[str, Any]:
        """Reflect on a completed step.

        Args:
            step: The step that was just executed.
            goal: The original goal.
            history: Full execution history.

        Returns:
            Reflection dict with quality_score, issues, suggestion, etc.
        """
        prompt = REFLECT_PROMPT.format(
            action=step.action,
            tool_name=step.tool_name,
            result=step.result[:1000],
            success=step.success,
            goal=goal,
            step_count=len(history),
        )

        response = await self.llm.generate(
            prompt=prompt,
            model=self.config.review_model,
            temperature=0.2,
        )

        reflection = extract_json(response)
        if isinstance(reflection, dict):
            # Update the step with reflection data
            step.quality_score = float(reflection.get("quality_score", 2))
            step.reflection = reflection.get("suggestion", "")
            return reflection

        # Fallback: basic heuristic assessment
        return self._heuristic_reflect(step)

    def _heuristic_reflect(self, step: Step) -> Dict[str, Any]:
        """Fallback reflection when LLM reflection fails."""
        if step.success:
            quality = 3.0
            issues = []
        else:
            quality = 1.0
            issues = [f"Step failed: {step.result[:200]}"]

        result = {
            "quality_score": quality,
            "made_progress": step.success,
            "issues": issues,
            "suggestion": "Continue" if step.success else "Investigate failure",
            "should_retry": not step.success,
            "goal_complete": False,
        }

        step.quality_score = quality
        step.reflection = result["suggestion"]
        return result

    async def quality_gate(self, code: str) -> Dict[str, Any]:
        """Run code through quality gate.

        Checks for syntax errors, security issues, and common bugs.

        Args:
            code: The code to evaluate.

        Returns:
            Dict with passed, issues, severity, fix_suggestion.
        """
        # Quick syntax check first (no LLM needed)
        syntax_issues = self._check_syntax(code)
        if syntax_issues:
            return {
                "passed": False,
                "issues": syntax_issues,
                "severity": "high",
                "fix_suggestion": "Fix syntax errors before proceeding",
            }

        prompt = QUALITY_GATE_PROMPT.format(code=code[:3000])

        response = await self.llm.generate(
            prompt=prompt,
            model=self.config.review_model,
            temperature=0.1,
        )

        result = extract_json(response)
        if isinstance(result, dict):
            return result

        # Fallback: passed (syntax was already checked)
        return {
            "passed": True,
            "issues": [],
            "severity": "none",
            "fix_suggestion": "",
        }

    def _check_syntax(self, code: str) -> List[str]:
        """Quick Python syntax check without LLM."""
        import ast
        issues = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"SyntaxError at line {e.lineno}: {e.msg}")
        return issues

    async def assess_overall_progress(
        self,
        goal: str,
        history: List[Step],
    ) -> Dict[str, Any]:
        """Assess overall progress toward the goal.

        Called periodically to decide if we should continue, change
        strategy, or declare the goal complete/failed.
        """
        if not history:
            return {
                "progress_pct": 0,
                "status": "starting",
                "recommendation": "begin",
            }

        successful = sum(1 for s in history if s.success)
        total = len(history)
        avg_quality = (
            sum(s.quality_score for s in history) / total if total > 0 else 0
        )

        # Simple heuristic: if recent steps are failing, we might be stuck
        recent = history[-3:]
        recent_failures = sum(1 for s in recent if not s.success)

        if recent_failures >= 3:
            return {
                "progress_pct": int(successful / total * 100) if total else 0,
                "status": "stuck",
                "recommendation": "change_approach",
                "avg_quality": avg_quality,
            }

        return {
            "progress_pct": int(successful / total * 100) if total else 0,
            "status": "progressing",
            "recommendation": "continue",
            "avg_quality": avg_quality,
        }
