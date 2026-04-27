#!/usr/bin/env python3
"""
NEXUS FUNDAMENTAL TOOLS SUITE
==============================

A collection of powerful, foundational tools that give AI agents
access to the entire web as an addressable environment.

Based on research from:
- Playwright MCP (Microsoft)
- Browser Use (Python library)
- CRW/Firecrawl (Scraping APIs)
- Magma, Orion (Multimodal agents)

Tools:
1. WikipediaTool - Structured knowledge access
2. GitHubTool - Code, repos, issues, PRs
3. StackOverflowTool - Problem solving
4. BrowserTool - Full browser automation (Playwright)
5. WebScraperTool - General web scraping
6. DocReaderTool - Documentation reading
7. UnifiedSearchTool - Multi-source search
8. WebResearchAgent - Orchestrates all tools

These tools turn the ENTIRE GUI into an addressable environment.
"""

import asyncio
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
from urllib.parse import quote, urlencode


# ============================================
# TOOL RESULT STANDARD
# ============================================

@dataclass
class ToolResult:
    """Standard result format for all tools"""
    success: bool
    data: Any
    metadata: Dict = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "metadata": self.metadata,
            "error": self.error
        }


# ============================================
# TOOL 1: WIKIPEDIA KNOWLEDGE TOOL
# ============================================

class WikipediaTool:
    """
    Wikipedia API access with intelligent caching and summarization.
    
    Capabilities:
    - Search articles
    - Get summaries
    - Extract sections
    - Find related topics
    - Answer factual questions
    """
    
    def __init__(self):
        self.base_url = "https://en.wikipedia.org/api/rest_v1"
        self.search_url = "https://en.wikipedia.org/w/api.php"
        self.cache = {}
    
    async def search(self, query: str, limit: int = 5) -> ToolResult:
        """Search Wikipedia for articles"""
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json"
            }
            
            url = f"{self.search_url}?{urlencode(params)}"
            
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            data = json.loads(stdout.decode())
            
            results = []
            for item in data.get("query", {}).get("search", []):
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", "").replace("<", "").replace(">", ""),
                    "pageid": item.get("pageid", 0)
                })
            
            return ToolResult(
                success=True,
                data=results,
                metadata={"query": query, "count": len(results)}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def get_summary(self, title: str) -> ToolResult:
        """Get article summary"""
        try:
            # Check cache
            if title in self.cache:
                return ToolResult(success=True, data=self.cache[title])
            
            # Fetch from API
            encoded_title = quote(title.replace(" ", "_"))
            url = f"{self.base_url}/page/summary/{encoded_title}"
            
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", "-H", "Accept: application/json", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            data = json.loads(stdout.decode())
            
            result = {
                "title": data.get("title", ""),
                "extract": data.get("extract", ""),
                "description": data.get("description", ""),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "thumbnail": data.get("thumbnail", {}).get("source", "")
            }
            
            # Cache it
            self.cache[title] = result
            
            return ToolResult(success=True, data=result)
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def get_section(self, title: str, section: str) -> ToolResult:
        """Get specific section from article"""
        try:
            # First get the page ID
            params = {
                "action": "query",
                "titles": title,
                "prop": "sections",
                "format": "json"
            }
            
            url = f"{self.search_url}?{urlencode(params)}"
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", url,
                stdout= asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            data = json.loads(stdout.decode())
            
            pages = data.get("query", {}).get("pages", {})
            page_id = list(pages.keys())[0] if pages else None
            
            if not page_id or page_id == "-1":
                return ToolResult(success=False, data=None, error="Page not found")
            
            # Get sections
            sections = pages.get(page_id, {}).get("sections", [])
            
            # Find matching section
            section_index = None
            for i, s in enumerate(sections):
                if section.lower() in s.get("line", "").lower():
                    section_index = s.get("index")
                    break
            
            if section_index:
                # Get section content
                params = {
                    "action": "parse",
                    "page": title,
                    "section": section_index,
                    "format": "json"
                }
                
                url = f"{self.search_url}?{urlencode(params)}"
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-s", "-L", url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
                parse_data = json.loads(stdout.decode())
                
                content = parse_data.get("parse", {}).get("text", {}).get("*", "")
                # Strip HTML tags
                content = re.sub(r'<[^>]+>', '', content)
                
                return ToolResult(
                    success=True,
                    data={"section": section, "content": content[:2000]}
                )
            
            return ToolResult(success=False, data=None, error="Section not found")
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def ask_question(self, question: str) -> ToolResult:
        """Answer a factual question using Wikipedia"""
        # Extract entity from question
        # Simplified: search for terms in question
        words = question.split()
        
        # Try each combination of words
        for i in range(len(words), 0, -1):
            for j in range(len(words) - i + 1):
                search_term = " ".join(words[j:j+i])
                result = await self.search(search_term, limit=1)
                
                if result.success and result.data:
                    # Get detailed summary
                    summary = await self.get_summary(result.data[0]["title"])
                    
                    if summary.success:
                        return ToolResult(
                            success=True,
                            data={
                                "question": question,
                                "answer": summary.data.get("extract", ""),
                                "source": summary.data.get("title", ""),
                                "url": summary.data.get("url", "")
                            },
                            metadata={"search_term": search_term}
                        )
        
        return ToolResult(success=False, data=None, error="Could not find answer")


# ============================================
# TOOL 2: GITHUB DEVELOPER TOOL
# ============================================

class GitHubTool:
    """
    GitHub API tool for developers.
    
    Capabilities:
    - Search repositories
    - Get file contents
    - Search code
    - Get issues/PRs
    - Get user info
    - Analyze code
    """
    
    def __init__(self, token: str = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
    
    async def _request(self, endpoint: str) -> Optional[Dict]:
        """Make authenticated request to GitHub API"""
        url = f"{self.base_url}{endpoint}"
        
        cmd = ["curl", "-s", "-L"]
        
        for k, v in self.headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
        
        cmd.append(url)
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        
        try:
            return json.loads(stdout.decode())
        except:
            return None
    
    async def search_repos(self, query: str, limit: int = 5) -> ToolResult:
        """Search repositories"""
        try:
            data = await self._request(f"/search/repositories?q={quote(query)}&per_page={limit}")
            
            if not data:
                return ToolResult(success=False, data=None, error="API request failed")
            
            results = []
            for repo in data.get("items", [])[:limit]:
                results.append({
                    "name": repo.get("name", ""),
                    "full_name": repo.get("full_name", ""),
                    "description": repo.get("description", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "url": repo.get("html_url", ""),
                    "forks": repo.get("forks_count", 0)
                })
            
            return ToolResult(
                success=True,
                data=results,
                metadata={"query": query, "count": len(results)}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def get_file(self, repo: str, path: str) -> ToolResult:
        """Get file contents from repository"""
        try:
            # Handle both full name (owner/repo) and just repo name
            if "/" not in repo:
                return ToolResult(success=False, data=None, error="Use format: owner/repo")
            
            data = await self._request(f"/repos/{repo}/contents/{path}")
            
            if not data:
                return ToolResult(success=False, data=None, error="File not found")
            
            # Decode content
            import base64
            content = ""
            if data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8")
            
            return ToolResult(
                success=True,
                data={
                    "name": data.get("name", ""),
                    "path": data.get("path", ""),
                    "content": content[:50000],  # Limit size
                    "size": data.get("size", 0),
                    "type": data.get("type", ""),
                    "url": data.get("html_url", "")
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def search_code(self, query: str, repo: str = None, limit: int = 5) -> ToolResult:
        """Search code in repositories"""
        try:
            q = query
            if repo:
                q += f" repo:{repo}"
            
            data = await self._request(f"/search/code?q={quote(q)}&per_page={limit}")
            
            if not data:
                return ToolResult(success=False, data=None, error="Search failed")
            
            results = []
            for item in data.get("items", [])[:limit]:
                results.append({
                    "name": item.get("name", ""),
                    "path": item.get("path", ""),
                    "repository": item.get("repository", {}).get("full_name", ""),
                    "url": item.get("html_url", ""),
                    "score": item.get("score", 0)
                })
            
            return ToolResult(
                success=True,
                data=results,
                metadata={"query": query, "repo": repo}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def get_issues(self, repo: str, state: str = "open", limit: int = 10) -> ToolResult:
        """Get repository issues"""
        try:
            data = await self._request(f"/repos/{repo}/issues?state={state}&per_page={limit}")
            
            if not data:
                return ToolResult(success=False, data=None, error="Failed to get issues")
            
            issues = []
            for issue in data[:limit]:
                issues.append({
                    "number": issue.get("number", 0),
                    "title": issue.get("title", ""),
                    "state": issue.get("state", ""),
                    "user": issue.get("user", {}).get("login", ""),
                    "labels": [l.get("name", "") for l in issue.get("labels", [])],
                    "url": issue.get("html_url", ""),
                    "comments": issue.get("comments", 0)
                })
            
            return ToolResult(
                success=True,
                data=issues,
                metadata={"repo": repo, "state": state, "count": len(issues)}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def get_readme(self, repo: str) -> ToolResult:
        """Get repository README"""
        try:
            data = await self._request(f"/repos/{repo}/readme")
            
            if not data:
                return ToolResult(success=False, data=None, error="No README found")
            
            import base64
            content = ""
            if data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8")
            
            return ToolResult(
                success=True,
                data={
                    "name": data.get("name", "README"),
                    "content": content[:50000],
                    "url": data.get("html_url", "")
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


# ============================================
# TOOL 3: STACK OVERFLOW SOLUTION FINDER
# ============================================

class StackOverflowTool:
    """
    Stack Exchange API tool for finding solutions to problems.
    
    Capabilities:
    - Search questions
    - Get answers
    - Find solutions by error message
    - Search by tags
    """
    
    def __init__(self):
        self.base_url = "https://api.stackexchange.com/2.3"
    
    async def search(self, query: str, limit: int = 5) -> ToolResult:
        """Search Stack Overflow"""
        try:
            params = {
                "order": "desc",
                "sort": "relevance",
                "intitle": query,
                "site": "stackoverflow",
                "pagesize": limit
            }
            
            url = f"{self.base_url}/search?{urlencode(params)}"
            
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            data = json.loads(stdout.decode())
            
            results = []
            for item in data.get("items", [])[:limit]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "score": item.get("score", 0),
                    "is_answered": item.get("is_answered", False),
                    "answer_count": item.get("answer_count", 0),
                    "tags": item.get("tags", [])[:5]
                })
            
            return ToolResult(
                success=True,
                data=results,
                metadata={"query": query, "count": len(results)}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def search_error(self, error: str, limit: int = 5) -> ToolResult:
        """Search for error message solutions"""
        # Clean up error message
        cleaned_error = error.replace(":", " ").replace("[", " ").replace("]", " ")
        
        return await self.search(cleaned_error, limit)
    
    async def get_answers(self, question_id: int, limit: int = 3) -> ToolResult:
        """Get answers for a question"""
        try:
            params = {
                "order": "desc",
                "sort": "votes",
                "site": "stackoverflow",
                "pagesize": limit
            }
            
            url = f"{self.base_url}/questions/{question_id}/answers?{urlencode(params)}"
            
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            data = json.loads(stdout.decode())
            
            answers = []
            for answer in data.get("items", [])[:limit]:
                # Get body without HTML
                body = answer.get("body_markdown", "")[:2000]
                
                answers.append({
                    "score": answer.get("score", 0),
                    "is_accepted": answer.get("is_accepted", False),
                    "body": body,
                    "link": answer.get("link", "")
                })
            
            return ToolResult(
                success=True,
                data=answers,
                metadata={"question_id": question_id, "count": len(answers)}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def search_tag(self, tag: str, query: str, limit: int = 5) -> ToolResult:
        """Search within a specific tag"""
        try:
            params = {
                "order": "desc",
                "sort": "relevance",
                "intitle": query,
                "tagged": tag,
                "site": "stackoverflow",
                "pagesize": limit
            }
            
            url = f"{self.base_url}/search?{urlencode(params)}"
            
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            data = json.loads(stdout.decode())
            
            results = []
            for item in data.get("items", [])[:limit]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "score": item.get("score", 0),
                    "is_answered": item.get("is_answered", False)
                })
            
            return ToolResult(
                success=True,
                data=results,
                metadata={"tag": tag, "query": query}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


# ============================================
# TOOL 4: BROWSER AUTOMATION TOOL
# ============================================

class BrowserTool:
    """
    Full browser automation using Playwright.
    
    This tool gives AI agents control over a real browser,
    enabling interaction with ANY website.
    
    Capabilities:
    - Navigate to URLs
    - Click elements
    - Type text
    - Extract data
    - Take screenshots
    - Execute JavaScript
    - Fill forms
    - Handle dynamic content
    """
    
    def __init__(self):
        self.playwright_script = """
const { chromium } = require('playwright');

async function execute(action, params) {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    
    try {
        switch(action) {
            case 'navigate':
                await page.goto(params.url, { waitUntil: 'networkidle' });
                return { success: true, url: page.url() };
            
            case 'click':
                await page.click(params.selector);
                return { success: true };
            
            case 'type':
                await page.fill(params.selector, params.text);
                return { success: true };
            
            case 'screenshot':
                await page.screenshot({ path: params.path || 'screenshot.png' });
                return { success: true, path: params.path || 'screenshot.png' };
            
            case 'get_text':
                const text = await page.textContent(params.selector || 'body');
                return { success: true, text };
            
            case 'get_html':
                const html = await page.content();
                return { success: true, html: html.slice(0, 50000) };
            
            case 'evaluate':
                const result = await page.evaluate(params.script);
                return { success: true, result: String(result) };
            
            case 'search':
                await page.goto('https://www.google.com');
                await page.fill('textarea[name="q"]', params.query);
                await page.press('textarea[name="q"]', 'Enter');
                await page.waitForLoadState('networkidle');
                return { success: true, url: page.url() };
            
            default:
                return { success: false, error: 'Unknown action' };
        }
    } catch (e) {
        return { success: false, error: e.message };
    } finally {
        await browser.close();
    }
}

// Run
const action = process.argv[2];
const params = JSON.parse(process.argv[3] || '{}');
execute(action, params).then(r => console.log(JSON.stringify(r)));
"""
    
    async def execute(self, action: str, params: Dict) -> ToolResult:
        """Execute browser action"""
        try:
            # Write script to temp file
            script_path = os.path.join(os.path.dirname(__file__), "_browser_temp.js")
            Path(script_path).write_text(self.playwright_script)
            
            # Execute
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c",
                f"""
import subprocess
import json
result = subprocess.run(
    ['node', r'{script_path}', '{action}', json.dumps({json.dumps(params)})],
    capture_output=True, timeout=30
)
print(result.stdout.decode())
"""
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=35)
            
            try:
                result = json.loads(stdout.decode())
                return ToolResult(
                    success=result.get("success", False),
                    data=result,
                    metadata={"action": action}
                )
            except:
                return ToolResult(success=False, data=stdout.decode()[:500], error="Parse error")
            
        except asyncio.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Browser action timeout")
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def navigate(self, url: str) -> ToolResult:
        """Navigate to URL"""
        return await self.execute("navigate", {"url": url})
    
    async def search(self, query: str) -> ToolResult:
        """Search the web (opens Google)"""
        return await self.execute("search", {"query": query})
    
    async def click(self, selector: str) -> ToolResult:
        """Click element"""
        return await self.execute("click", {"selector": selector})
    
    async def type(self, selector: str, text: str) -> ToolResult:
        """Type text into element"""
        return await self.execute("type", {"selector": selector, "text": text})
    
    async def screenshot(self, path: str = "screenshot.png") -> ToolResult:
        """Take screenshot"""
        return await self.execute("screenshot", {"path": path})
    
    async def get_text(self, selector: str = None) -> ToolResult:
        """Get text from page/element"""
        return await self.execute("get_text", {"selector": selector or "body"})
    
    async def get_html(self) -> ToolResult:
        """Get page HTML"""
        return await self.execute("get_html", {})


# ============================================
# TOOL 5: GENERAL WEB SCRAPER
# ============================================

class WebScraperTool:
    """
    General web scraping with multiple backends.
    
    Capabilities:
    - Simple HTML fetch
    - JavaScript-rendered pages (browser)
    - Structured data extraction
    - Table extraction
    - Link extraction
    """
    
    def __init__(self):
        pass
    
    async def fetch(self, url: str, selector: str = None) -> ToolResult:
        """Fetch HTML from URL"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", "-A", "Mozilla/5.0", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            html = stdout.decode("utf-8", errors="ignore")
            
            # Extract text if selector provided
            content = html
            if selector:
                # Simple regex extraction (not perfect but works)
                match = re.search(rf'<{selector}[^>]*>(.*?)</{selector}>', html, re.DOTALL)
                if match:
                    content = match.group(1)
                else:
                    content = "Selector not found"
            
            # Clean HTML
            text = re.sub(r'<[^>]+>', ' ', content)
            text = re.sub(r'\s+', ' ', text).strip()
            
            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "html": html[:100000],
                    "text": text[:10000]
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def extract_links(self, url: str) -> ToolResult:
        """Extract all links from page"""
        try:
            result = await self.fetch(url)
            
            if not result.success:
                return result
            
            # Extract links
            links = re.findall(r'href=["\']([^"\']+)["\']', result.data["html"])
            
            # Filter and clean
            clean_links = []
            for link in links:
                if link.startswith("http"):
                    clean_links.append(link)
                elif link.startswith("/"):
                    from urllib.parse import urljoin
                    clean_links.append(urljoin(url, link))
            
            # Deduplicate
            clean_links = list(set(clean_links))[:50]
            
            return ToolResult(
                success=True,
                data={"url": url, "links": clean_links},
                metadata={"count": len(clean_links)}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def extract_tables(self, url: str) -> ToolResult:
        """Extract tables from page"""
        try:
            result = await self.fetch(url)
            
            if not result.success:
                return result
            
            # Find tables
            tables = re.findall(r'<table[^>]*>(.*?)</table>', result.data["html"], re.DOTALL)
            
            extracted = []
            for table_html in tables[:5]:  # Limit to 5 tables
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
                
                table_data = []
                for row in rows[:20]:  # Limit rows
                    cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
                    cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                    if cells:
                        table_data.append(cells)
                
                if table_data:
                    extracted.append(table_data)
            
            return ToolResult(
                success=True,
                data={"url": url, "tables": extracted},
                metadata={"count": len(extracted)}
            )
            
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


# ============================================
# TOOL 6: DOCUMENTATION READER
# ============================================

class DocReaderTool:
    """
    Read and search documentation.
    
    Capabilities:
    - Search documentation
    - Get sections
    - Find examples
    - Read API reference
    """
    
    def __init__(self):
        # Known doc sources
        self.doc_sources = {
            "python": "https://docs.python.org/3/",
            "javascript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
            "react": "https://react.dev/reference",
            "node": "https://nodejs.org/docs/latest/api/",
            "typescript": "https://www.typescriptlang.org/docs/",
            "docker": "https://docs.docker.com/",
            "git": "https://git-scm.com/doc",
            "github": "https://docs.github.com/en"
        }
        
        self.scraper = WebScraperTool()
    
    async def search(self, framework: str, query: str) -> ToolResult:
        """Search documentation"""
        base_url = self.doc_sources.get(framework.lower())
        
        if not base_url:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown framework: {framework}. Available: {list(self.doc_sources.keys())}"
            )
        
        # Search using browser
        browser = BrowserTool()
        
        # Navigate to search
        search_url = f"{base_url}?search={quote(query)}"
        
        result = await browser.navigate(search_url)
        
        if result.success:
            # Get text
            text_result = await browser.get_text()
            
            return ToolResult(
                success=True,
                data={
                    "framework": framework,
                    "query": query,
                    "url": search_url,
                    "content": text_result.data.get("text", "")[:5000] if text_result.success else ""
                },
                metadata={"source": base_url}
            )
        
        return result
    
    async def get_page(self, url: str) -> ToolResult:
        """Get documentation page"""
        return await self.scraper.fetch(url)


# ============================================
# TOOL 7: UNIFIED SEARCH (Multi-Source)
# ============================================

class UnifiedSearchTool:
    """
    Search multiple sources at once.
    
    This is the "one search to rule them all" tool.
    """
    
    def __init__(self):
        self.wikipedia = WikipediaTool()
        self.github = GitHubTool()
        self.stackoverflow = StackOverflowTool()
        self.web_scraper = WebScraperTool()
    
    async def search_all(self, query: str) -> ToolResult:
        """Search all sources"""
        results = {
            "query": query,
            "sources": {}
        }
        
        # Run searches in parallel
        tasks = [
            self._safe_search(self.wikipedia.search, query, "wikipedia"),
            self._safe_search(self.github.search_repos, query, "github"),
            self._safe_search(self.stackoverflow.search, query, "stackoverflow"),
        ]
        
        search_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, r in enumerate(search_results):
            source = ["wikipedia", "github", "stackoverflow"][i]
            if isinstance(r, Exception):
                results["sources"][source] = {"error": str(r)}
            else:
                results["sources"][source] = r
        
        return ToolResult(
            success=True,
            data=results,
            metadata={"sources_searched": len(search_results)}
        )
    
    async def _safe_search(self, func, query: str, source: str) -> Dict:
        """Wrapper for safe searching"""
        try:
            if source == "wikipedia":
                result = await func(query, limit=3)
            elif source == "github":
                result = await func(query, limit=3)
            elif source == "stackoverflow":
                result = await func(query, limit=3)
            
            return result.data if hasattr(result, "data") else {}
        except Exception as e:
            return {"error": str(e)}


# ============================================
# TOOL 8: WEB RESEARCH AGENT
# ============================================

class WebResearchAgent:
    """
    Orchestrates all tools for comprehensive research.
    
    This is the "brain" that decides which tools to use
    based on the research goal.
    """
    
    def __init__(self):
        self.wikipedia = WikipediaTool()
        self.github = GitHubTool()
        self.stackoverflow = StackOverflowTool()
        self.browser = BrowserTool()
        self.scraper = WebScraperTool()
        self.doc_reader = DocReaderTool()
        self.unified_search = UnifiedSearchTool()
    
    async def research(self, topic: str, depth: str = "basic") -> ToolResult:
        """
        Comprehensive research on a topic.
        
        depth: "basic", "medium", "deep"
        """
        results = {
            "topic": topic,
            "depth": depth,
            "findings": []
        }
        
        if depth == "basic":
            # Quick overview
            wiki = await self.wikipedia.get_summary(topic)
            if wiki.success:
                results["findings"].append({
                    "type": "overview",
                    "source": "wikipedia",
                    "data": wiki.data
                })
            
            so = await self.stackoverflow.search(topic, limit=3)
            if so.success:
                results["findings"].append({
                    "type": "solutions",
                    "source": "stackoverflow",
                    "data": so.data
                })
        
        elif depth in ["medium", "deep"]:
            # Full research
            # 1. Unified search
            unified = await self.unified_search.search_all(topic)
            if unified.success:
                results["findings"].append({
                    "type": "multi_source",
                    "data": unified.data
                })
            
            # 2. Code examples from GitHub
            code = await self.github.search_code(topic, limit=5)
            if code.success:
                results["findings"].append({
                    "type": "code_examples",
                    "source": "github",
                    "data": code.data
                })
            
            # 3. Stack Overflow solutions
            so = await self.stackoverflow.search(topic, limit=5)
            if so.success:
                results["findings"].append({
                    "type": "solutions",
                    "source": "stackoverflow",
                    "data": so.data
                })
            
            # 4. Wikipedia deep dive
            wiki = await self.wikipedia.get_summary(topic)
            if wiki.success:
                results["findings"].append({
                    "type": "knowledge",
                    "source": "wikipedia",
                    "data": wiki.data
                })
        
        return ToolResult(
            success=True,
            data=results,
            metadata={"depth": depth, "sources": len(results["findings"])}
        )
    
    async def solve_problem(self, problem: str) -> ToolResult:
        """
        Try to solve a technical problem using multiple sources.
        """
        results = {
            "problem": problem,
            "solutions": []
        }
        
        # 1. Search Stack Overflow first
        so = await self.stackoverflow.search_error(problem, limit=5)
        if so.success and so.data:
            results["solutions"].append({
                "source": "stackoverflow",
                "data": so.data
            })
        
        # 2. Try GitHub for related issues
        # Extract key terms
        terms = problem.split()[:5]
        search_term = " ".join(terms)
        
        github = await self.github.search_repos(search_term, limit=3)
        if github.success:
            results["solutions"].append({
                "source": "github",
                "data": github.data
            })
        
        # 3. Wikipedia for concepts
        wiki = await self.wikipedia.ask_question(problem)
        if wiki.success:
            results["solutions"].append({
                "source": "wikipedia",
                "data": wiki.data
            })
        
        return ToolResult(
            success=True,
            data=results,
            metadata={"sources_used": len(results["solutions"])}
        )


# ============================================
# MAIN CLI
# ============================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Nexus Fundamental Tools")
    parser.add_argument("--tool", help="Tool to use")
    parser.add_argument("--action", help="Action within tool")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--url", help="URL for web tools")
    parser.add_argument("--list", action="store_true", help="List all tools")
    
    args = parser.parse_args()
    
    print("""
============================================================
  NEXUS FUNDAMENTAL TOOLS SUITE
============================================================
  
  Tools that turn the web into an addressable environment
============================================================
    """)
    
    # List tools
    tools = [
        ("wikipedia", "WikipediaTool", "Search and read Wikipedia articles"),
        ("github", "GitHubTool", "Search repos, code, issues on GitHub"),
        ("stackoverflow", "StackOverflowTool", "Find solutions to problems"),
        ("browser", "BrowserTool", "Full browser automation"),
        ("scraper", "WebScraperTool", "General web scraping"),
        ("docs", "DocReaderTool", "Read documentation"),
        ("search", "UnifiedSearchTool", "Search multiple sources"),
        ("research", "WebResearchAgent", "Comprehensive research agent")
    ]
    
    if args.list:
        print("\nAvailable Tools:")
        print("-" * 60)
        for name, cls, desc in tools:
            print(f"  {name:20} - {desc}")
        return
    
    # Example usage
    print("\nTool Usage Examples:")
    print("-" * 60)
    print("  python fused_tools.py --tool wikipedia --action search --query 'python'")
    print("  python fused_tools.py --tool github --action search_repos --query 'react'")
    print("  python fused_tools.py --tool stackoverflow --action search --query 'async await error'")
    print("  python fused_tools.py --tool research --action research --query 'machine learning'")
    print("  python fused_tools.py --tool search --action search_all --query 'neural networks'")


if __name__ == "__main__":
    asyncio.run(main())