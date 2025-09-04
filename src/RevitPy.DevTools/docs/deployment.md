# RevitPy Developer Tools Deployment Guide

This guide covers deployment strategies for the RevitPy Developer Tools suite across different environments.

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [Development Environment](#development-environment)
3. [Production Environment](#production-environment)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Monitoring & Health Checks](#monitoring--health-checks)
8. [Security Considerations](#security-considerations)
9. [Troubleshooting](#troubleshooting)

## Deployment Overview

The RevitPy Developer Tools consist of multiple interconnected services:

- **Dashboard App**: React application for the main developer interface
- **Package Registry**: Web interface for package discovery and management
- **Hot Reload Server**: Development server for real-time updates
- **VS Code Extension**: Development environment integration
- **WebView2 Host**: .NET application for embedding web content in Revit

## Development Environment

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- .NET 6+ SDK
- Visual Studio Code
- Docker (optional)

### Local Setup

1. **Clone and Install Dependencies**:
```bash
git clone <repository-url>
cd RevitPy.DevTools
npm install
```

2. **Start Development Servers**:
```bash
# Start all services in development mode
npm run dev

# Or start individual services
npm run dev:dashboard    # Dashboard on port 3000
npm run dev:registry     # Package registry on port 3001
npm run dev:hotreload    # Hot reload server on port 3002
```

3. **Install VS Code Extension**:
```bash
cd src/RevitPy.VSCodeExtension
npm run package
code --install-extension revitpy-*.vsix
```

4. **Build .NET WebView2 Host**:
```bash
cd src/RevitPy.WebHost
dotnet build
dotnet run
```

### Environment Configuration

Create a `.env.local` file in each application directory:

```bash
# Dashboard (.env.local)
VITE_API_BASE_URL=http://localhost:3001
VITE_WEBSOCKET_URL=ws://localhost:3002
VITE_ENVIRONMENT=development
VITE_LOG_LEVEL=debug

# Package Registry
DATABASE_URL=postgresql://localhost:5432/revitpy_dev
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-dev-jwt-secret
STORAGE_PATH=./storage/packages

# Hot Reload Server
PORT=3002
WATCH_PATHS=./src,../dashboard/src
REVIT_CONNECTION_PORT=3003
```

## Production Environment

### Build Process

1. **Build Frontend Applications**:
```bash
# Build dashboard
cd apps/dashboard
npm run build

# Build package registry
cd ../package-registry
npm run build

# Build component library
cd ../../packages/ui
npm run build
```

2. **Build .NET Applications**:
```bash
cd src/RevitPy.WebHost
dotnet publish -c Release -o publish

cd ../RevitPy.HotReload
dotnet publish -c Release -o publish
```

3. **Package VS Code Extension**:
```bash
cd src/RevitPy.VSCodeExtension
npm run package
```

### Static File Serving

Serve built frontend applications using nginx:

```nginx
# /etc/nginx/sites-available/revitpy-devtools
server {
    listen 80;
    server_name devtools.revitpy.local;

    # Dashboard
    location / {
        root /var/www/revitpy/dashboard/dist;
        try_files $uri $uri/ /index.html;
        
        # Enable gzip compression
        gzip on;
        gzip_types text/css application/javascript application/json image/svg+xml;
        gzip_min_length 1000;
    }

    # Package Registry API
    location /api/ {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket connections
    location /ws {
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Static assets caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## Docker Deployment

### Multi-Stage Dockerfiles

**Dashboard Dockerfile**:
```dockerfile
# apps/dashboard/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Package Registry Dockerfile**:
```dockerfile
# apps/package-registry/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:18-alpine AS runtime
WORKDIR /app

RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

USER nextjs
EXPOSE 3001
CMD ["node", "dist/server.js"]
```

**Hot Reload Server Dockerfile**:
```dockerfile
# src/RevitPy.HotReload/Dockerfile
FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build
WORKDIR /src

COPY *.csproj ./
RUN dotnet restore

COPY . .
RUN dotnet publish -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/runtime:6.0
WORKDIR /app
COPY --from=build /app/publish .

EXPOSE 3002
ENTRYPOINT ["dotnet", "RevitPy.HotReload.dll"]
```

### Docker Compose

**Development**:
```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  dashboard:
    build:
      context: ./apps/dashboard
      dockerfile: Dockerfile.dev
    ports:
      - "3000:3000"
    volumes:
      - ./apps/dashboard/src:/app/src
      - ./packages:/app/packages
    environment:
      - VITE_API_BASE_URL=http://localhost:3001
      - VITE_WEBSOCKET_URL=ws://localhost:3002
      - NODE_ENV=development

  package-registry:
    build:
      context: ./apps/package-registry
      dockerfile: Dockerfile.dev
    ports:
      - "3001:3001"
    volumes:
      - ./apps/package-registry/src:/app/src
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/revitpy_dev
      - REDIS_URL=redis://redis:6379
      - NODE_ENV=development
    depends_on:
      - postgres
      - redis

  hot-reload:
    build:
      context: ./src/RevitPy.HotReload
    ports:
      - "3002:3002"
    volumes:
      - ./src:/src
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - WATCH_PATHS=/src

  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: revitpy_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

**Production**:
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - dashboard
      - package-registry
      - hot-reload

  dashboard:
    build:
      context: ./apps/dashboard
      dockerfile: Dockerfile
    environment:
      - NODE_ENV=production
    restart: unless-stopped

  package-registry:
    build:
      context: ./apps/package-registry
      dockerfile: Dockerfile
    environment:
      - NODE_ENV=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  hot-reload:
    build:
      context: ./src/RevitPy.HotReload
    environment:
      - ASPNETCORE_ENVIRONMENT=Production
    restart: unless-stopped

  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

## Kubernetes Deployment

### Namespace and ConfigMap

```yaml
# k8s/namespace.yml
apiVersion: v1
kind: Namespace
metadata:
  name: revitpy-devtools

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: revitpy-config
  namespace: revitpy-devtools
data:
  database-url: "postgresql://postgres:5432/revitpy"
  redis-url: "redis://redis:6379"
  api-base-url: "https://api.devtools.revitpy.com"
  websocket-url: "wss://ws.devtools.revitpy.com"
```

### Dashboard Deployment

```yaml
# k8s/dashboard.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dashboard
  namespace: revitpy-devtools
spec:
  replicas: 3
  selector:
    matchLabels:
      app: dashboard
  template:
    metadata:
      labels:
        app: dashboard
    spec:
      containers:
      - name: dashboard
        image: revitpy/dashboard:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 80
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: dashboard-service
  namespace: revitpy-devtools
spec:
  selector:
    app: dashboard
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
```

### Package Registry Deployment

```yaml
# k8s/package-registry.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: package-registry
  namespace: revitpy-devtools
spec:
  replicas: 2
  selector:
    matchLabels:
      app: package-registry
  template:
    metadata:
      labels:
        app: package-registry
    spec:
      containers:
      - name: package-registry
        image: revitpy/package-registry:latest
        ports:
        - containerPort: 3001
        env:
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: revitpy-config
              key: database-url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: revitpy-config
              key: redis-url
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: revitpy-secrets
              key: jwt-secret
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 3001
          initialDelaySeconds: 10
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: package-registry-service
  namespace: revitpy-devtools
spec:
  selector:
    app: package-registry
  ports:
  - port: 3001
    targetPort: 3001
  type: ClusterIP
```

### Ingress Configuration

```yaml
# k8s/ingress.yml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: revitpy-devtools-ingress
  namespace: revitpy-devtools
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/websocket-services: "hot-reload-service"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  tls:
  - hosts:
    - devtools.revitpy.com
    - api.devtools.revitpy.com
    - ws.devtools.revitpy.com
    secretName: revitpy-devtools-tls
  rules:
  - host: devtools.revitpy.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: dashboard-service
            port:
              number: 80
  - host: api.devtools.revitpy.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: package-registry-service
            port:
              number: 3001
  - host: ws.devtools.revitpy.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: hot-reload-service
            port:
              number: 3002
```

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy RevitPy DevTools

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: revitpy/devtools

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        cache: 'npm'
    
    - name: Install dependencies
      run: npm ci
    
    - name: Run linting
      run: npm run lint
    
    - name: Run type checking
      run: npm run type-check
    
    - name: Run unit tests
      run: npm run test
    
    - name: Run integration tests
      run: npm run test:integration
    
    - name: Run E2E tests
      run: npm run test:e2e

  build:
    needs: test
    runs-on: ubuntu-latest
    strategy:
      matrix:
        app: [dashboard, package-registry]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Log in to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-${{ matrix.app }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha,prefix=sha-
          type=raw,value=latest,enable={{is_default_branch}}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: ./apps/${{ matrix.app }}
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup kubectl
      uses: azure/setup-kubectl@v3
      with:
        version: 'v1.24.0'
    
    - name: Setup Kustomize
      uses: imranismail/setup-kustomize@v1
      with:
        kustomize-version: '4.5.7'
    
    - name: Deploy to staging
      run: |
        cd k8s/staging
        kustomize edit set image dashboard=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-dashboard:sha-${{ github.sha }}
        kustomize edit set image package-registry=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-package-registry:sha-${{ github.sha }}
        kubectl apply -k .
      env:
        KUBE_CONFIG_DATA: ${{ secrets.KUBE_CONFIG_DATA }}
    
    - name: Wait for deployment
      run: kubectl rollout status deployment/dashboard deployment/package-registry -n revitpy-devtools-staging
    
    - name: Run smoke tests
      run: npm run test:smoke -- --env staging
    
    - name: Deploy to production
      if: success()
      run: |
        cd k8s/production
        kustomize edit set image dashboard=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-dashboard:sha-${{ github.sha }}
        kustomize edit set image package-registry=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-package-registry:sha-${{ github.sha }}
        kubectl apply -k .
      env:
        KUBE_CONFIG_DATA: ${{ secrets.KUBE_CONFIG_DATA_PROD }}
```

## Monitoring & Health Checks

### Health Check Endpoints

**Dashboard Health Check** (`/health`):
```typescript
// Health check for static dashboard
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: process.env.npm_package_version,
    uptime: process.uptime()
  });
});
```

**Package Registry Health Check** (`/health`):
```typescript
app.get('/health', async (req, res) => {
  try {
    // Check database connection
    await db.raw('SELECT 1');
    
    // Check Redis connection
    await redis.ping();
    
    res.status(200).json({
      status: 'healthy',
      checks: {
        database: 'healthy',
        cache: 'healthy'
      },
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(503).json({
      status: 'unhealthy',
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});
```

### Prometheus Metrics

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'revitpy-dashboard'
    static_configs:
      - targets: ['dashboard:80']
    metrics_path: '/metrics'
    
  - job_name: 'revitpy-package-registry'
    static_configs:
      - targets: ['package-registry:3001']
    metrics_path: '/metrics'
    
  - job_name: 'revitpy-hot-reload'
    static_configs:
      - targets: ['hot-reload:3002']
    metrics_path: '/metrics'

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "RevitPy DevTools Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{status}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m])",
            "legendFormat": "5xx errors"
          }
        ]
      }
    ]
  }
}
```

## Security Considerations

### SSL/TLS Configuration

```nginx
# SSL configuration for production
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;

# Security headers
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' wss: https:" always;
```

### Environment Variables

```bash
# Production environment variables
NODE_ENV=production
JWT_SECRET=<strong-random-secret>
DATABASE_URL=postgresql://user:password@host:5432/database
REDIS_URL=redis://user:password@host:6379
CORS_ORIGIN=https://devtools.revitpy.com
API_RATE_LIMIT=100
SESSION_SECRET=<another-strong-secret>
BCRYPT_ROUNDS=12
```

### Network Policies

```yaml
# k8s/network-policy.yml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: revitpy-devtools-netpol
  namespace: revitpy-devtools
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    - podSelector:
        matchLabels:
          app: dashboard
    - podSelector:
        matchLabels:
          app: package-registry
    - podSelector:
        matchLabels:
          app: hot-reload
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    - podSelector:
        matchLabels:
          app: redis
  - to: []
    ports:
    - protocol: TCP
      port: 53
    - protocol: UDP
      port: 53
```

## Troubleshooting

### Common Issues

**1. WebSocket Connection Failures**
```bash
# Check WebSocket server logs
kubectl logs -f deployment/hot-reload -n revitpy-devtools

# Test WebSocket connection
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: test" http://localhost:3002/ws
```

**2. Database Connection Issues**
```bash
# Check database connectivity
kubectl exec -it deployment/postgres -n revitpy-devtools -- psql -U postgres -c "SELECT version();"

# Check connection pool
kubectl logs -f deployment/package-registry -n revitpy-devtools | grep -i "database\|connection"
```

**3. Memory/CPU Issues**
```bash
# Check resource usage
kubectl top pods -n revitpy-devtools

# Check resource limits
kubectl describe pod <pod-name> -n revitpy-devtools
```

**4. SSL Certificate Problems**
```bash
# Check certificate status
kubectl get certificate -n revitpy-devtools
kubectl describe certificate revitpy-devtools-tls -n revitpy-devtools

# Check cert-manager logs
kubectl logs -f deployment/cert-manager -n cert-manager
```

### Debug Commands

```bash
# Port forward for local debugging
kubectl port-forward svc/dashboard-service 3000:80 -n revitpy-devtools
kubectl port-forward svc/package-registry-service 3001:3001 -n revitpy-devtools

# Access pod shell
kubectl exec -it deployment/dashboard -n revitpy-devtools -- sh

# View logs
kubectl logs -f deployment/dashboard -n revitpy-devtools --previous
kubectl logs -f deployment/package-registry -n revitpy-devtools --tail=100

# Check service endpoints
kubectl get endpoints -n revitpy-devtools

# Test service connectivity
kubectl run debug --image=busybox -it --rm --restart=Never -n revitpy-devtools -- sh
```

### Performance Optimization

**1. Database Optimization**
```sql
-- Add database indexes
CREATE INDEX CONCURRENTLY idx_packages_name ON packages(name);
CREATE INDEX CONCURRENTLY idx_packages_created_at ON packages(created_at);
CREATE INDEX CONCURRENTLY idx_downloads_package_id ON downloads(package_id);

-- Analyze table statistics
ANALYZE packages;
ANALYZE downloads;
```

**2. Redis Optimization**
```bash
# Redis configuration
maxmemory 256mb
maxmemory-policy allkeys-lru
tcp-keepalive 60
timeout 300
```

**3. Application Optimization**
```typescript
// Enable compression middleware
app.use(compression({
  level: 6,
  threshold: 1000,
  filter: (req, res) => {
    return compression.filter(req, res);
  }
}));

// Enable response caching
app.use('/api/packages', cache('5 minutes'));
```

This deployment guide provides comprehensive instructions for deploying the RevitPy Developer Tools across different environments, from development to production Kubernetes clusters, with proper monitoring, security, and troubleshooting procedures.