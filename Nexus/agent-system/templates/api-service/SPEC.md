# ENTERPRISE API SERVICE TEMPLATE
# Production-Ready REST/GraphQL API
# Scale: Millions of Requests

## TECH STACK
- Runtime: Node.js 22 + TypeScript 5
- Framework: Fastify / Express / NestJS
- Database: PostgreSQL 16 + Prisma/Drizzle
- Cache: Redis Cluster
- Queue: BullMQ + Redis
- Documentation: OpenAPI 3.0 / GraphQL
- Testing: Vitest + Supertest
- Container: Docker + Kubernetes

## ARCHITECTURE
```
src/
├── app.ts                    # Application entry
├── config/                   # Configuration
│   ├── database.ts          # DB connection
│   ├── redis.ts             # Redis client
│   └── auth.ts              # Auth config
├── routes/                   # API routes
│   ├── v1/
│   │   ├── users.ts
│   │   ├── products.ts
│   │   └── orders.ts
│   └── index.ts
├── controllers/              # Route handlers
├── services/                 # Business logic
│   ├── user.service.ts
│   ├── product.service.ts
│   └── order.service.ts
├── middleware/               # Express/Fastify middleware
│   ├── auth.ts
│   ├── validation.ts
│   ├── rateLimit.ts
│   └── errorHandler.ts
├── models/                   # Data models
│   ├── user.model.ts
│   └── types.ts
├── utils/                    # Utilities
│   ├── logger.ts
│   └── helpers.ts
├── workers/                  # Background jobs
│   └── email.worker.ts
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── scripts/
    ├── migrate.ts
    └── seed.ts
```

## KEY FEATURES
- Rate limiting (Redis-backed)
- Request validation (Zod)
- Response compression
- Caching strategy
- Background jobs
- WebSocket support
- OpenAPI documentation
- Health checks
- Graceful shutdown

## DEPLOYMENT
```bash
# Build
npm run build

# Run
NODE_ENV=production npm start

# Docker
docker build -t api-service .
docker-compose up -d
```