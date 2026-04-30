FROM python:3.12-slim

# System deps for tools (git, ripgrep, node for code_runner)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ripgrep \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Optional: Node.js for code_runner tool
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Nexus
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir -e ".[all]" 2>/dev/null || pip install --no-cache-dir -e .

# Default workspace
RUN mkdir -p /workspace
WORKDIR /workspace

# Ollama URL default (host network mode expected)
ENV NEXUS_OLLAMA_URL=http://localhost:11434

ENTRYPOINT ["nexus"]
CMD ["--help"]
