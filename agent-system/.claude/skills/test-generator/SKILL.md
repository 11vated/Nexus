---
name: test-generator
description: Generate comprehensive tests for Python code - use when creating new functions or fixing bugs
tools: Read, Write, Glob
model: qwen2.5-coder:14b
---
# Test Generator Skill

## When to Use
- Creating new Python functions/modules
- After fixing bugs (add regression tests)
- Before refactoring

## Test Structure

```python
# test_[module].py
import pytest
from module import function

def test_function_success():
    result = function(input)
    assert result == expected

def test_function_edge_case():
    with pytest.raises(Exception):
        function(invalid_input)
```

## Best Practices
- One assertion per test
- Test happy path + edge cases
- Use descriptive names: `test_should_return_X_when_Y`
- Mock external dependencies
- Fixtures for shared setup

## Running Tests
```bash
pytest                    # All tests
pytest -x                 # Stop on first failure
pytest -k pattern         # Filter by name
pytest --cov=module        # Coverage
```