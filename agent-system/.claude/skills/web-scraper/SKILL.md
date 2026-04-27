---
name: web-scraper
description: Fetch and parse web pages using requests and BeautifulSoup
tools: Bash
model: qwen2.5-coder:14b
---
# Web Scraper Skill

## Usage
- Fetch HTML from URLs
- Parse with BeautifulSoup
- Extract data

## Templates

### Basic Fetch
```python
import requests
from bs4 import BeautifulSoup

r = requests.get(url)
soup = BeautifulSoup(r.text, 'html.parser')
# Extract data
```

### JSON API
```python
import requests
r = requests.get(api_url)
data = r.json()
```