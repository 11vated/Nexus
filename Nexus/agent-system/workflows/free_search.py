import subprocess
import json
import re
from typing import Dict, List, Optional
from datetime import datetime


class DuckDuckGoSearch:
    def __init__(self):
        self.cache = {}
    
    def search(self, query: str, num_results: int = 5) -> List[Dict]:
        if query in self.cache:
            return self.cache[query]
        
        try:
            from duckduckgo_search import DDGS
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=num_results))
            
            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "relevance": 0.9
                })
            
            self.cache[query] = formatted
            return formatted
        except ImportError:
            return self._search_via_ollama(query, num_results)
        except Exception as e:
            return self._search_via_ollama(query, num_results)
    
    def _search_via_ollama(self, query: str, num_results: int) -> List[Dict]:
        prompt = f"""Search the web for: {query}

Return {num_results} results as JSON array with keys:
title, url, snippet

This is REAL web search - find actual websites with working links.
Output ONLY JSON array.
"""
        
        try:
            result = subprocess.run(
                'ollama run qwen2.5-coder:14b --verbose "web_search: {query}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            parsed = json.loads(result.stdout.strip("`").strip("json"))
            self.cache[query] = parsed
            return parsed
        except:
            return [{"error": "Install duckduckgo-search: pip install duckduckgo-search"}]
    
    def find_documentation(self, library: str) -> Dict:
        results = self.search(f"{library} documentation official site", num_results=3)
        
        return {
            "library": library,
            "doc_links": [r.get("url", "") for r in results if r.get("url")],
            "results": results
        }
    
    def find_code_examples(self, task: str) -> List[Dict]:
        results = self.search(f"{task} github code example", num_results=5)
        return results
    
    def clear_cache(self):
        self.cache = {}


class FreeWebSearch:
    """100% free web search - no API keys needed"""
    
    def __init__(self):
        self.ddg = DuckDuckGoSearch()
        self.ollama_fallback = True
    
    def search(self, query: str) -> List[Dict]:
        return self.ddg.search(query)
    
    def research(self, query: str) -> Dict:
        results = self.search(query)
        return {
            "query": query,
            "results": results,
            "num_results": len(results),
            "timestamp": datetime.now().isoformat()
        }


def create_free_searcher() -> FreeWebSearch:
    return FreeWebSearch()