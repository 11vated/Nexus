---
name: refactor-code
description: Refactor code for clarity and efficiency - use when code is hard to understand or maintain
tools: Read, Write, Str_Replace, Bash
model: qwen2.5-coder:14b
---
# Refactor Code Skill

## When to Use
- Long functions (>50 lines)
- Duplicate code
- Unclear naming
- Technical debt

## Refactoring Patterns

### Extract Function
```python
# Before
def process(data):
    data = validate(data)
    data = transform(data)
    return save(data)

# After  
def validate(data): ...
def transform(data): ...
def save(data): ...
def process(data):
    return save(transform(validate(data)))
```

### Rename Variables
- `x` → `user_count`
- `tmp` → `temp_file_path`
- `data` → `validated_input`

### Add Type Hints
```python
def calculate(x: int, y: int) -> int:
    return x + y
```

## Tools
- `str_replace_editor` for safe edits
- Run tests after each change