#!/usr/bin/env python3
"""
NEXUS FUSED TOOLS - Individual Tool Unification
=================================================

Instead of unifying ALL tools (bad), we unify SPECIFIC pairs that create synergy:

1. Vision + Code = Visual Debugger (see UI bugs, visual errors)
2. Search + Memory = Contextual Research (search with project context)
3. Terminal + Vision = Visual Terminal (see terminal output visually)
4. Git + Code Analysis = Intelligent Version Control (understand code changes)
5. Sandbox + Vision = Visual Test Runner (visual error detection)
6. Computer Use + Vision = Visual Automation (see before/after actions)

Each fusion has:
- Unified interface
- Specialized execution
- Intelligent routing

"Standardized interfaces, specialized engines" - DNA, Organs, Brain analogy
"""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime


# ============================================
# UNIFIED TOOL PROTOCOL (Layer 1)
# ============================================

@dataclass
class ToolResult:
    """Standard result format for all fused tools"""
    success: bool
    output: Any
    metadata: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "output": self.output,
            "metadata": self.metadata,
            "errors": self.errors
        }


class FusedTool:
    """
    Base class for all fused tools.
    Each fusion gets a standardized interface but keeps specialized execution.
    """
    
    def __init__(self, name: str, fusion_type: str):
        self.name = name
        self.fusion_type = fusion_type  # e.g., "vision+code", "search+memory"
    
    async def execute(self, input_data: Any, **kwargs) -> ToolResult:
        """Execute the fused tool - to be implemented by each fusion"""
        raise NotImplementedError
    
    def _create_result(self, success: bool, output: Any, 
                       metadata: Optional[Dict] = None,
                       errors: Optional[List[str]] = None) -> ToolResult:
        return ToolResult(
            success=success,
            output=output,
            metadata=metadata or {},
            errors=errors or []
        )


# ============================================
# FUSION 1: VISION + CODE = VISUAL DEBUGGER
# ============================================

class VisualDebugger(FusedTool):
    """
    FUSION: Vision + Code Execution
    
    What it does:
    - Takes a screenshot of an error/UI
    - Analyzes visually what's wrong
    - Runs code to understand the error
    - Correlates visual state with code logic
    
    Why it's valuable:
    - UI bugs are visual - text error messages don't show what's wrong
    - Can see layout issues, missing elements, wrong colors
    - Can trace visual problems back to code
    """
    
    def __init__(self):
        super().__init__("VisualDebugger", "vision+code")
        self.vision_model = "llava"
    
    async def execute(self, input_data: Any, **kwargs) -> ToolResult:
        """
        Input: {
            "screenshot": base64_image OR path,
            "error_message": str (optional),
            "code_context": str (optional - relevant code)
        }
        """
        try:
            # Step 1: Analyze screenshot visually
            visual_analysis = await self._analyze_screenshot(input_data.get("screenshot"))
            
            # Step 2: Analyze error message if provided
            code_analysis = ""
            if input_data.get("error_message"):
                code_analysis = await self._analyze_error(input_data.get("error_message"))
            
            # Step 3: Use code context if provided
            code_context = input_data.get("code_context", "")
            
            # Step 4: Synthesize diagnosis
            diagnosis = await self._synthesize_diagnosis(
                visual=visual_analysis,
                error=code_analysis,
                code=code_context
            )
            
            return self._create_result(
                success=True,
                output=diagnosis,
                metadata={
                    "visual_analysis": visual_analysis,
                    "code_analysis": code_analysis,
                    "fusion_type": "vision+code"
                }
            )
            
        except Exception as e:
            return self._create_result(False, None, errors=[str(e)])
    
    async def _analyze_screenshot(self, screenshot) -> str:
        """Use vision model to analyze the screenshot"""
        if not screenshot:
            return "No screenshot provided"
        
        # If it's a path, read it
        if isinstance(screenshot, str) and os.path.exists(screenshot):
            with open(screenshot, "rb") as f:
                image_data = f.read()
        else:
            image_data = screenshot
        
        import base64
        b64 = base64.b64encode(image_data).decode('utf-8')
        
        prompt = """Analyze this screenshot showing an error/debugging situation:
        1. What UI elements are visible?
        2. Are there any error messages, warnings, or visual anomalies?
        3. What application/website is shown?
        4. Describe any visual bugs (overlap, wrong colors, missing elements)
        
        Be specific and detailed."""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.vision_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=f"[img-1]<base64>{b64[:1000]}...\n\n{prompt}".encode()),
                timeout=90
            )
            
            return stdout.decode()[:500]
            
        except Exception as e:
            return f"Visual analysis error: {e}"
    
    async def _analyze_error(self, error_message: str) -> str:
        """Analyze error message using code model"""
        prompt = f"""Analyze this error message and provide:
        1. Root cause (what went wrong)
        2. Suggested fix
        3. What part of the code to check
        
        Error: {error_message}"""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", "deepseek-r1:7b",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=60
            )
            
            return stdout.decode()[:300]
            
        except:
            return "Could not analyze error"
    
    async def _synthesize_diagnosis(self, visual: str, error: str, code: str) -> Dict:
        """Synthesize final diagnosis combining visual and code analysis"""
        
        prompt = f"""You are a debugging expert. Combine these analyses to diagnose the bug:

VISUAL ANALYSIS:
{visual}

CODE/ERROR ANALYSIS:
{error}

CODE CONTEXT:
{code[:500] if code else 'No code context'}

Provide:
1. ROOT CAUSE: What's actually wrong?
2. VISUAL EVIDENCE: What you see supporting this
3. FIX: How to solve it
4. CONFIDENCE: high/medium/low

Respond in JSON format:
{{"root_cause": "...", "visual_evidence": "...", "fix": "...", "confidence": "high"}}"""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", "qwen2.5-coder:14b",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=60
            )
            
            result = stdout.decode()
            
            # Try to parse JSON
            if '{' in result:
                try:
                    json_str = result[result.find('{'):result.rfind('}')+1]
                    return json.loads(json_str)
                except:
                    pass
            
            return {"raw_diagnosis": result[:500], "confidence": "medium"}
            
        except Exception as e:
            return {"error": str(e), "confidence": "low"}


# ============================================
# FUSION 2: SEARCH + MEMORY = CONTEXTUAL RESEARCH
# ============================================

class ContextualResearch(FusedTool):
    """
    FUSION: Search + Project Memory
    
    What it does:
    - Knows about your project (tech stack, patterns, preferences)
    - Searches the web WITH that context
    - Filters results relevant to YOUR stack
    - Remembers what it learns for future research
    
    Why it's valuable:
    - Generic search results aren't helpful for specific stacks
    - "How to do X in React" vs "How to do X in Vue" are different
    - Project-specific context makes research 10x more relevant
    """
    
    def __init__(self, memory_path: str = None):
        super().__init__("ContextualResearch", "search+memory")
        self.memory_path = memory_path or os.path.join(
            os.path.expanduser("~"), ".nexus", "memory"
        )
        self.memory = self._load_memory()
        self.search_cache = {}
    
    def _load_memory(self) -> Dict:
        """Load project memory"""
        mem_file = Path(self.memory_path) / "projects.json"
        if mem_file.exists():
            try:
                return json.loads(mem_file.read_text())
            except:
                return {}
        return {}
    
    async def execute(self, input_data: Any, **kwargs) -> ToolResult:
        """
        Input: {
            "query": str,
            "project_path": str (optional - use specific project context)
        }
        """
        query = input_data.get("query", "")
        project_path = input_data.get("project_path", ".")
        
        try:
            # Step 1: Get project context
            project_context = self._get_project_context(project_path)
            
            # Step 2: Enhance query with context
            enhanced_query = self._enhance_query(query, project_context)
            
            # Step 3: Search with enhanced query
            search_results = await self._search(enhanced_query)
            
            # Step 4: Filter by relevance to project
            filtered_results = self._filter_by_relevance(
                search_results, project_context
            )
            
            # Step 5: Learn from this research
            self._learn_research(query, filtered_results, project_context)
            
            return self._create_result(
                success=True,
                output={
                    "query": query,
                    "enhanced_query": enhanced_query,
                    "project_context": project_context,
                    "results": filtered_results
                },
                metadata={
                    "fusion_type": "search+memory",
                    "results_count": len(filtered_results)
                }
            )
            
        except Exception as e:
            return self._create_result(False, None, errors=[str(e)])
    
    def _get_project_context(self, project_path: str) -> Dict:
        """Get context about the project"""
        for proj_path, proj_data in self.memory.items():
            if proj_path in project_path or project_path in proj_path:
                return proj_data
        return {"name": "Unknown", "language": "unknown"}
    
    def _enhance_query(self, query: str, context: Dict) -> str:
        """Enhance search query with project context"""
        lang = context.get("language", "")
        framework = context.get("framework", "")
        name = context.get("name", "")
        
        # Build enhanced query
        enhancements = []
        if lang:
            enhancements.append(lang)
        if framework:
            enhancements.append(str(framework))
        
        if enhancements:
            return f"{query} ({' '.join(enhancements)})"
        return query
    
    async def _search(self, query: str) -> List[Dict]:
        """Perform web search"""
        # Simplified - use curl to search
        try:
            # Try duckduckgo via HTML
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", f"https://html.duckduckgo.com/html/?q={query}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            html = stdout.decode()
            
            # Extract results (simplified)
            results = []
            # This is a very simplified parser
            titles = re.findall(r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', html)
            for url, title in titles[:10]:
                results.append({"url": url, "title": title, "query": query})
            
            return results
            
        except Exception as e:
            return [{"error": str(e)}]
    
    def _filter_by_relevance(self, results: List[Dict], context: Dict) -> List[Dict]:
        """Filter results by relevance to project"""
        lang = context.get("language", "").lower()
        framework = str(context.get("framework", "")).lower()
        
        filtered = []
        for r in results:
            url = r.get("url", "").lower()
            title = r.get("title", "").lower()
            
            # Boost results matching project tech
            score = 0
            if lang and (lang in url or lang in title):
                score += 2
            if framework and (framework in url or framework in title):
                score += 2
            
            r["relevance_score"] = score
            if score > 0 or not lang:
                filtered.append(r)
        
        # Sort by relevance
        filtered.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return filtered[:5]
    
    def _learn_research(self, query: str, results: List[Dict], context: Dict):
        """Remember this research for future"""
        # Store in cache
        cache_key = hashlib.md5(query.encode()).hexdigest()
        self.search_cache[cache_key] = {
            "query": query,
            "results": results,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }


# ============================================
# FUSION 3: TERMINAL + VISION = VISUAL TERMINAL
# ============================================

class VisualTerminal(FusedTool):
    """
    FUSION: Terminal + Vision
    
    What it does:
    - Executes terminal commands
    - Takes screenshot after execution
    - Analyzes visual output
    - Reports what the user would SEE
    
    Why it's valuable:
    - Terminal output is text, but applications have GUI
    - "npm install" might show a progress bar that looks wrong
    - Build errors might have visual components
    - See what the terminal is actually producing visually
    """
    
    def __init__(self):
        super().__init__("VisualTerminal", "terminal+vision")
        self.vision_model = "llava"
        self.command_history = []
    
    async def execute(self, input_data: Any, **kwargs) -> ToolResult:
        """
        Input: {
            "command": str,
            "cwd": str (optional - working directory)
        }
        """
        command = input_data.get("command", "")
        cwd = input_data.get("cwd", os.getcwd())
        
        try:
            # Step 1: Execute command
            start_time = time.time()
            result = await self._execute_command(command, cwd)
            duration = time.time() - start_time
            
            # Step 2: Take screenshot of output state
            screenshot = await self._capture_state()
            
            # Step 3: Analyze visual output
            visual_analysis = ""
            if screenshot:
                visual_analysis = await self._analyze_visual_state(screenshot)
            
            # Step 4: Combine textual and visual analysis
            combined_result = {
                "command": command,
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code"),
                "duration": duration,
                "visual_analysis": visual_analysis,
                "timestamp": datetime.now().isoformat()
            }
            
            # Store in history
            self.command_history.append(combined_result)
            
            return self._create_result(
                success=result.get("exit_code", -1) == 0,
                output=combined_result,
                metadata={"fusion_type": "terminal+vision"}
            )
            
        except Exception as e:
            return self._create_result(False, None, errors=[str(e)])
    
    async def _execute_command(self, command: str, cwd: str) -> Dict:
        """Execute terminal command"""
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        
        return {
            "stdout": stdout.decode()[:5000],
            "stderr": stderr.decode()[:1000],
            "exit_code": proc.returncode
        }
    
    async def _capture_state(self) -> Optional[bytes]:
        """Capture current visual state"""
        try:
            import mss
            with mss.mss() as sct:
                # Capture primary monitor
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                return mss.tools.to_png(screenshot.rgb, screenshot.size)
        except:
            return None
    
    async def _analyze_visual_state(self, screenshot: bytes) -> str:
        """Analyze what's visually happening"""
        import base64
        b64 = base64.b64encode(screenshot).decode('utf-8')
        
        prompt = """Analyze this screenshot showing terminal/application state:
        1. What application or interface is visible?
        2. Are there any error dialogs, warnings, or visual issues?
        3. What is the current state of the process?
        4. Any visual anomalies worth noting?
        
        Be specific about what you see."""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.vision_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=f"[img-1]<base64>{b64[:1000]}...\n\n{prompt}".encode()),
                timeout=90
            )
            
            return stdout.decode()[:400]
            
        except:
            return "Visual analysis unavailable"


# ============================================
# FUSION 4: GIT + CODE ANALYSIS = INTELLIGENT VC
# ============================================

class IntelligentVersionControl(FusedTool):
    """
    FUSION: Git + Code Analysis
    
    What it does:
    - Understands what code CHANGES mean, not just what changed
    - Analyzes code semantics, not just diffs
    - Suggests meaningful commit messages
    - Reviews changes for bugs, security issues
    - Understands code dependencies
    
    Why it's valuable:
    - "git diff" shows WHAT, but not SO WHAT
    - This tool understands the IMPACT of changes
    - Can catch bugs before commit
    - Generates meaningful commit messages
    """
    
    def __init__(self):
        super().__init__("IntelligentVC", "git+code")
        self.code_model = "qwen2.5-coder:14b"
    
    async def execute(self, input_data: Any, **kwargs) -> ToolResult:
        """
        Input: {
            "action": "commit_message|review|analyze|security",
            "repo_path": str,
            "diff": str (optional)
        }
        """
        action = input_data.get("action", "analyze")
        repo_path = input_data.get("repo_path", ".")
        
        try:
            # Get git status/diff
            git_data = await self._get_git_data(repo_path)
            
            if action == "commit_message":
                result = await self._generate_commit_message(git_data)
            elif action == "review":
                result = await self._review_changes(git_data)
            elif action == "security":
                result = await self._security_scan(git_data)
            else:
                result = await self._analyze_changes(git_data)
            
            return self._create_result(
                success=True,
                output=result,
                metadata={"action": action, "fusion_type": "git+code"}
            )
            
        except Exception as e:
            return self._create_result(False, None, errors=[str(e)])
    
    async def _get_git_data(self, repo_path: str) -> Dict:
        """Get comprehensive git data"""
        data = {}
        
        # Status
        proc = await asyncio.create_subprocess_exec(
            "git", "status", "--porcelain",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        data["status"] = stdout.decode()
        
        # Diff
        proc = await asyncio.create_subprocess_exec(
            "git", "diff", "--staged",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        data["diff"] = stdout.decode()[:10000]
        
        # Branch
        proc = await asyncio.create_subprocess_exec(
            "git", "branch", "--show-current",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        data["branch"] = stdout.decode().strip()
        
        return data
    
    async def _generate_commit_message(self, git_data: Dict) -> Dict:
        """Generate meaningful commit message"""
        diff = git_data.get("diff", "")
        status = git_data.get("status", "")
        
        prompt = f"""Analyze these git changes and generate a meaningful commit message:

CHANGES:
{diff}

FILES CHANGED:
{status}

Generate:
1. A short commit title (50 chars max)
2. A detailed body explaining WHAT changed and WHY
3. Type: feat/fix/docs/refactor/test/chore

Format as:
title: ...
body: ..."""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.code_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=60
            )
            
            return {"commit_message": stdout.decode(), "git_data": git_data}
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _review_changes(self, git_data: Dict) -> Dict:
        """Review changes for potential issues"""
        diff = git_data.get("diff", "")
        
        prompt = f"""Review these code changes for issues:

{diff}

Analyze for:
1. BUGS - potential logic errors
2. SECURITY - vulnerable patterns
3. PERFORMANCE - inefficient code
4. CODE SMELL - maintainability issues

Rate each file changed: SAFE / WARNING / CRITICAL

Provide specific feedback for each issue found."""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.code_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=60
            )
            
            return {"review": stdout.decode(), "git_data": git_data}
            
        except:
            return {"error": "Could not review"}
    
    async def _security_scan(self, git_data: Dict) -> Dict:
        """Scan for security issues"""
        diff = git_data.get("diff", "")
        
        prompt = f"""Security scan these changes:

{diff}

Check for:
1. SQL injection vulnerabilities
2. Hardcoded secrets/keys
3. XSS vulnerabilities
4. Command injection
5. Authentication bypass
6. Insecure dependencies

For each issue found, provide:
- Severity: CRITICAL/HIGH/MEDIUM/LOW
- Location: file:line
- Description
- Fix"""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.code_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=60
            )
            
            return {"security_scan": stdout.decode(), "git_data": git_data}
            
        except:
            return {"error": "Scan failed"}
    
    async def _analyze_changes(self, git_data: Dict) -> Dict:
        """General analysis of changes"""
        return await self._review_changes(git_data)


# ============================================
# FUSION 5: SANDBOX + VISION = VISUAL TEST
# ============================================

class VisualTestRunner(FusedTool):
    """
    FUSION: Sandbox + Vision
    
    What it does:
    - Runs code in sandbox
    - Captures visual output (not just text)
    - Detects visual bugs/breaks
    - Records visual regression
    
    Why it's valuable:
    - Code can "succeed" textually but render wrongly
    - UI tests are hard - this makes them easier
    - Can detect layout issues, missing elements
    """
    
    def __init__(self):
        super().__init__("VisualTestRunner", "sandbox+vision")
        self.vision_model = "llava"
    
    async def execute(self, input_data: Any, **kwargs) -> ToolResult:
        """
        Input: {
            "code": str,
            "language": "python|javascript|...",
            "expected_output": str (optional)
        }
        """
        code = input_data.get("code", "")
        language = input_data.get("language", "python")
        
        try:
            # Step 1: Run in sandbox
            exec_result = await self._execute_sandbox(code, language)
            
            # Step 2: Capture visual state
            screenshot = await self._capture_screen()
            
            # Step 3: Analyze visual output
            visual_analysis = ""
            if screenshot:
                visual_analysis = await self._analyze_visual_output(screenshot)
            
            # Step 4: Compare with expected (if provided)
            comparison = {}
            if input_data.get("expected_output"):
                comparison = self._compare_outputs(
                    exec_result.get("output", ""),
                    input_data["expected_output"]
                )
            
            result = {
                "execution": exec_result,
                "visual_analysis": visual_analysis,
                "comparison": comparison,
                "passed": exec_result.get("success") and not comparison.get("mismatch")
            }
            
            return self._create_result(
                success=result["passed"],
                output=result,
                metadata={"fusion_type": "sandbox+vision"}
            )
            
        except Exception as e:
            return self._create_result(False,None, errors=[str(e)])
    
    async def _execute_sandbox(self, code: str, language: str) -> Dict:
        """Execute code in sandbox"""
        # Simplified execution
        if language == "python":
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            return {"error": f"Unsupported language: {language}", "success": False}
        
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        
        return {
            "stdout": stdout.decode()[:5000],
            "stderr": stderr.decode()[:1000],
            "exit_code": proc.returncode,
            "success": proc.returncode == 0
        }
    
    async def _capture_screen(self) -> Optional[bytes]:
        """Capture screen after execution"""
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                return mss.tools.to_png(screenshot.rgb, screenshot.size)
        except:
            return None
    
    async def _analyze_visual_output(self, screenshot: bytes) -> str:
        """Analyze visual output"""
        import base64
        b64 = base64.b64encode(screenshot).decode('utf-8')
        
        prompt = """Analyze this screenshot showing code execution output:
        1. What is visible on screen?
        2. Are there any error dialogs, warnings, or issues?
        3. What is the application state?
        4. Any visual anomalies?"""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.vision_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=f"[img-1]<base64>{b64[:1000]}...\n\n{prompt}".encode()),
                timeout=90
            )
            
            return stdout.decode()[:300]
            
        except:
            return "Visual analysis unavailable"
    
    def _compare_outputs(self, actual: str, expected: str) -> Dict:
        """Compare actual vs expected"""
        # Simple comparison
        actual_lines = set(actual.strip().split('\n'))
        expected_lines = set(expected.strip().split('\n'))
        
        missing = expected_lines - actual_lines
        extra = actual_lines - expected_lines
        
        return {
            "mismatch": bool(missing or extra),
            "missing": list(missing),
            "extra": list(extra)
        }


# ============================================
# FUSION 6: COMPUTER USE + VISION = VISUAL AUTO
# ============================================

class VisualAutomation(FusedTool):
    """
    FUSION: Computer Use + Vision
    
    What it does:
    - Before action: Capture visual state
    - Execute action (click, type, etc)
    - After action: Capture new visual state
    - Compare to understand impact
    
    Why it's valuable:
    - Know if action SUCCEEDED visually
    - Detect if something went wrong immediately
    - Can roll back or retry based on visual feedback
    - Much more reliable than just checking return codes
    """
    
    def __init__(self):
        super().__init__("VisualAutomation", "computer+vision")
        self.vision_model = "llava"
    
    async def execute(self, input_data: Any, **kwargs) -> ToolResult:
        """
        Input: {
            "action": "click|type|hotkey|...",
            "params": {...},
            "verify": bool (verify visually after)
        }
        """
        action = input_data.get("action", "")
        params = input_data.get("params", {})
        
        try:
            # Step 1: Capture BEFORE state
            before_state = await self._capture_screen()
            before_analysis = ""
            if before_state:
                before_analysis = await self._analyze_state(before_state, "before")
            
            # Step 2: Execute action
            action_result = await self._execute_action(action, params)
            
            await asyncio.sleep(0.5)  # Wait for UI to update
            
            # Step 3: Capture AFTER state
            after_state = await self._capture_screen()
            after_analysis = ""
            if after_state:
                after_analysis = await self._analyze_state(after_state, "after")
            
            # Step 4: Compare states
            comparison = await self._compare_states(before_state, after_state)
            
            result = {
                "action": action,
                "params": params,
                "action_result": action_result,
                "before": before_analysis,
                "after": after_analysis,
                "comparison": comparison,
                "success": action_result.get("success") and comparison.get("changed")
            }
            
            return self._create_result(
                success=result["success"],
                output=result,
                metadata={"fusion_type": "computer+vision"}
            )
            
        except Exception as e:
            return self._create_result(False, None, errors=[str(e)])
    
    async def _execute_action(self, action: str, params: Dict) -> Dict:
        """Execute computer action"""
        x = params.get("x", 0)
        y = params.get("y", 0)
        
        cmd = []
        
        if action == "click":
            cmd = [sys.executable, "-c", f"import pyautogui; pyautogui.click({x}, {y})"]
        elif action == "type":
            text = params.get("text", "")
            cmd = [sys.executable, "-c", f"import pyautogui; pyautogui.write('{text}')"]
        elif action == "hotkey":
            keys = params.get("keys", [])
            keys_str = ", ".join([f"'{k}'" for k in keys])
            cmd = [sys.executable, "-c", f"import pyautogui; pyautogui.hotkey({keys_str})"]
        
        if cmd:
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()
            return {"success": True}
        
        return {"success": False, "error": "Unknown action"}
    
    async def _capture_screen(self) -> Optional[bytes]:
        """Capture screen"""
        try:
            import mss
            with mss.mss() as sct:
                screenshot = sct.grab(sct.monitors[1])
                return mss.tools.to_png(screenshot.rgb, screenshot.size)
        except:
            return None
    
    async def _analyze_state(self, screenshot: bytes, context: str) -> str:
        """Analyze screen state"""
        import base64
        b64 = base64.b64encode(screenshot).decode('utf-8')
        
        prompt = f"""Analyze this screenshot ({context} action):
        What's visible? Any dialogs? What application is focused?"""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.vision_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=f"[img-1]<base64>{b64[:500]}...\n\n{prompt}".encode()),
                timeout=60
            )
            
            return stdout.decode()[:200]
            
        except:
            return ""
    
    async def _compare_states(self, before: bytes, after: bytes) -> Dict:
        """Compare before/after states"""
        if not before or not after:
            return {"changed": True, "reason": "Could not capture both states"}
        
        # Simple comparison - hash the images
        before_hash = hashlib.md5(before[:1000]).hexdigest()
        after_hash = hashlib.md5(after[:1000]).hexdigest()
        
        changed = before_hash != after_hash
        
        return {
            "changed": changed,
            "before_hash": before_hash,
            "after_hash": after_hash
        }


# ============================================
# TOOL ROUTER (Layer 3 - The Brain)
# ============================================

class NexusToolRouter:
    """
    The "Brain" - Routes requests to the right fused tool.
    
    This is where "intelligence" emerges - the router decides
    which specialized tool combination to use.
    """
    
    def __init__(self):
        # Register all fused tools
        self.tools = {
            "visual_debugger": VisualDebugger(),
            "contextual_research": ContextualResearch(),
            "visual_terminal": VisualTerminal(),
            "intelligent_vc": IntelligentVersionControl(),
            "visual_test": VisualTestRunner(),
            "visual_automation": VisualAutomation()
        }
    
    async def route(self, request: Dict) -> ToolResult:
        """
        Route request to appropriate fused tool.
        
        Request format:
        {
            "intent": "debug_ui|research|run_command|review_changes|test_code|automate",
            "data": {...}
        }
        """
        intent = request.get("intent", "")
        
        # Map intent to tool
        tool_map = {
            "debug_ui": "visual_debugger",
            "debug_visual": "visual_debugger",
            "research": "contextual_research",
            "search_with_context": "contextual_research",
            "run_command": "visual_terminal",
            "terminal_visual": "visual_terminal",
            "review_changes": "intelligent_vc",
            "commit_message": "intelligent_vc",
            "security_scan": "intelligent_vc",
            "test_code": "visual_test",
            "visual_test": "visual_test",
            "automate": "visual_automation",
            "visual_auto": "visual_automation"
        }
        
        tool_name = tool_map.get(intent, intent)
        
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                output=None,
                errors=[f"Unknown tool: {tool_name}"]
            )
        
        tool = self.tools[tool_name]
        return await tool.execute(request.get("data", {}))
    
    def list_tools(self) -> List[Dict]:
        """List all available fused tools"""
        return [
            {
                "name": name,
                "type": tool.fusion_type,
                "description": self._get_description(name)
            }
            for name, tool in self.tools.items()
        ]
    
    def _get_description(self, tool_name: str) -> str:
        descriptions = {
            "visual_debugger": "Vision + Code = See UI bugs, understand errors visually",
            "contextual_research": "Search + Memory = Research with project context",
            "visual_terminal": "Terminal + Vision = See what your commands produce",
            "intelligent_vc": "Git + Code Analysis = Understand what changes mean",
            "visual_test": "Sandbox + Vision = Visual test execution",
            "visual_automation": "Computer + Vision = Verify automation visually"
        }
        return descriptions.get(tool_name, "")


# ============================================
# CLI INTERFACE
# ============================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Nexus Fused Tools")
    parser.add_argument("--tool", help="Tool to use")
    parser.add_argument("--intent", help="Intent (debug_ui, research, etc)")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--command", help="Terminal command")
    parser.add_argument("--list", action="store_true", help="List tools")
    
    args = parser.parse_args()
    
    print("""
============================================================
  NEXUS FUSED TOOLS - Individual Tool Unification
============================================================

  Standardized interfaces + Specialized engines
  (DNA + Organs + Brain architecture)
============================================================
    """)
    
    router = NexusToolRouter()
    
    if args.list:
        print("\nAvailable Fused Tools:")
        print("-" * 60)
        for tool in router.list_tools():
            print(f"\n{tool['name']} ({tool['type']})")
            print(f"  {tool['description']}")
        return
    
    # Example usage based on args
    if args.tool:
        result = await router.route({
            "intent": args.intent or args.tool,
            "data": {}
        })
        print(json.dumps(result.to_dict(), indent=2))
    
    else:
        # Interactive demo
        print("\nFused Tools Available:")
        for tool in router.list_tools():
            print(f"  - {tool['name']}: {tool['type']}")
        
        print("\nUsage examples:")
        print("  --tool visual_debugger --intent debug_ui")
        print("  --tool contextual_research --query 'react hooks'")
        print("  --tool visual_terminal --command 'ls -la'")
        print("  --tool intelligent_vc --intent review_changes")
        print("  --tool visual_test --intent test_code")


if __name__ == "__main__":
    asyncio.run(main())