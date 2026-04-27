# WORLD-CLASS SKILL: Enterprise DevOps & Deployment

## CI/CD PIPELINE

### GitHub Actions - Production Pipeline
```yaml
name: Production Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # 1. Security Scan
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Trivy
        run: |
          docker build -t $IMAGE_NAME:scan .
          trivy image --severity HIGH,CRITICAL $IMAGE_NAME:scan
      
      - name: Run Bandit
        run: pip install bandit && bandit -r src/
      
      - name: Dependency Audit
        run: npm audit --audit-level=high

  # 2. Build & Test
  build:
    needs: security
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Lint
        run: npm run lint
      
      - name: Type check
        run: npm run typecheck
      
      - name: Unit tests
        run: npm run test:coverage
      
      - name: Build
        run: npm run build
      
      - name: Build Docker
        run: |
          docker build -t $IMAGE_NAME:${{ github.sha }} .
          docker build -t $IMAGE_NAME:latest .

  # 3. Integration Tests
  integration-test:
    needs: build
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      
      - name: Pull Docker image
        run: docker pull $IMAGE_NAME:${{ github.sha }}
      
      - name: Run integration tests
        run: |
          docker-compose -f docker-compose.test.yml up -d
          npm run test:integration
          docker-compose down

  # 4. Deploy to Staging
  deploy-staging:
    needs: integration-test
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster staging --service app --force-new-deployment
          aws ecs wait services-stable --cluster staging --services app

  # 5. Production Deploy (after approval)
  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster production --service app --force-new-deployment
          aws ecs wait services-stable --cluster production --services app

  # 6. Post-deploy smoke tests
  smoke-test:
    needs: deploy-production
    runs-on: ubuntu-latest
    steps:
      - name: Smoke tests
        run: |
          curl -f https://api.example.com/health || exit 1
          curl -f https://app.example.com || exit 1
```

### Docker Compose - Full Stack
```yaml
version: '3.9'

services:
  # Application
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://user:pass@db:5432/app
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # Database
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: app
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d app"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes - Production Ready
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  labels:
    app: app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: app
  template:
    metadata:
      labels:
        app: app
    spec:
      containers:
      - name: app
        image: app:latest
        ports:
        - containerPort: 3000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        env:
        - name: NODE_ENV
          value: "production"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/ready
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: secrets
          mountPath: /app/secrets
          readOnly: true
      volumes:
      - name: secrets
        secret:
          secretName: app-secrets

---
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## INFRASTRUCTURE AS CODE

### Terraform - AWS Production
```hcl
# main.tf
provider "aws" {
  region = "us-east-1"
}

# EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"
  
  cluster_name    = "production"
  cluster_version = "1.28"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  eks_managed_node_groups = {
    primary = {
      min_size       = 3
      max_size       = 10
      instance_types = ["m6i.xlarge"]
    }
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "main" {
  identifier           = "production-db"
  engine               = "postgres"
  engine_version       = "16.1"
  instance_class       = "db.r6g.xlarge"
  allocated_storage    = 100
  storage_encrypted    = true
  multi_az             = true
  backup_retention_period = 30
  skip_final_snapshot  = false
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "production-redis"
  engine               = "redis"
  node_type            = "cache.r6g.xlarge"
  num_cache_nodes      = 2
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
}

# S3 for static assets
resource "aws_s3_bucket" "assets" {
  bucket = "production-assets"
}

# CloudFront CDN
resource "aws_cloudfront_distribution" "cdn" {
  origin {
    domain_name = aws_s3_bucket.assets.bucket_regional_domain_name
    origin_id   = "S3-assets"
  }
  
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Production CDN"
  
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-assets"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }
}
```

---

## MONITORING & OBSERVABILITY

### Prometheus + Grafana Stack
- Metrics collection
- Custom dashboards
- Alertmanager for alerts
- Loki for logs

### Tracing
- OpenTelemetry integration
- Jaeger/X-Ray backend

### Logging
- Structured JSON logs
- Log aggregation (Loki)
- Retention policies