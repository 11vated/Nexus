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

---

## 7. Cognitive Partnership Architecture

This is Nexus's deepest differentiator. While other tools treat AI as either
a tool (autocomplete) or an autonomous agent (fire-and-forget), Nexus implements
a **cognitive partnership** model — AI as a thinking partner who reasons
transparently, remembers context, and never acts without awareness.

### The Cognitive Loop State Machine

Replaces the linear Plan → Act → Observe → Reflect loop with a human-centered cycle:

```
IDLE → UNDERSTAND → PROPOSE → DISCUSS → REFINE → EXECUTE → REVIEW
  ↑                                                          │
  └──────────────────────────────────────────────────────────┘
```

Key properties:
- **UNDERSTAND**: Parse the goal, detect ambiguity, search knowledge/memory
- **PROPOSE**: Generate a plan with explicit dependencies and risk levels
- **DISCUSS**: Human reviews plan, asks questions, adjusts
- **REFINE**: Update plan based on feedback before any code touches disk
- **EXECUTE**: Run approved steps one at a time with verification
- **REVIEW**: Reflect on what worked, update memory, ask for feedback

The AI never advances without human awareness. In GUIDED mode, every state
transition is visible. In PASSIVE mode, the cognitive features run silently
in the background, enriching responses without enforcing the cycle.

### Stratified Knowledge Architecture (5 Layers)

Inspired by ALMA research — knowledge isn't flat, it has structure:

```
┌─────────────────────────┐
│   INTENT (why)          │  "The user wants X because Y"
├─────────────────────────┤
│   DOMAIN (what)         │  "This project uses OAuth2 + JWT"
├─────────────────────────┤
│   PATTERNS (how)        │  "Factory pattern for DB connections"
├─────────────────────────┤
│   FLOW (structure)      │  "Module A imports from Module B"
├─────────────────────────┤
│   SYNTAX (tokens)       │  "Variable naming: snake_case"
└─────────────────────────┘
```

Each layer has **membrane rules** controlling what knowledge flows between layers.
Knowledge auto-accumulates from file reads, tool calls, and explicit teaching.

### Reasoning Trace DAG

Every decision Nexus makes is recorded as a node in a directed acyclic graph:

- **Observation** — "User said X", "File contains Y"
- **Hypothesis** — "I think the bug is in Z" (with confidence)
- **Decision** — "I'll refactor using pattern P"
- **Alternative** — "Could also do Q, but chose P because..."
- **Action** — "Calling tool T with args..."
- **Outcome** — "Tool succeeded/failed"
- **Correction** — "User corrected my approach"
- **Checkpoint** — Named milestone in the reasoning

The trace is searchable, serializable, and visible to the user via `/trace`.
This means you can always ask "why did you do that?" and get a real answer.

### Design-Aware Verification

Every file write is checked against design constraints before hitting disk:

- No star imports (`from x import *`)
- No hardcoded secrets
- Functions under complexity limits
- Custom project-specific constraints

Violations produce warnings (not blocks) so the user stays in control.

### Ambiguity Detection

When a user message is underspecified, Nexus detects it:

- Vague scope ("fix the API" — which part?)
- Implicit assumptions ("make it faster" — what metric?)
- Missing constraints ("add auth" — OAuth? JWT? Basic?)
- Contradictions with prior context

In PASSIVE mode, ambiguity signals enrich the system prompt so the LLM asks
better clarifying questions. In GUIDED mode, a clarification dialog is
presented before work begins.

### Multi-Memory Architecture (MemoryMesh)

Not one memory — a mesh of memory banks with lineage tracking:

- **Episodic** — what happened (conversation turns, tool calls)
- **Semantic** — what things mean (project facts, user preferences)
- **Procedural** — how to do things (successful patterns, failed approaches)
- **Working** — current context (active plan, recent decisions)
- **Preference** — learned preferences (style, tools, workflow choices)

Each memory has an importance score and decay rate. Memories consolidate
over time — repeated patterns become procedural knowledge.

### Cognitive Modes

```
OFF        → Pure chat, no cognitive overhead
PASSIVE    → Silent enrichment — ambiguity detection, knowledge lookup, trace
GUIDED     → Full loop — plan review, approval gates, structured collaboration
AUTONOMOUS → Loop + auto-approve (for CI/testing, not recommended for dev)
```

### Slash Commands

```
/cognitive [mode]  — Show or set cognitive mode
/trace             — Show reasoning trace
/knowledge         — Show knowledge store summary
/memory            — Show memory mesh summary
/learn <text>      — Teach Nexus something explicitly
/remember <text>   — Store a memory explicitly
```

### Integration Architecture

The cognitive layer hooks into ChatSession at four points:

1. **Message analysis** (`analyze_message`) — Before the LLM sees the message.
   Detects ambiguity, searches knowledge/memory, updates trace, sets goals.

2. **System prompt augmentation** (`get_context_augmentation`) — Injects
   cognitive state, relevant knowledge, and memories into the system prompt.

3. **Tool call interception** (`before_tool_call` / `after_tool_call`) —
   Verifies file writes against constraints. Records tool results. Learns
   from file reads. Stores procedural memories.

4. **Response analysis** (`analyze_response`) — Traces AI reasoning.
   Stores episodic memories. Updates the cognitive loop state.

All four hooks produce `CognitiveEvent` objects that ChatSession translates
into `ChatEvent`s for the TUI to display.

---

## Architecture Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                         ChatSession                              │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Intelligence  │  │  Interactive  │  │     Cognitive         │  │
│  │               │  │               │  │                       │  │
│  │ ModelRouter   │  │ DiffEngine    │  │ CognitiveLoop         │  │
│  │ StanceManager │  │ DiffRenderer  │  │ SharedState            │  │
│  │ ProjectMap    │  │ ConvTree      │  │ ReasoningTrace         │  │
│  │ SessionStore  │  │ Permissions   │  │ KnowledgeStore         │  │
│  │               │  │ HookEngine    │  │ DesignVerifier         │  │
│  │               │  │ WatcherEngine │  │ AmbiguityDetector      │  │
│  │               │  │               │  │ MemoryMesh             │  │
│  │               │  │               │  │ CognitiveLayer (glue)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Tool System                             │   │
│  │  shell · file_read · file_write · file_list               │   │
│  │  code_run · test_run · search · git                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Config System                           │   │
│  │  .nexus/config.yaml · .nexus/rules.md · .nexus/hooks/     │   │
│  │  PluginConfigLoader · ProjectConfig                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

**Total: 20+ integrated modules, 963 tests, 0 failures.**
