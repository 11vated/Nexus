---
name: dockerize
description: Create Docker containers for applications - use when deploying
tools: Write, Glob, Bash
model: qwen2.5-coder:14b
---
# Dockerize Skill

## Dockerfile Template
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## Commands
```bash
docker build -t app .
docker run -p 5000:5000 app
```