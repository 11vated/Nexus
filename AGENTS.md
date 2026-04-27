# AGENTS.md - Agent Configuration for This Project

This file guides AI agents on how to work with this codebase.

## Project Overview

- **Project Name**: Ultimate AI Agent Workstation
- **Type**: Multi-agent development platform
- **Core Functionality**: Autonomous coding agents with production-grade capabilities
- **Target Users**: Developers seeking frontier-level AI assistance

---

## Architecture

```
agent-system/
├── core/                 # Agent core logic
├── templates/           # Project templates (enterprise-saas, api-service, frontend)
├── workspace/          # Working directory for projects
├── .claude/            # Claude/agent skills
│   └── skills/        # 1000+ production skills
└── venv_aider/        # Python environment with Aider
```

---

## Commands & Aliases

```bash
# Start Aider with production config
aider

# Start with specific model
aider --model ollama/qwen2.5-coder:14b

# Run tests
npm test && npm run test:coverage

# Build project
npm run build

# Docker commands
docker-compose up -d
docker-compose logs -f
```

---

## Environment

- **Node**: v22+
- **Python**: 3.12
- **Ollama**: Running on localhost:11434
- **Models Available**:
  - qwen2.5-coder:14b (code generation)
  - deepseek-r1:7b (reasoning/planning)
  - gemma4:26b (Google large)
  - codellama (Meta code specialist)

---

## Development Standards

### Code Style
- TypeScript strict mode
- ESLint + Prettier
- Conventional commits

### Testing
- Unit tests: Vitest
- E2E: Playwright
- Coverage: 80%+ required

### Security
- Never commit secrets
- Use environment variables
- Scan for vulnerabilities

---

## Agent Behavior

### Task Detection
When the user provides input, detect whether it's:
1. **Question** - Provide explanation, don't modify code
2. **Build Request** - Create files, implement features
3. **Debug Request** - Analyze, identify root cause, fix
4. **Planning** - Create SPEC.md, design architecture
5. **Review** - Analyze code, suggest improvements

### Workflow
1. Understand the request
2. Ask clarifying questions if needed
3. Execute the appropriate action
4. Verify the result
5. Summarize what was done

### Production Checklist
Before considering done:
- [ ] Code compiles without errors
- [ ] Tests pass
- [ ] No console.log in production
- [ ] Error handling in place
- [ ] README updated if needed

---

## Dependencies

Key packages and their purposes:
- `next` - React framework
- `prisma` - Database ORM
- `zod` - Validation
- `tanstack-query` - Server state
- `zustand` - Client state

---

## Testing Commands

```bash
# Unit tests
npm run test:unit

# Integration tests  
npm run test:integration

# E2E tests
npx playwright test

# Coverage
npm run test:coverage

# Lint
npm run lint

# Type check
npm run typecheck
```

---

## Deployment

```bash
# Docker
docker build -t app .
docker run -p 3000:3000 app

# Kubernetes
kubectl apply -f k8s/
```