#!/usr/bin/env python3
"""
PROJECT INITIALIZATION SYSTEM
Like Codex's project creation - initialize full projects with best practices
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

TEMPLATES = {
    "saas": {
        "name": "Enterprise SaaS",
        "description": "Full-stack multi-tenant SaaS application",
        "tech": ["Next.js 15", "TypeScript", "PostgreSQL", "Prisma", "NextAuth"],
        "files": {
            "package.json": """{
  "name": "enterprise-saas",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest",
    "test:coverage": "vitest --coverage"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@prisma/client": "^5.0.0",
    "next-auth": "^5.0.0",
    "zod": "^3.23.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "eslint": "^8.0.0",
    "vitest": "^1.0.0",
    "@testing-library/react": "^14.0.0",
    "prisma": "^5.0.0"
  }
}""",
            "tsconfig.json": """{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}""",
            "next.config.ts": """import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
}

export default nextConfig""",
            ".env.example": """# Database
DATABASE_URL="postgresql://user:password@localhost:5432/db"

# NextAuth
NEXTAUTH_SECRET="your-secret-here"
NEXTAUTH_URL="http://localhost:3000"

# OAuth (add your own)
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
GITHUB_CLIENT_ID=""
GITHUB_CLIENT_SECRET=""
""",
            "prisma/schema.prisma": """generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id            String    @id @default(cuid())
  email         String    @unique
  name          String?
  password      String
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

model Account {
  id                String  @id @default(cuid())
  userId            String
  type              String
  provider          String
  providerAccountId String
  refresh_token     String? @db.Text
  access_token     String? @db.Text
  expires_at        Int?
  token_type        String?
  scope             String?
  id_token          String? @db.Text
  session_state    String?
  user             User    @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([provider, providerAccountId])
}

model Session {
  id           String   @id @default(cuid())
  sessionToken String   @unique
  userId       String
  expires      DateTime
  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)
}"""
        }
    },
    
    "api": {
        "name": "REST API Service",
        "description": "Production REST API with rate limiting, caching",
        "tech": ["Fastify", "TypeScript", "PostgreSQL", "Redis"],
        "files": {
            "package.json": """{
  "name": "api-service",
  "version": "1.0.0",
  "main": "dist/index.js",
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "test": "vitest"
  },
  "dependencies": {
    "fastify": "^4.25.0",
    "@fastify/cors": "^8.5.0",
    "@fastify/rate-limit": "^9.1.0",
    "@prisma/client": "^5.0.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "tsx": "^4.0.0",
    "vitest": "^1.0.0",
    "prisma": "^5.0.0"
  }
}"""
        }
    },
    
    "cli": {
        "name": "CLI Tool",
        "description": "Command-line interface application",
        "tech": ["Commander", "TypeScript", "Oclif"],
        "files": {
            "package.json": """{
  "name": "my-cli",
  "version": "1.0.0",
  "bin": {
    "my-cli": "./bin/run.js"
  },
  "scripts": {
    "dev": "tsx src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {
    "commander": "^11.0.0",
    "chalk": "^5.0.0"
  }
}"""
        }
    }
}

class ProjectInitializer:
    """Initialize projects with full structure - like Codex"""
    
    def __init__(self, base_path: str = "workspace"):
        self.base_path = Path(base_path)
        
    def create_project(self, name: str, template: str = "saas") -> Dict[str, Any]:
        """Create a new project from template"""
        if template not in TEMPLATES:
            return {"error": f"Template {template} not found"}
            
        project_path = self.base_path / name
        project_path.mkdir(parents=True, exist_ok=True)
        
        template_data = TEMPLATES[template]
        
        # Create all files
        for filename, content in template_data.get("files", {}).items():
            file_path = project_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            
        # Create README
        readme = f"""# {template_data['name']}

{template_data['description']}

## Tech Stack
- {', '.join(template_data['tech'])}

## Getting Started

```bash
# Install dependencies
npm install

# Set up environment
cp .env.example .env

# Generate Prisma client (if using)
npx prisma generate

# Run database migrations
npx prisma db push

# Start development
npm run dev
```

## Available Scripts

- `npm run dev` - Development server
- `npm run build` - Production build
- `npm run test` - Run tests

## Project Structure
"""
        
        # Add structure based on template
        if template == "saas":
            readme += """
```
src/
├── app/              # Next.js App Router
│   ├── api/         # API routes
│   └── (routes)/    # Page routes
├── components/       # React components
├── lib/             # Utilities
├── hooks/           # Custom hooks
├── stores/          # Zustand stores
└── types/           # TypeScript types
```
"""
        
        (project_path / "README.md").write_text(readme)
        
        return {
            "success": True,
            "project": name,
            "template": template,
            "path": str(project_path)
        }
    
    def list_templates(self) -> Dict[str, Any]:
        """List available templates"""
        return {
            name: {
                "name": data["name"],
                "description": data["description"],
                "tech": data["tech"]
            }
            for name, data in TEMPLATES.items()
        }


def main():
    import sys
    
    initializer = ProjectInitializer("workspace")
    
    if len(sys.argv) < 2:
        print("Available templates:")
        for name, info in initializer.list_templates().items():
            print(f"  {name:12} - {info['name']}")
            print(f"              {info['description']}")
        print("\nUsage: python init_project.py <project-name> [template]")
        return
    
    name = sys.argv[1]
    template = sys.argv[2] if len(sys.argv) > 2 else "saas"
    
    result = initializer.create_project(name, template)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"✅ Created {result['project']} at {result['path']}")


if __name__ == "__main__":
    main()