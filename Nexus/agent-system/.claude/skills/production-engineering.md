# WORLD-CLASS SKILL: Production-Ready Software Engineering

## Your Mission
Build software that scales to billions of users, handles millions of requests, and operates with 99.99% uptime. Not prototypes. Not MVPs. Production systems.

---

## PHASE 1: RESEARCH & DISCOVERY

### Before Writing Any Code:
1. **Understand the domain deeply**
   - Read existing documentation
   - Research industry best practices
   - Identify compliance requirements (GDPR, SOC2, HIPAA, PCI)
   - Analyze scaling requirements

2. **Analyze the codebase**
   - Understand existing architecture
   - Identify integration points
   - Map data flows
   - Document dependencies

3. **Technology selection**
   - Choose battle-tested technologies
   - Consider: community size, maintenance, performance, support
   - Avoid: cutting-edge untested, abandoned projects, niche tools

---

## PHASE 2: ARCHITECTURE & DESIGN

### Always Create SPEC.md First

The SPEC.md MUST contain:
1. **Executive Summary** - What we're building and why
2. **User Stories** - From user perspective
3. **Technical Architecture**
   - High-level diagram
   - Component design
   - Data model
   - API contracts
4. **Security Design**
   - Authentication flow
   - Authorization model
   - Data protection
5. **Scaling Strategy**
   - Horizontal vs vertical
   - Caching strategy
   - Database partitioning
6. **Monitoring Plan**
   - Key metrics
   - Alert thresholds
   - Runbooks

### Architecture Patterns
- **Clean Architecture** - Dependency inversion
- **Event-Driven** - Decoupled services
- **Microservices** - When needed, not as default
- **CQRS** - For complex domains
- **Event Sourcing** - When audit trail critical

---

## PHASE 3: IMPLEMENTATION

### Production Checklist

#### Code Quality
- [ ] TypeScript strict mode, NO `any`
- [ ] Error handling on EVERY function
- [ ] Input validation (Zod/Valibot)
- [ ] Proper logging (structured JSON)
- [ ] No console.log in production
- [ ] No TODO comments
- [ ] No placeholder code

#### Security (NON-NEGOTIBLE)
- [ ] Never hardcode secrets
- [ ] Use environment variables
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (React auto-escapes)
- [ ] CSRF protection
- [ ] Rate limiting
- [ ] Input sanitization
- [ ] Output encoding
- [ ] HTTPS everywhere
- [ ] Secure headers (Helmet)

#### Database
- [ ] Proper indexes for queries
- [ ] Migrations (not manual changes)
- [ ] Connection pooling
- [ ] Query optimization (EXPLAIN ANALYZE)
- [ ] Backup strategy
- [ ] Failover configuration

#### API Design
- [ ] RESTful or GraphQL (consistent)
- [ ] Proper HTTP status codes
- [ ] Consistent error response format
- [ ] Pagination on lists
- [ ] Versioning (/api/v1/)
- [ ] Rate limiting
- [ ] Request/response validation

#### Testing
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests
- [ ] E2E tests for critical paths
- [ ] Performance tests
- [ ] Security tests

---

## PHASE 4: VERIFICATION

### Before Declaring Complete:
1. **Run the application**
   - No crashes
   - No console errors
   - All routes work

2. **Test authentication flows**
   - Login/logout
   - Password reset
   - Session management

3. **Test data operations**
   - CRUD operations
   - Edge cases
   - Error handling

4. **Performance check**
   - Load time < 2s
   - API response < 200ms
   - No memory leaks

5. **Security check**
   - No exposed secrets
   - Input validation works
   - Auth enforced

---

## PHASE 5: DELIVERY

### What "Done" Means:
- [ ] `git clone && npm install && npm run dev` → working app
- [ ] README with setup instructions
- [ ] Environment configuration (.env.example)
- [ ] Database migrations run
- [ ] Tests passing
- [ ] No critical bugs
- [ ] Documentation updated

---

## KEY PRINCIPLES

### The 9 Laws of Production Software

1. **No Secrets in Code** - Everything in environment variables
2. **Fail Fast, Recover Gracefully** - Handle errors at every level
3. **Log Everything Useful** - Structured logs for debugging
4. **Validate All Input** - Trust nothing from user
5. **Cache Strategically** - Redis, CDN, browser
6. **Design for Scale** - 10x from day one
7. **Monitor Everything** - Metrics, logs, traces
8. **Automate Testing** - CI/CD pipeline
9. **Document Decisions** - ADRs for architecture

---

## OUTPUT STANDARD

When you build something, deliver:
1. Working code (runs without errors)
2. SPEC.md (architecture document)
3. README.md (setup instructions)
4. Tests (unit + integration)
5. Migration scripts (if DB changes)

If you can't deliver all five, you haven't finished.