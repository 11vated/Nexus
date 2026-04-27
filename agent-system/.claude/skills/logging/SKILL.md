---
name: logging
description: Implement structured logging - use in all production code
tools: Bash, Read, Write
model: qwen2.5-coder:14b
---
# Logging Skill

## Python Logging
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Starting process")
logger.error("Failed", exc_info=True)
```

## Best Practices
- Use appropriate levels: DEBUG, INFO, WARNING, ERROR
- Include context in messages
- Log exceptions with traceback