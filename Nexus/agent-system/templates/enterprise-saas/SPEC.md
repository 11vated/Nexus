# ENTERPRISE SAAS TEMPLATE
# Production-Ready Full-Stack Application
# Architecture: Multi-Trillion Dollar Standard

## TECH STACK
- Frontend: Next.js 15 + React 19 + TypeScript 5
- Styling: Tailwind CSS 4 + shadcn/ui
- Backend: Next.js API Routes / Server Actions
- Database: PostgreSQL 16 + Prisma ORM
- Auth: NextAuth.js v5 (Auth.js)
- State: TanStack Query + Zustand
- Validation: Zod + Valibot
- Testing: Vitest + Playwright
- CI/CD: GitHub Actions
- Cloud: Docker + Kubernetes ready

## PROJECT STRUCTURE
```
├── apps/
│   ├── web/                 # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/         # App Router pages
│   │   │   ├── components/  # React components
│   │   │   ├── lib/         # Utilities
│   │   │   ├── hooks/       # Custom hooks
│   │   │   ├── types/       # TypeScript types
│   │   │   └── styles/      # Global styles
│   │   ├── public/          # Static assets
│   │   └── tests/           # E2E tests
│   └── api/                 # API service (if separate)
│       ├── src/
│       │   ├── routes/      # API endpoints
│       │   ├── services/    # Business logic
│       │   ├── middleware/  # Express/Next middleware
│       │   └── utils/       # Utilities
│       └── tests/
├── packages/
│   ├── ui/                  # Shared UI components
│   ├── config/              # Shared config
│   ├── database/            # Prisma schema & client
│   ├── utils/               # Shared utilities
│   └── types/               # Shared TypeScript types
├── services/                # Backend services
│   ├── auth/               # Authentication service
│   ├── users/              # User management
│   ├── payments/           # Payment processing
│   └── notifications/      # Notification service
├── k8s/                     # Kubernetes manifests
├── docker/                  # Dockerfiles
├── .github/
│   └── workflows/          # GitHub Actions
├── scripts/                 # Dev scripts
├── docs/                    # Documentation
├── SPEC.md                  # System specification
└── README.md                # Setup instructions
```

## DATABASE SCHEMA
```prisma
// Users & Auth
model User {
  id            String    @id @default(cuid())
  email         String    @unique
  name          String?
  password      String    // Hashed
  role          Role      @default(USER)
  emailVerified DateTime?
  image         String?
  accounts      Account[]
  sessions      Session[]
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
}

enum Role {
  USER
  ADMIN
  MODERATOR
}

// Multi-tenancy
model Organization {
  id          String   @id @default(cuid())
  name        String
  slug        String   @unique
  logo        String?
  ownerId     String
  owner       User     @relation(fields: [ownerId], references: [id])
  members     OrganizationMember[]
  invitations OrganizationInvitation[]
  settings    Json?
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
}

// Subscriptions
model Subscription {
  id               String   @id @default(cuid())
  organizationId   String
  organization     Organization @relation(fields: [organizationId], references: [id])
  plan             Plan
  status           SubscriptionStatus
  currentPeriodEnd DateTime
  cancelAtPeriodEnd Boolean @default(false)
  createdAt        DateTime @default(now())
  updatedAt        DateTime @updatedAt
}

// Audit Logging
model AuditLog {
  id           String   @id @default(cuid())
  organizationId String
  userId       String
  action       String
  resource     String
  resourceId   String?
  metadata     Json?
  ipAddress    String?
  userAgent    String?
  createdAt    DateTime @default(now())
}
```

## AUTHENTICATION
- JWT + Refresh Tokens
- OAuth (Google, GitHub, etc.)
- Magic Links
- 2FA/TOTP support
- Session management
- Role-based access control (RBAC)

## API STRUCTURE
```typescript
// RESTful API with proper error handling
// Base: /api/v1

// Users
GET    /api/v1/users          # List users (admin)
GET    /api/v1/users/:id      # Get user
POST   /api/v1/users          # Create user
PATCH  /api/v1/users/:id      # Update user
DELETE /api/v1/users/:id      # Delete user

// Organizations
GET    /api/v1/orgs           # List orgs
POST   /api/v1/orgs           # Create org

// Resources (with RBAC)
GET    /api/v1/resources      # List (with pagination, filters)
POST   /api/v1/resources      # Create
GET    /api/v1/resources/:id  # Get single
PATCH  /api/v1/resources/:id  # Update
DELETE /api/v1/resources/:id  # Delete

// Error Response Format
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [...],
    "requestId": "req_xxx"
  }
}
```

## SECURITY CHECKLIST
- [ ] Input validation (Zod schema)
- [ ] SQL injection prevention (Prisma parameterized)
- [ ] XSS prevention (React auto-escaping, DOMPurify)
- [ ] CSRF protection
- [ ] Rate limiting
- [ ] CORS configured
- [ ] Security headers (Helmet)
- [ ] Secrets management (.env, not in code)
- [ ] Audit logging
- [ ] Encryption at rest
- [ ] HTTPS only

## DEPLOYMENT
```bash
# Development
npm install
npx prisma generate
npm run db:push
npm run dev

# Production
npm run build
npm run start

# Docker
docker build -t myapp .
docker run -p 3000:3000 myapp

# Kubernetes (see k8s/ directory)
kubectl apply -f k8s/
```

## MONITORING & OBSERVABILITY
- Error tracking (Sentry)
- Analytics (PostHog)
- Logging (structured JSON logs)
- Metrics (Prometheus)
- Tracing (OpenTelemetry)

## TESTING STRATEGY
- Unit tests (Vitest)
- Integration tests (Vitest + test DB)
- E2E tests (Playwright)
- Contract tests (Pact)
- Performance tests (k6)

## DOCUMENTATION
- API Reference (OpenAPI/Swagger)
- Component Library (Storybook)
- Architecture Decision Records (ADR)
- Runbooks for operations