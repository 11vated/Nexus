---
name: coding-review
description: Perform adversarial code review to find bugs and improvements - use PROACTIVELY before any commit
tools: Read, Glob, Grep
model: qwen2.5-coder:14b
---
# Code Review Skill

## When to Use
- Before any commit or PR
- After implementing new features
- When fixing bugs

## Review Checklist

### Correctness
- [ ] Does the code solve the stated problem?
- [ ] Are edge cases handled?
- [ ] Does it pass existing tests?

### Security
- [ ] No hardcoded secrets/API keys
- [ ] Input validation present
- [ ] SQL injection prevention (parameterized queries)

### Performance
- [ ] No N+1 queries
- [ ] Proper indexing
- [ ] Efficient data structures

### Code Quality
- [ ] Clear variable names
- [ ] Functions under 50 lines
- [ ] No code duplication

### Testing
- [ ] Unit tests for new code
- [ ] Edge cases tested
- [ ] Test coverage maintained

## Review Process

1. **Read the changed files**
2. **Check for common issues**:
   - Unused imports/variables
   - Missing error handling
   - Race conditions
   - Memory leaks
3. **Run tests**: `pytest --tb=short`
4. **Check lint**: `ruff check .`

## Output Format
```
REVIEW: [PASS/FAIL]
Issues found:
- [issue 1]
- [issue 2]
Confidence: X%
```