---
name: debug-code
description: Debug Python code with tracebacks and errors - use when tests fail or errors occur
tools: Read, Bash, Grep
model: qwen2.5-coder:14b
---
# Debug Code Skill

## Process
1. Read error traceback
2. Identify root cause
3. Find relevant code
4. Fix and verify

## Common Patterns

### AttributeError
- Check import path
- Verify object initialization

### TypeError
- Check argument types
- Verify None handling

### ImportError
- Check PYTHONPATH
- Verify package installed

## Debug Commands
```bash
python -c "import code; code.main()"
python -m pdb script.py
pytest --tb=long
```