# MODERN FRONTEND TEMPLATE
# Enterprise-Grade React/Next.js Application

## TECH STACK
- Framework: Next.js 15 (App Router)
- UI: React 19 + TypeScript 5
- Styling: Tailwind CSS 4 + shadcn/ui
- State: Zustand + TanStack Query
- Forms: React Hook Form + Zod
- Testing: Vitest + Playwright
- Linting: ESLint + Prettier

## STRUCTURE
```
src/
├── app/                      # Next.js App Router
│   ├── (auth)/              # Auth routes
│   │   ├── login/
│   │   └── register/
│   ├── (dashboard)/         # Protected routes
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── api/                 # API routes
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── ui/                  # shadcn components
│   ├── forms/              # Form components
│   └── features/           # Feature components
├── lib/
│   ├── api.ts              # API client
│   ├── auth.ts             # Auth utilities
│   └── utils.ts            # Helpers
├── hooks/                   # Custom hooks
├── stores/                  # Zustand stores
├── types/                   # TypeScript types
└── styles/                  # Global styles

public/
├── fonts/
└── images/

tests/
├── unit/
├── integration/
└── e2e/
```

## FEATURES
- Dark/Light mode
- Responsive design
- Form validation
- Error boundaries
- Loading states
- SEO optimized
- Analytics ready
- Accessibility (WCAG)

## PERFORMANCE
- Server Components
- Image optimization
- Font optimization
- Code splitting
- Bundle analysis
- Lighthouse 95+