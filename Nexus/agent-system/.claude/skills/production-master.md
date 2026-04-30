# ================================================================================
# ULTIMATE SKILL: FULL-STACK PRODUCTION DEVELOPMENT
# ================================================================================
# This skill enables agents to build complete, production-ready applications
# from architecture to deployment - matching any frontier system
# ================================================================================

## 🎯 YOUR MISSION

Build world-class software that:
- Scales to millions of users
- Operates with 99.99% uptime
- Meets enterprise security standards
- Can be deployed with one command

---

## 📐 PHASE 1: ARCHITECTURE & DESIGN

### For ANY new project, ALWAYS create SPEC.md containing:

1. **Executive Summary**
   - What we're building
   - Target users
   - Success metrics

2. **Technical Architecture**
   - High-level diagram (describe in text)
   - Component design
   - Data model (complete schema)
   - API contracts (complete)

3. **Infrastructure**
   - Database selection & schema
   - Caching strategy
   - CDN configuration
   - Cloud services

4. **Security**
   - Authentication flow (detailed)
   - Authorization model (RBAC)
   - Encryption approach
   - Compliance (GDPR, SOC2, etc.)

5. **Scaling Plan**
   - Current capacity
   - Scaling triggers
   - Multi-region strategy

---

## 🔨 PHASE 2: IMPLEMENTATION

### Production Code Checklist:

- [ ] TypeScript (strict mode, NO any)
- [ ] Clean Architecture
- [ ] Error handling on EVERY function
- [ ] Input validation (Zod)
- [ ] Structured logging
- [ ] Environment config (.env)
- [ ] Database migrations
- [ ] Unit tests (>80%)
- [ ] Integration tests
- [ ] E2E tests for critical flows
- [ ] Security headers
- [ ] Rate limiting
- [ ] Cache strategy

### File Structure:
```
src/
├── app/           # App router pages / Express routes
├── components/    # UI components
├── lib/          # Utilities, API clients
├── services/     # Business logic
├── models/       # Data models
├── middleware/   # Express/Next middleware
├── hooks/       # React hooks
├── stores/      # State management
├── types/       # TypeScript types
├── styles/      # Global styles
└── tests/       # Test files
```

---

## ✅ PHASE 3: VERIFICATION

### Before declaring done, verify:

1. **Build**: `npm run build` → No errors
2. **Type check**: `npm run typecheck` → No errors  
3. **Lint**: `npm run lint` → No errors
4. **Tests**: `npm test` → All passing
5. **Run**: `npm run dev` → App works
6. **API**: All routes return correct responses
7. **Auth**: Login/logout works
8. **DB**: Migrations run, queries work

---

## 🚀 PHASE 4: DEPLOYMENT

### One-command deployment:
```bash
# Development
npm install && npm run dev

# Production  
docker build -t app . && docker run -p 3000:3000 app

# Kubernetes
kubectl apply -f k8s/
```

### CI/CD Pipeline:
- Security scan (Trivy, Bandit)
- Build
- Test (unit, integration, E2E)
- Security audit
- Deploy to staging
- Smoke tests
- Deploy to production

---

## 🛠️ TOOLS REFERENCE

### Database
- PostgreSQL - Primary database
- Redis - Caching, sessions
- Prisma/Drizzle - ORM

### API
- REST or GraphQL
- Proper HTTP status codes
- Validated inputs/outputs

### Testing
- Vitest - Unit tests
- Playwright - E2E tests
- Supertest - API tests

### Deployment
- Docker - Containerization
- GitHub Actions - CI/CD
- AWS/GCP/Azure - Cloud

---

## ⚡ QUICK REFERENCE

### Common Tasks:
- Create API route: Express/Fastify route with validation
- Create component: React component with TypeScript
- Database model: Prisma schema with relations
- Auth flow: JWT with refresh tokens
- Test: Vitest test file with coverage

### When Stuck:
1. Check SPEC.md first
2. Search documentation
3. Ask for clarification
4. Use simpler approach if unsure

---

## 🎓 THE GOLDEN RULE

**When you finish: User runs ONE command → has WORKING production app.**

Not "should work", not "might work" - WORKS.

If it's not production-ready, you haven't finished.