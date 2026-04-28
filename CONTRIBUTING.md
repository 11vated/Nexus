# Contributing to Nexus

Thank you for your interest in contributing to Nexus. This document outlines the process for contributing and the standards we follow.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](https://github.com/11vated/Nexus/blob/main/CODE_OF_CONDUCT.md). Please be respectful and constructive.

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists
2. Create a detailed issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details
   - Log snippets if applicable

### Suggesting Features

1. Check existing issues and discussions
2. Open a feature request with:
   - Clear description of the feature
   - Use case and motivation
   - Potential implementation approach
   - Alternatives considered

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes following our style guide
4. Add tests for new functionality
5. Update documentation as needed
6. Commit with clear messages: `git commit -m "feat: add new feature"`
7. Push and create a Pull Request

## Development Process

### Required Checks

All PRs must pass:
- [ ] Unit tests pass
- [ ] Linting passes (`ruff check`)
- [ ] Type checking passes (`mypy`)
- [ ] No security issues (`bandit`)

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance

Examples:
```
feat(security): add model name validation
fix(cli): resolve timeout issue
docs: update developer guide
test: add unit tests for cache
```

### Code Style

- Use Python 3.10+ features
- Add type hints where possible
- Use f-strings for formatting
- Maximum line length: 100
- Use descriptive variable names

### Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest --cov=nexus --cov-report=html

# Specific test
pytest tests/unit/test_security/test_sanitizer.py -v
```

### Security Requirements

- Never commit secrets or API keys
- Use environment variables for sensitive data
- Validate all user inputs
- Avoid `shell=True` in subprocess calls
- Run security checks: `bandit -r src/`

## Review Process

1. Maintainers will review within 48 hours
2. Address feedback promptly
3. Once approved, a maintainer will merge

## Recognition

Contributors will be added to the README.md hall of fame.

## Questions?

- Open a discussion
- Join our community chat
- Email: maintainers@nexus.dev

We appreciate all contributions, from bug reports to documentation improvements!