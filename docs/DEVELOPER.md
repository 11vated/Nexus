# Developer Guide

Welcome to the Nexus developer documentation. This guide will help you set up a development environment and start contributing to Nexus.

## Prerequisites

- Python 3.10 or higher
- Git
- Docker (for containerized development)
- Ollama (for local LLM inference)

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/11vated/Nexus.git
cd Nexus

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
```

### 3. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=nexus --cov-report=html
```

### 4. Run Development Server

```bash
# Start health API
python -m nexus.api.health

# Or use the CLI
python -m nexus.cli --help
```

## Project Structure

```
nexus/
├── src/nexus/           # Main source code
│   ├── api/            # FastAPI health endpoints
│   ├── config/         # Configuration management
│   ├── core/           # Core agent logic
│   ├── security/       # Security utilities
│   ├── tools/          # Tool wrappers
│   └── utils/          # Utilities
├── tests/              # Test suite
├── docs/               # Documentation
└── scripts/            # Helper scripts
```

## Running with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Code Style

We use:
- **Ruff** for linting
- **Black** for formatting
- **mypy** for type checking

Run checks:

```bash
# Lint
ruff check src/

# Format
ruff format src/

# Type check
mypy src/
```

## Pre-commit Hooks

Install pre-commit to run checks automatically:

```bash
pip install pre-commit
pre-commit install
```

## Adding a New Tool

1. Create tool in `src/nexus/tools/`
2. Add validation in `src/nexus/security/sanitizer.py`
3. Add tests in `tests/`
4. Update CLI in `src/nexus/cli.py`

## Running Specific Tests

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_security/test_sanitizer.py -v

# With verbose output
pytest -vv --tb=long
```

## Debugging

### VS Code

```json
{
    "configurations": [
        {
            "name": "Python: Nexus",
            "type": "python",
            "request": "launch",
            "module": "nexus.cli",
            "args": ["--help"]
        }
    ]
}
```

### Logging

Set `LOG_LEVEL=DEBUG` in your `.env` for detailed logging.

## Common Tasks

### Add a New Configuration

Edit `src/nexus/config/settings.py` to add a new config option with proper Pydantic validation.

### Modify Health Checks

Edit `src/nexus/api/health.py` to add or modify health check endpoints.

### Add Security Validation

Add new validation functions in `src/nexus/security/sanitizer.py`.

## Troubleshooting

### Ollama Not Running

```bash
# Start Ollama
ollama serve

# Pull a model
ollama pull qwen2.5-coder:14b
```

### Import Errors

Make sure you've installed in development mode:
```bash
pip install -e ".[dev]"
```

### Test Failures

Check that all dependencies are installed:
```bash
pip install -e ".[dev,all]"
```

## Next Steps

- Read [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
- Check [SECURITY.md](SECURITY.md) for security policies
- See [CHANGELOG.md](CHANGELOG.md) for version history