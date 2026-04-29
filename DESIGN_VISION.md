# Nexus — Design Vision: What Makes It Different

## The Problem with Current AI Coding Tools

| Tool | Approach | Limitation |
|------|----------|------------|
| Copilot | Autocomplete | No agency — just suggestions |
| Cursor | IDE-integrated chat | Cloud-dependent, no local models |
| Aider | CLI git-aware chat | Single-model, no multi-model routing |
| Claude Code | Terminal agent | Cloud-only, expensive, no customization |

## Nexus's Unique Position: Local-First Intelligent Coding System

Nexus runs entirely on YOUR machine with YOUR models. That unlocks things
cloud tools literally cannot do:

### 1. Multi-Model Intelligence (ModelRouter)
Not just "pick a model" — Nexus automatically routes different PARTS of a
conversation to different specialized models:
- Planning/architecture → reasoning model (deepseek-r1)
- Code generation → coding model (qwen2.5-coder)  
- Quick edits/refactors → fast model (qwen2.5-coder:7b)
- Code review → review model (different temperature/system prompt)

The user sees ONE conversation. Under the hood, Nexus picks the best model
for each sub-task.

### 2. Conversation Stances (Personas)
Not just a chatbot — Nexus shifts its behavior based on context:
- **Architect** — high-level planning, asks probing questions
- **Pair Programmer** — writes code alongside you, explains choices
- **Debugger** — systematic hypothesis-testing, reads logs carefully
- **Reviewer** — critical eye, finds bugs, suggests improvements
- **Teacher** — explains concepts, walks through code

### 3. Project Intelligence (ProjectMap)
Before you even ask, Nexus understands your project:
- Dependency graph (what imports what)
- Test coverage map (what's tested, what's not)
- Hot files (most-changed, most-imported)
- Architecture detection (is this a FastAPI app? Django? CLI tool?)
- Auto-context: when you mention "the API", Nexus already knows which files

### 4. Session Continuity
Save and resume sessions. Nexus remembers:
- What you were building
- Decisions you made and why
- Files you care about
- Your preferred coding style

### 5. Adaptive Toolchain
Tools that compose and learn:
- **Watchers**: background processes that monitor file changes, test results
- **Workflows**: chain tools into reusable sequences
- **Hooks**: pre/post hooks on tool execution (auto-lint after file_write, etc.)

### 6. Conversation Branching
Like git, but for conversations:
- "Let's try approach A" → branch
- "Actually, let's explore approach B" → another branch
- Compare results, pick the best
