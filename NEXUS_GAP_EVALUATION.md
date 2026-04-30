# NEXUS — Exhaustive Gap Evaluation

**Date:** 2026-04-30
**Codebase:** 22,951 lines source / 10,096 lines tests / 1,034 tests passing
**Reference Documents:** v1 Cognitive Partnership Manifesto, v2 Research Vision, v3 Claude Gap Analysis, v4 Overlooked Gaps

---

## Methodology

Every module in `src/nexus/` evaluated against every requirement from all 4 vision documents.
Gaps scored: ✅ Exists & Production-Quality | 🟡 Exists but Shallow | 🔴 Missing Entirely

---

## LAYER 1: AGENT FOUNDATION

### 1.1 Core Agent Loop

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| AgentLoop (autonomous) | 🟡 | 338 lines. Plan→Act→Observe→Reflect. Works. | Linear pipeline only. No async event-driven runtime. No backpressure management. No streaming sampling. |
| ChatSession (collaborative) | 🟡 | 1,705 lines. Streaming, tool dispatch, history, cognitive hooks. | No context compression when history grows. No automatic summarization of past turns. Hits context wall at ~15-20 turns. |
| CognitiveLoop (8-state) | 🟡 | 619 lines. IDLE→UNDERSTAND→PROPOSE→DISCUSS→REFINE→EXECUTE→REVIEW→PAUSED. Meta-reflection at UNDERSTAND and EXECUTE transitions. | Meta-reflection is string templates, not actual LLM self-critique. It generates text like "What assumptions am I making?" but never actually answers the question. Placeholder, not real meta-cognition. |
| LLM Client | 🟡 | 312 lines. Ollama HTTP client, sync+async, streaming, JSON extraction. | No structured output enforcement. No response validation. No retry with temperature escalation. |
| Planner | 🟡 | 272 lines. Create plan, get next step, decompose tasks. | Plans once, replans reactively. No continuous re-planning from updated belief state. No dynamic environment model. |
| Reflector | 🟡 | 240 lines. LLM-based reflection on step outcomes + heuristic fallback. | Reflects on "did the test pass?" not "why did I think that approach would work?" No IRSC dual-loop. No reasoning self-critique. |
| Executor | 🟡 | 124 lines. Simple tool dispatch, subprocess execution. | No parallel execution. No timeout budgets. No cancellation. |

**Layer 1 Gaps Summary:**

1. **🔴 Multi-Agent Coordination** — ZERO infrastructure. No AgentBus, no parallel sub-agents, no task decomposition into parallel waves, no result merging, no conflict detection between agent outputs. This is the single largest architectural gap. The v3 doc identifies Claude's multi-agent as: orchestrator plans → launches parallel sub-agents → each executes independently → orchestrator verifies. We have nothing.

2. **🔴 Specialized Agent Roles** — ZERO. No architect/developer/tester/reviewer specialization. No role-specific prompts, role-specific memory, role-specific tools. Every task runs through one monolithic ChatSession.

3. **🔴 Hierarchical Agent Lifecycle** — No parent-child agent management, no cancellation propagation, no resource cleanup when a sub-agent fails.

4. **🔴 Real Meta-Cognition (IRSC)** — CognitiveLoop has `meta_reflection` flag but it just generates static prompt text. It never actually has the LLM reflect on its own reasoning process. True IRSC requires: outer loop (execution) + inner loop (reflect on reflection). We have one loop.

5. **🔴 Dynamic Environment Model** — Planner treats codebase as static target. After each tool execution, the environment changes (new files, test results, errors) but the plan doesn't update its belief state. It replans reactively when steps fail, not proactively from observed changes.

6. **🟡 Event-Driven Runtime** — ChatSession uses async generators (good) but the tool execution is sequential within a turn. No concurrent tool execution, no event bus for real-time state propagation.

---

## LAYER 2: TOOL EXECUTION & PERMISSIONS

### 2.1 Tools

| Tool | Status | Lines | What's Missing |
|------|--------|-------|----------------|
| shell | 🟡 | 117 | No timeout enforcement, no output truncation |
| file_read | ✅ | 174 | OK for basic use |
| file_write | 🟡 | 174 | No backup before write, no atomic write |
| code_runner | 🟡 | 159 | No sandbox isolation for arbitrary code |
| test_runner | 🟡 | 132 | No parallel test execution, no coverage |
| search | 🟡 | 159 | grep-based only, no semantic search |
| git | 🟡 | 97 | Basic operations only, no rebase/cherry-pick |
| registry | ✅ | 106 | Tool registration works |

**8 tools total. Claude Code has 20+ including web search, MCP connectors, code analysis.**

### 2.2 Permission System

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| PermissionManager | 🟡 | 428 lines. Allow/Ask/Deny rules, pattern matching, audit logging. | Static rules only. No ML-based classification. No context-aware safety prediction. No learning from past permission decisions. |
| Permission modes | 🟡 | 3 modes (allow/ask/deny) | Claude has 7 modes with dynamic risk assessment |
| Audit trail | ✅ | Logs permission decisions | OK |

### 2.3 Tool Execution Pipeline

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| `_execute_tool()` | 🔴 Shallow | 20 lines. Try/except wrapper. Fuzzy name matching. | **No fallback chains.** If search fails, it just returns an error. No retry with alt params. No graceful degradation to simpler tools. |
| Result validation | 🔴 | None | No schema validation on tool outputs. Malformed JSON from tools passes straight to LLM. |
| Timeout handling | 🔴 | None | No per-tool timeout. Shell commands can hang forever. |
| Retry budgets | 🔴 | None | No "try 3 times with different params" logic. |
| Tool composition | 🔴 | None | No ability to chain tools (search → read → analyze). Each tool call is a separate LLM turn. |

**Layer 2 Gaps Summary:**

1. **🔴 Tool Fallback Chains** — Single-shot execution. When a tool fails, the error goes back to the LLM which might retry, but there's no orchestrated fallback (search→grep→manual scan, or file_read→shell cat→error message).

2. **🔴 ML-Based Permission Classification** — Permissions are static pattern matching. No model that predicts "this shell command is risky because it modifies system files" based on context.

3. **🔴 Tool Result Validation** — No enforcement that tool outputs are well-formed before passing to LLM. This matters because local models are more brittle with malformed input.

4. **🔴 Concurrent Tool Execution** — Tools execute sequentially. If the LLM requests 3 file_reads, they happen one at a time. Could parallelize independent tool calls.

---

## LAYER 3: CONTEXT & MEMORY

### 3.1 Context Management

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| ContextManager | 🔴 Shallow | 157 lines. Priority queue with character budget. Entries added/pinned, sorted by priority, truncated to budget. | **THE critical gap.** No compression. No summarization. No semantic importance scoring. No selective pruning. No residual context. When the budget is exceeded, lower-priority entries are simply dropped. |
| Chat history | 🔴 | Raw `self.history: List[Dict]` in ChatSession. Grows unbounded. | No history compression. No sliding window. No "summarize turns 1-20 into a paragraph." After ~15 turns with tool use, the context window overflows and the LLM loses coherence. |
| Claude's 5-layer pipeline | 🔴 | Not implemented | Need: (1) Detect overrun → (2) Selective prune (remove low-importance) → (3) Semantic summarize (LLM-compress segments) → (4) Preserve tool results/diffs → (5) Residual context (compressed state the model can continue from) |

### 3.2 Memory Systems

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| Short-term memory | 🟡 | 124 lines. Deque-based, recent entries. | In-memory only. Dies on restart. No importance scoring. |
| Long-term memory | 🟡 | 218 lines. Key-value store with categories. | In-memory only. No disk persistence in practice (has init but no auto-save). No semantic retrieval. |
| KnowledgeStore | 🟡 | 448 lines. 5-layer stratified (Syntax→Flow→Patterns→Domain→Intent). Membrane rules control cross-layer flow. | **Text matching only.** No embedding-based semantic search. No knowledge graph relationships. Entries are flat text, not structured nodes with edges. |
| MemoryMesh | 🟡 | 405 lines. Multi-bank (private/shared/project scope), lineage tracking, tagging, importance scoring. | **In-memory only.** `to_dict()`/`from_dict()` exist but nothing calls save/load to disk automatically. Cross-session memory is conceptual, not real. |
| ContextRetriever (SWE-bench) | 🟡 | 250 lines. ChromaDB vector index for codebase files. Fallback to grep. | Only used in SWE-bench pipeline, NOT wired into ChatSession. The main chat experience has zero vector/semantic retrieval. |
| FeedbackSystem | 🟡 | 701 lines. UserProfile → `.nexus/profile.yaml`, PreferenceLearner, code style detection, asymptotic confidence. | **Does persist to disk** (the one module that does). But preferences are pattern-based, not embedding-based. No contradiction resolution beyond confidence decay. |

### 3.3 Knowledge Graph

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| ProjectMap | 🟡 | 576 lines. AST-based file scanning, import graph (dict of sets), class/function extraction. | **Flat import graph, not a knowledge graph.** Edges are only "file A imports file B." No call graph (which functions call which), no inheritance graph (which classes extend which), no data flow. Can answer "what does this file import?" but NOT "what functions call function X?" |
| Knowledge graph layer | 🔴 | Not implemented | Need: networkx or similar graph where nodes = files/functions/classes/variables, edges = calls/inherits/contains/imports. Hybrid retrieval: vector similarity + graph traversal. This enables "find all callers of X that are called by Y." |
| Cross-file relationship awareness | 🔴 | Import graph only | No understanding of: which functions modify shared state, which classes implement an interface, which tests cover which functions. The LLM discovers these by reading files, not from a pre-built graph. |

### 3.4 Design Verification

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| DesignVerifier | 🟡 | 449 lines. 8 built-in constraints (no-print, no-star-import, no-bare-except, no-hardcoded-secrets, module-docstring, max-function-length, no-todo-fixme, no-mutable-default). Pattern + predicate matching. | **Regex-based only.** Cannot check semantic constraints like "this module should not depend on that module" or "error handling should use the project's custom exception hierarchy." No LLM-based second-pass verification. No constraint extraction from existing code. |
| Constraint categories | 🟡 | PATTERN, SECURITY, DEPENDENCY, DOCUMENTATION, COMPLEXITY | Missing: ARCHITECTURE (module boundaries), PERFORMANCE (algorithmic complexity), TESTING (coverage requirements) |
| Verification in pipeline | 🟡 | Wired into CognitiveLayer.before_tool_call() for file_write operations | Only checks individual files, not cross-file design rules |

### 3.5 Underspecification Handling

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| AmbiguityDetector | 🟡 | 332 lines. 10-type taxonomy (SCOPE, PRIORITY, CONSTRAINT, CONTEXT, PERFORMANCE, SECURITY, COMPATIBILITY, EDGE_CASE, NAMING, ARCHITECTURE). Pattern-based + heuristic detection. | **Pattern matching, not LLM-based.** Checks for keywords like "fast", "good", "nice" as ambiguity signals. Cannot detect subtle underspecification like "implement auth" (which auth? OAuth? JWT? Session?). |
| ClarificationDialog | 🟡 | Part of clarification.py. Generates questions from signals. | Questions are template-based, not context-aware. The dialog doesn't update the task plan based on answers. |
| Integration | 🟡 | Wired into CognitiveLayer.analyze_message() | Detects ambiguity but doesn't block execution. The signal is logged as an event, not surfaced to the user as a mandatory clarification step. |

### 3.6 Memory Persistence (Cross-Session)

| Component | Status | What's Missing |
|-----------|--------|----------------|
| Session save/restore | 🔴 | SessionStore (241 lines) saves snapshots but MemoryMesh/KnowledgeStore are not auto-persisted across sessions |
| Profile persistence | ✅ | FeedbackSystem persists UserProfile to `.nexus/profile.yaml` |
| Knowledge persistence | 🔴 | KnowledgeStore has `to_dict()` but no auto-save. Knowledge learned during a session is lost on exit. |
| Memory persistence | 🔴 | MemoryMesh has `to_dict()` but no auto-save. All episodic/procedural memories lost on exit. |
| Conversation archive | 🔴 | History is in-memory list. No automatic archival of past conversations for future reference. |

---

## LAYER 4: UI & COLLABORATION

### 4.1 Terminal Interface

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| Textual TUI | 🟡 | 1,308 lines. NexusApp with header, chat stream, 5-tab sidebar, input area, status bar. StreamingMessage, PlanCard, CognitiveIndicator, HelpScreen. 20+ slash commands, keyboard shortcuts. | **No progressive disclosure.** All information shown at full detail always. No "show summary first, expand on demand." No attention-guided highlighting. No memory compression of past turns into summaries. |
| Rich Chat UI | 🟡 | 896 lines. Classic terminal chat with slash commands. | Simpler alternative, lacks sidebar and visual structure. |
| Dashboard | 🟡 | 299 lines. Agent monitoring. | Basic status display only. |
| Diff Engine | ✅ | 553 lines. Generate, apply, undo diffs. Hunk-level accept/reject. | Functional. |
| Diff Renderer | ✅ | 325 lines. Side-by-side, unified, inline rendering. | Functional. |
| EditorProtocol | 🟡 | 295 lines. VSCode/Vim/Emacs integration hooks. | Hooks defined but no actual editor plugins built. |

### 4.2 Interaction Metaphor

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| Command model | 🔴 | Slash commands: /help, /clear, /tools, /plan, /stance, /project, /route, /stats, /cognitive, /trace, /knowledge, /memory, /learn | **Supervisor-employee pattern.** User gives commands, AI executes. Missing: /discuss, /suggest, /question, /alternative, /whatif. The AI never initiates dialogue. It never says "What do you think about X?" or "I have concerns about Y." |
| AI-initiated clarification | 🔴 | AmbiguityDetector detects but doesn't interrupt | AI should proactively ask questions when it detects ambiguity, not just log it. In GUIDED mode it asks one question at UNDERSTAND phase, but in PASSIVE (default) mode, it stays silent. |
| Shared common ground | 🔴 | Plan is visible in sidebar, but not editable by user | User can see the plan but can't drag-reorder steps, edit step descriptions, mark steps as "don't do this," or add new steps. It's a display, not a collaboration surface. |
| Joint cognitive system | 🔴 | Not implemented | The fundamental metaphor shift from "approve this action" to "what do you think about this approach" requires redesigning how conversations flow. AI should present alternatives, explain tradeoffs, and wait for discussion before executing. |

### 4.3 Progressive Disclosure

| Component | Status | What's Missing |
|-----------|--------|----------------|
| Detail levels | 🔴 | No concept of summary/detail/full views |
| Past turn compression | 🔴 | Old messages displayed in full, never compressed to summaries |
| Attention guidance | 🔴 | No highlighting of what changed vs. what stayed the same |
| Explainable defaults | 🔴 | AI makes decisions without showing reasoning unless explicitly asked |

### 4.4 Live Collaboration

| Component | Status | What's Missing |
|-----------|--------|----------------|
| Multi-user sessions | 🔴 | Single-user only. No session sharing. |
| WebSocket server | 🔴 | No real-time communication layer |
| Conflict resolution | 🔴 | No CRDT, no conflict handling between simultaneous edits |
| Role-based access | 🔴 | No read-only vs. write access for session participants |

---

## LAYER 5: AGENT NETWORK

### 5.1 Model Federation (Advisor Pattern)

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| ModelRouter | 🟡 | 324 lines. Routes by task intent (coding/architecture/debugging/quick). Picks single best model from profiles. | **NOT the Advisor pattern.** Router picks ONE model per request. No cheap-executor + expensive-advisor tandem. No cost tracking. No "ask the 14B model only for hard decisions." |
| Model profiles | 🟡 | Predefined profiles with strengths, speed tier, reasoning depth. | Static profiles. No learning from past routing decisions. No A/B testing of model performance. |
| Cost management | 🔴 | None | No VRAM budgeting, no compute cost tracking, no "this task isn't worth the expensive model" logic |

### 5.2 Extensibility

| Component | Status | What Exists | What's Missing |
|-----------|--------|-------------|----------------|
| HookEngine | 🟡 | 475 lines. Pre/post hooks for tool calls, messages, sessions. Plugin YAML config loading. | Hooks run in-process. No sandboxing. No API versioning. No dependency management. |
| PluginConfigLoader | 🟡 | 422 lines. YAML-based plugin config (tools, hooks, rules). | Config loading only. No plugin discovery, no scaffolding, no validation, no marketplace. |
| MCP Server | 🟡 | 282 lines. Protocol skeleton for external tool integration. | Skeleton only. Not connected to any real MCP clients. |
| BaseTool abstraction | 🟡 | Tool registry with `execute()` interface. | No BaseAgent or BaseMemory abstract classes. No plugin template generator. |

### 5.3 Distributed Agent Network

| Component | Status | What's Missing |
|-----------|--------|----------------|
| Agent discovery | 🔴 | No registry, no announcement protocol, no capability advertising |
| Task negotiation | 🔴 | No auction, no bidding, no capability matching |
| Trust mechanisms | 🔴 | No output verification between agents, no reputation scoring |
| Communication protocol | 🔴 | No message format standard, no agent-to-agent API |
| Agent marketplace | 🔴 | No registry, no publishing, no discovery |

---

## CROSS-CUTTING GAPS (from v4 research)

### Co-Design via Collaborative Multi-Agent

| Requirement | Status | What's Missing |
|-------------|--------|----------------|
| Parallel exploration | 🔴 | Agents don't explore solutions simultaneously |
| Structured negotiation | 🔴 | No debate/comparison mechanism between agents |
| Consensus mechanism | 🔴 | No voting, no weighted agreement, no conflict resolution |
| Divergent expertise | 🔴 | No role specialization means no diverse perspectives |

### Knowledge Graph (Structural Code Awareness)

| Requirement | Status | What Exists | What's Missing |
|-------------|--------|-------------|----------------|
| File nodes | 🟡 | ProjectMap has FileInfo | Basic info only |
| Function/class nodes | 🟡 | ProjectMap extracts names via AST | Names only, no call relationships |
| Call graph edges | 🔴 | Not implemented | Need AST-based analysis of function calls |
| Inheritance edges | 🔴 | Not implemented | Need AST-based class hierarchy |
| Data flow edges | 🔴 | Not implemented | Need variable assignment/usage tracking |
| Hybrid retrieval | 🔴 | Not implemented | Need vector similarity + graph traversal |

### Cognitive Load Reduction

| Requirement | Status | What's Missing |
|-------------|--------|----------------|
| Progressive disclosure | 🔴 | TUI shows everything at full detail always |
| Memory compression in UI | 🔴 | Past messages never compressed to summaries |
| Attention-guided visualization | 🔴 | No diff highlighting relative to context |
| Explainable defaults | 🔴 | AI decisions not explained unless asked |

### Dynamic Environment Model

| Requirement | Status | What's Missing |
|-------------|--------|----------------|
| Belief state about codebase | 🔴 | No explicit "what I believe about the project right now" state |
| Belief update after each action | 🔴 | ProjectMap can rescan but doesn't auto-update |
| Prediction of future states | 🔴 | No "if I change X, Y will break" reasoning |
| Continuous re-planning | 🔴 | Plans are created once, updated only on failure |

### IRSC (Iterative Reasoning with Self-Critique)

| Requirement | Status | What Exists | What's Missing |
|-------------|--------|-------------|----------------|
| Outer loop (execution) | ✅ | AgentLoop Plan→Act→Observe→Reflect | Works |
| Inner loop (meta-cognition) | 🔴 | CognitiveLoop has `meta_reflection` flag | Generates template strings, never actually has the LLM critique its own reasoning. Need: "Why did I choose that approach? What assumptions proved wrong? How should my decision process change?" — answered by the LLM, not templated. |
| Learning from meta-reflection | 🔴 | Not implemented | No mechanism to update future behavior based on meta-cognitive insights |

### Interaction Metaphor (Partner vs. Tool)

| Requirement | Status | What's Missing |
|-------------|--------|----------------|
| AI initiates dialogue | 🔴 | AI only responds, never proactively asks |
| Shared reasoning visibility | 🟡 | Trace sidebar shows reasoning nodes | But it's a log display, not an interactive discussion |
| Editable plans | 🔴 | PlanCard is display-only | User can't drag, reorder, edit, or reject individual steps in the UI |
| Strategic oversight mode | 🔴 | User is tactical approver | No "set the direction, AI handles the details" mode |
| /discuss, /suggest, /whatif | 🔴 | Not implemented | Missing collaborative commands |

---

## SEVERITY-RANKED GAP LIST

### Tier 1: Without these, the system can't function beyond a demo

1. **Context Compaction Pipeline** — After ~15 turns, LLM loses coherence. Blocks ALL extended use.
2. **Memory Persistence** — Knowledge/memories lost on restart. Every session starts from zero.
3. **Tool Fallback + Timeout** — Single-shot tools with no error recovery. Production unusable.

### Tier 2: Without these, the system can't differentiate from existing tools

4. **Advisor Model Federation** — Burning expensive model time on simple tasks. Can't be cost-effective.
5. **Multi-Agent Coordination** — Serial execution for all tasks. Can't parallelize.
6. **Knowledge Graph** — Can't reason about code structure. Can only find "similar text."
7. **Real Meta-Cognition** — Reflects on outcomes, not on reasoning. Can't improve its decision process.

### Tier 3: Without these, the system can't fulfill the "cognitive partnership" vision

8. **AI-Initiated Dialogue** — AI never proactively asks, suggests, or challenges.
9. **Progressive Disclosure** — Information overload in TUI. Not designed for human cognition.
10. **Dynamic Environment Model** — Plans don't adapt to changing codebase state.
11. **Interaction Metaphor Redesign** — Commands instead of conversation.
12. **Co-Design with Parallel Exploration** — No diverse solution exploration.

### Tier 4: Future vision

13. **Live Multi-User Collaboration** — WebSocket, CRDT, session sharing.
14. **Plugin SDK + Marketplace** — Sandboxed plugins, discovery, API versioning.
15. **Distributed Agent Network** — Agent discovery, negotiation, trust.

---

## TOTAL SCORECARD

| Category | Modules Built | Depth Rating | Notes |
|----------|--------------|--------------|-------|
| Agent loop (single) | 6 | 🟡 50% | Works but shallow |
| Multi-agent | 0 | 🔴 0% | Nothing exists |
| Tools | 8 | 🟡 45% | Basic, no fallbacks |
| Permissions | 1 | 🟡 40% | Static rules only |
| Context management | 1 | 🔴 15% | Priority queue, no compression |
| Memory (session) | 4 | 🟡 35% | Structures exist, no persistence |
| Knowledge | 2 | 🟡 30% | Text-based, no graph |
| Verification | 1 | 🟡 35% | Regex patterns, no semantic |
| Clarification | 1 | 🟡 30% | Pattern-based, not LLM-based |
| Feedback | 1 | 🟡 55% | Best cognitive module, persists |
| TUI | 3 | 🟡 50% | Good structure, no progressive disclosure |
| Diff system | 2 | ✅ 75% | Most complete subsystem |
| Intelligence | 5 | 🟡 40% | Routing/stances work, no advisor |
| Cognitive integration | 1 | 🟡 45% | Wiring works, modules shallow |
| Agent network | 0 | 🔴 5% | MCP skeleton only |

**Overall weighted estimate: ~30-35% of Claude-level capability**

The foundation is clean and testable. The architecture is sound. But most modules are "API surface" — they define the right interfaces and data structures without the deep implementations that make them actually work with real LLM outputs on real codebases.
