import subprocess
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path


class WebResearchTool:
    """Uses Ollama + free search - NO API KEYS"""
    
    def __init__(self):
        self.cache = {}
        self.results_history = []
    
    def search(self, query: str, num_results: int = 5) -> List[Dict]:
        if query in self.cache:
            print(f"[RESEARCH] Cache hit: {query}")
            return self.cache[query]
        
        prompt = f"""Research: {query}

Find {num_results} relevant, real websites with working URLs.
Use knowledge of:
- Official documentation sites
- GitHub repositories  
- Stack Overflow answers
- Tutorial sites

Return JSON array with: title, url, snippet
No invented URLs - only real, verified sites.
"""
        
        try:
            result = subprocess.run(
                f'ollama run qwen2.5-coder:14b "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            data = json.loads(result.stdout.strip("`").strip("json")[:500])
            if isinstance(data, dict):
                data = data.get("results", [data])
            
            self.cache[query] = data
            self.results_history.append({
                "query": query,
                "results": data,
                "timestamp": datetime.now().isoformat()
            })
            return data
        except Exception as e:
            return [{"error": str(e), "fallback": "use local knowledge"}]
    
    def search_documentation(self, library: str, query: str = "") -> Dict:
        doc_known = {
            "flask": "https://flask.palletsprojects.com/",
            "django": "https://docs.djangoproject.com/",
            "fastapi": "https://fastapi.tiangolo.com/",
            "requests": "https://docs.python-requests.org/",
            "pytest": "https://docs.pytest.org/",
            "numpy": "https://numpy.org/doc/",
            "pandas": "https://pandas.pydata.org/docs/",
            "react": "https://react.dev/",
            "vue": "https://vuejs.org/guide/",
            "node": "https://nodejs.org/docs/"
        }
        
        url = doc_known.get(library.lower(), f"https://{library.lower()}.js.org")
        
        return {
            "library": library,
            "url": url,
            "query": query
        }
    
    def find_best_library(self, task: str) -> Dict:
        known_gems = {
            "http": {"name": "requests", "stars": "50k", "desc": "HTTP for humans"},
            "web server": {"name": "fastapi", "stars": "65k", "desc": "Modern web framework"},
            "async": {"name": "asyncio", "stars": "built-in", "desc": "Python standard library"},
            "testing": {"name": "pytest", "stars": "11k", "desc": "Testing framework"},
            "api": {"name": "fastapi", "stars": "65k", "desc": "Fast API building"},
            "database": {"name": "sqlalchemy", "stars": "24k", "desc": "Database ORM"},
            "auth": {"name": "python-jose", "stars": "2k", "desc": "JWT tokens"},
        }
        
        task_lower = task.lower()
        best = known_gems.get(task_lower, known_gems.get(task_lower.split()[0], {}))
        
        if not best:
            return {
                "task": task,
                "recommended": "requests",
                "stars": "50k",
                "desc": "HTTP library",
                "note": "Based on general knowledge"
            }
        
        return {
            "task": task,
            "recommended": best.get("name", "requests"),
            "stars": best.get("stars", "?"),
            "desc": best.get("desc", "")
        }
    
    def get_trending(self, category: str = "python") -> List[str]:
        trending = {
            "python": ["fastapi", "pydantic", "ruff", "uv", "polars"],
            "javascript": ["nextjs", "tailwind", "vite", "bun"],
            "ai": ["llama.cpp", "ollama", "aider", "opencode"]
        }
        
        return trending.get(category, trending["python"])


class GitHubResearchTool:
    """Uses curl to GitHub API - FREE rate limit (no token needed)"""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
    
    def search_repos(self, query: str, language: str = "Python") -> List[Dict]:
        search_url = f"{self.base_url}/search/repositories?q={query}+language:{language}&sort=stars&per_page=5"
        
        try:
            result = subprocess.run(
                ["curl", "-s", search_url],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            data = json.loads(result.stdout)
            items = data.get("items", [])[:5]
            
            return [{
                "name": r.get("full_name"),
                "stars": r.get("stargazers_count"),
                "description": r.get("description"),
                "url": r.get("html_url"),
                "language": r.get("language")
            } for r in items]
        except Exception as e:
            return [{"error": str(e)}]
    
    def search_code(self, query: str, language: str = "Python") -> List[Dict]:
        search_url = f"{self.base_url}/search/code?q={query}+language:{language}&per_page=5"
        
        try:
            result = subprocess.run(
                ["curl", "-s", search_url],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            data = json.loads(result.stdout)
            items = data.get("items", [])[:5]
            
            return [{
                "name": r.get("name"),
                "path": r.get("path"),
                "repository": r.get("repository", {}).get("full_name"),
                "url": r.get("html_url")
            } for r in items]
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_trending(self, language: str = "Python", days: int = 7) -> List[Dict]:
        from datetime import datetime, timedelta
        date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        search_url = f"{self.base_url}/search/repositories?q=created:>{date}+language:{language}&sort=stars&per_page=10"
        
        try:
            result = subprocess.run(
                ["curl", "-s", search_url],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            data = json.loads(result.stdout)
            items = data.get("items", [])[:10]
            
            return [{
                "name": r.get("full_name"),
                "stars": r.get("stargazers_count"),
                "description": r.get("description")
            } for r in items]
        except Exception as e:
            return [{"error": str(e)}]


class ResearchOrchestrator:
    """100% FREE - NO API KEYS"""
    
    def __init__(self):
        self.web = WebResearchTool()
        self.github = GitHubResearchTool()
    
    def research_task(self, task: str) -> Dict:
        print(f"[RESEARCH] {task}")
        
        lib = self.web.find_best_library(task)
        
        return {
            "task": task,
            "best_libraries": lib,
            "status": "free",
            "timestamp": datetime.now().isoformat()
        }
    
    def find_code_patterns(self, task: str) -> List[Dict]:
        results = self.github.search_code(task)
        return results
    
    def get_best_repo(self, task: str, language: str = "Python") -> Dict:
        results = self.github.search_repos(task, language)
        
        if not results:
            return {"error": "No results"}
        
        best = max(results, key=lambda x: x.get("stars", 0))
        
        return best


def create_researcher() -> ResearchOrchestrator:
    return ResearchOrchestrator()


class DocumentationTool:
    """Free documentation fetcher - NO API KEY"""
    
    known_docs = {
        "python": "https://docs.python.org/3/",
        "flask": "https://flask.palletsprojects.com/",
        "fastapi": "https://fastapi.tiangolo.com/",
        "django": "https://docs.djangoproject.com/",
        "requests": "https://docs.python-requests.org/",
        "pytest": "https://docs.pytest.org/",
        "numpy": "https://numpy.org/doc/",
        "pandas": "https://pandas.pydata.org/docs/",
    }
    
    def get_url(self, library: str) -> str:
        return self.known_docs.get(library.lower(), f"https://{library.lower()}.dev")
    
    def fetch(self, url: str) -> str:
        try:
            result = subprocess.run(
                ["curl", "-s", url],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout[:1000]
        except Exception as e:
            return f"[ERROR] {str(e)}"