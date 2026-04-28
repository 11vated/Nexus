# Changelog

All notable changes to Nexus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-27

### Added

**Security**
- `shell=True` vulnerability fixed in `unified_cli.py`
- Model name whitelist validation
- Path traversal prevention (`safe_path_join`)
- Command argument validation
- Prompt injection sanitization
- `SecretManager` for API key encryption
- Rate limiting utilities (`RateLimiter`, `TokenBucket`)
- Security policy document (`SECURITY.md`)

**Configuration**
- `NexusConfig` using Pydantic Settings
- `.env` file support with `.env.example`
- Centralized configuration system

**Testing**
- Comprehensive unit tests for security module
- Edge case tests for vulnerabilities
- Integration tests for subprocess utilities
- Retry/circuit breaker tests
- Config tests
- Logging tests
- Test fixtures and configuration

**CLI**
- Click-based CLI interface
- Model management commands
- Tool management commands
- Workspace management
- Configuration commands

**Performance**
- `OllamaCache` for response caching
- `PersistentCache` for file-based caching
- `TaskQueue` for async task execution
- `ParallelExecutor` for concurrent execution
- `BatchRunner` for batch processing

**Metrics & Observability**
- Prometheus metrics utilities
- Tool, model, agent, cache, HTTP metrics
- Custom metrics support

**Deployment**
- Dockerfile for production
- `docker-compose.yml` for local development
- Dockerfile.test for CI
- GitHub Actions CI workflow

**Documentation**
- DEVELOPER.md guide
- CONTRIBUTING.md guidelines
- Pre-commit hooks configuration
- Security documentation

### Known Issues

- Some legacy `shell=True` usages remain in agent-system (documentation created)
- Initial release - some features are marked as alpha

## [0.0.1] - 2026-04-?? (Pre-release)

Initial pre-release containing:
- Basic multi-agent architecture
- Ollama integration
- Aider wrapper
- Initial CLI