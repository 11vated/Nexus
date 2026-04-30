# AIDER SETUP - MAKE IT EXECUTE

## Quick Setup

### Option 1: Use our config file

```bash
# Copy to Aider config location
copy config_aider.toml %APPDATA%\aider.conf.yml

# Or use directly:
aider --config config_aider.toml
```

### Option 2: Run with execution flags

```bash
aider --no-read \
      --no-autosave \
      --exec-only \
      --model ollama/qwen2.5-coder:14b
```

### Option 3: Interactive command in Aider

Once in Aider:
```
/set auto-commits on
/set exec-only on
```

## Key Commands

| Command | What it does |
|---------|--------------|
| `/commit` | Actually RUN/commits |
| `/run <cmd>` | Execute shell command |
| `/exec` | Auto-execute |
| `/test` | Run tests |

## Test It Works

```bash
# Should create AND run code
aider --exec-only

> create a simple http server in python and run it
```

Expected: Creates server.py AND runs it!

---

# GOOSE SETUP - MAKE IT EXECUTE

## Quick Setup

### Option 1: Use our config

```bash
# Copy to Goose config
copy config_goose.yaml %APPDATA%\goose\config.yaml
```

### Option 2: Run with execution

```bash
goose run --execute "create flask app"
```

### Option 3: Configure in Goose

```bash
goose configure
# Enable: Execution Mode
# Provider: Ollama
# Model: qwen2.5-coder:14b
# Allow: All tools
```

## Key Commands

| Command | What it does |
|---------|--------------|
| `goose run --execute` | Execute not just chat |
| `/run` | Run command |
| `!` prefix | Run shell command |

## Test It Works

```bash
# Should create AND run code
goose run --execute "write hello world to test.py and run it"
```

Expected: Creates test.py AND runs it!


---

# THE FIX - Summary

Both Aider and Goose were JUST CHATTING because:

1. Missing `--execute` flag
2. Missing `auto_commits: true` 
3. Missing system prompts that FORCE action

The configs above fix all of this!

Just run with the flags or use the configs.