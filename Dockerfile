FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --user -e .

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app/src

EXPOSE 8000 8080

LABEL org.opencontainers.image.source="https://github.com/11vated/Nexus"
LABEL org.opencontainers.image.description="Nexus - Ultimate AI Agent Workstation"

CMD ["python", "-m", "nexus.cli", "--help"]