---
name: security-scan
description: Security audit code for vulnerabilities - use before deploying
tools: Bash, Grep, Read
model: qwen2.5-coder:14b
---
# Security Scan Skill

## Checks
- Hardcoded passwords/keys: `password=`, `api_key=`, `secret=`
- SQL injection: string formatting in queries
- XSS: unsanitized HTML input
- Command injection: user input in shell

## Commands
```bash
grep -r 'password=' --include='*.py'
grep -r 'os.system' --include='*.py'
```