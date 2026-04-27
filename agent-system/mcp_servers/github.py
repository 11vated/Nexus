import subprocess
import json
from typing import Optional, List, Dict
from pathlib import Path


class GitHubClient:
    """100% FREE GitHub client - NO TOKEN NEEDED for basic operations"""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.base_url = "https://api.github.com"
    
    def _make_request(self, endpoint: str) -> Dict:
        cmd = ["curl", "-s", f"{self.base_url}/{endpoint}"]
        
        if self.token:
            cmd.extend(["-H", f"Authorization: Bearer {self.token}"])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        try:
            return json.loads(result.stdout)
        except:
            return {"error": "Failed to parse response"}
    
    def search_repos(self, query: str, language: str = "Python") -> List[Dict]:
        endpoint = f"search/repositories?q={query}+language:{language}&sort=stars&per_page=5"
        data = self._make_request(endpoint)
        
        return [{
            "name": r.get("full_name"),
            "stars": r.get("stargazers_count"),
            "description": r.get("description"),
            "url": r.get("html_url")
        } for r in data.get("items", [])[:5]]
    
    def get_repo(self, owner: str, repo: str) -> Dict:
        endpoint = f"repos/{owner}/{repo}"
        return self._make_request(endpoint)
    
    def list_issues(self, owner: str, repo: str) -> List[Dict]:
        endpoint = f"repos/{owner}/{repo}/issues?state=open&per_page=5"
        data = self._make_request(endpoint)
        
        return [{
            "number": i.get("number"),
            "title": i.get("title"),
            "url": i.get("html_url")
        } for i in data[:5]]
    
    def create_issue(self, owner: str, repo: str, title: str, body: str = "") -> str:
        if not self.token:
            return "[ERROR] GITHUB_TOKEN required for write operations"
        
        endpoint = f"repos/{owner}/{repo}/issues"
        data = json.dumps({"title": title, "body": body})
        
        cmd = ["curl", "-s", "-X", "POST", "-H", f"Authorization: Bearer {self.token}",
              "-H", "Content-Type: application/json", "-d", data,
              f"{self.base_url}/{endpoint}"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if "id" in result.stdout:
                return "[SUCCESS] Issue created"
            return f"[INFO] {result.stdout[:200]}"
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def find_best_library(self, task: str) -> Dict:
        results = self.search_repos(task)
        
        if not results:
            return {"error": "No results"}
        
        best = max(results, key=lambda x: x.get("stars", 0))
        return best


class GitHubWorkflow:
    """GitHub workflow without requiring API token for read operations"""
    
    def __init__(self, token: Optional[str] = None):
        self.github = GitHubClient(token)
    
    def find_and_fix_issue(self, repo: str, issue_number: int) -> Dict:
        owner, repo_name = repo.split("/")[-2], repo.split("/")[-1]
        
        issues = self.github.list_issues(owner, repo_name)
        
        if not issues:
            return {"error": "No issues found"}
        
        return {
            "issue": issues[0],
            "status": "ready_for_agent",
            "workflow": "research → plan → fix → test → pr"
        }
    
    def research_best_repo(self, task: str) -> Dict:
        lib = self.github.find_best_library(task)
        return {
            "task": task,
            "recommended": lib.get("name"),
            "stars": lib.get("stars"),
            "url": lib.get("url")
        }


def create_github_client(token: Optional[str] = None) -> GitHubClient:
    return GitHubClient(token)


def create_github_workflow(token: Optional[str] = None) -> GitHubWorkflow:
    return GitHubWorkflow(token)