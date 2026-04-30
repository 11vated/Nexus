# Security Policy

## Supported Versions

We currently support the following versions of Nexus with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within Nexus, please send an email to security@nexus.dev. All security vulnerabilities will be promptly addressed.

Please include the following information:

- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

## Security Principles

### Defense in Depth
Multiple layers of security controls are implemented:
- Input validation (sanitizer module)
- Whitelist-based allowlists for models and commands
- Secure subprocess execution without shell=True
- Environment variable isolation

### Least Privilege
- Subprocesses run with minimal environment variables
- No PYTHONPATH or LD_PRELOAD inheritance
- All user inputs are sanitized before use

### Secure Defaults
- Models must be explicitly whitelisted
- No shell command execution with user input
- All configuration requires explicit opt-in

## Security Features

### Input Validation
All user inputs are validated against allowlists:
- Model names must be in ALLOWED_MODELS
- Command arguments must match known patterns
- File paths are checked for directory traversal

### Secret Management
- API keys can be encrypted at rest using Fernet encryption
- Sensitive values are masked in logs
- Environment variable based configuration

### Rate Limiting
- Built-in rate limiting for tool calls
- Configurable per-user limits
- Resource quotas for memory and CPU

## Known Security Considerations

### shell=True Usage
The original codebase contains some `shell=True` usages which pose potential command injection risks. These are documented issues being addressed incrementally. All new code uses the secure `subprocess_utils.py` module for command execution.

### Local Execution
Nexus runs locally, so users should:
- Not run with elevated privileges
- Keep their system updated
- Review generated code before execution

### Model Safety
- Only use models from trusted sources
- Review model outputs before executing
- Be aware of potential prompt injection attacks

## Dependencies Security

We regularly scan dependencies for vulnerabilities:
- `bandit` - Static security analysis
- `safety` - Python dependency vulnerability scanning

Run security checks locally:
```bash
pip install bandit safety
bandit -r src/
safety check
```

## Security Updates

Security updates will be released as patch versions and announced in the changelog.