# GitHub Actions CI/CD Implementation Guide

## 🎯 Overview

This guide covers the complete GitHub Actions CI/CD implementation for Dev-Assist, providing ephemeral PR environments with promotion to development environments.

## 🏗️ Architecture

```
Pull Request → Ephemeral Environment → Development Environment
     │                    │                        │
     ├─ Quality Gates     ├─ Fast Testing          ├─ Extended Testing
     ├─ Docker Build      ├─ SQLite Database       ├─ PostgreSQL Database
     ├─ Automated Tests   ├─ Auto-cleanup          ├─ Persistent State
     └─ Security Scan     └─ PR Comments           └─ Team Sharing
```

## 📋 Workflows Implemented

### 1. PR Environment Workflow (`.github/workflows/pr-environment.yml`)

**Triggers:**
- Pull request opened/synchronized/reopened
- Pull request approved
- Manual workflow dispatch
- PR comments with `/deploy` or `/test`

**Jobs:**
1. **Quality Gates**: Linting, testing, security scanning
2. **Build**: Docker images for API and frontend
3. **Deploy**: Ephemeral environment with unique ports
4. **Test**: Smoke tests and health verification
5. **Comment**: PR updates with environment URLs
6. **Cleanup**: Automatic cleanup on PR close

**Features:**
- ✅ Unique environment per PR (isolated containers)
- ✅ Port-based routing (8000+PR%, 3000+PR%)
- ✅ SQLite database for fast startup
- ✅ Auto-cleanup after 24 hours
- ✅ PR comments with environment URLs
- ✅ Manual cleanup via `/cleanup` command

### 2. Promotion Workflow (`.github/workflows/promote-to-dev.yml`)

**Triggers:**
- PR comment with `/deploy-to-dev`
- Manual workflow dispatch

**Jobs:**
1. **Validation**: PR approval status, CI checks, merge conflicts
2. **Backup**: Development environment state backup
3. **Deploy**: Production-style deployment to development
4. **Test**: Integration tests and health verification
5. **Notify**: Team notifications and status updates

**Features:**
- ✅ Promotion validation and approval gates
- ✅ Automatic backup before deployment
- ✅ Production-ready deployment process
- ✅ Rollback capability via `/rollback-dev`
- ✅ Team notifications and status tracking

## 🚀 Quick Start

### 1. Repository Setup

**Required Secrets:**
- `GITHUB_TOKEN` (automatically provided)

**Optional Secrets (for production deployment):**
- Cloud provider credentials
- Notification webhooks (Slack, email)

**Required Files:**
- `.github/workflows/pr-environment.yml`
- `.github/workflows/promote-to-dev.yml`
- `docker-compose.pr.yml`
- `frontend/Dockerfile.dev`

### 2. First PR Environment

1. **Create a Pull Request**
2. **Wait for Automatic Deployment** (5-10 minutes)
3. **Access Environment URLs** (posted in PR comments)
4. **Test Your Changes** in the live environment

### 3. Promote to Development

1. **Comment `/deploy-to-dev`** on the PR
2. **Wait for Validation** and deployment
3. **Access Development Environment** at configured URL
4. **Share with Team** for extended testing

## 🎮 Available Commands

### PR Comments

| Command | Description | Example |
|---------|-------------|---------|
| `/deploy` | Redeploy ephemeral environment | `/deploy` |
| `/test` | Run tests on current environment | `/test` |
| `/cleanup` | Manually cleanup environment | `/cleanup` |
| `/deploy-to-dev` | Promote to development | `/deploy-to-dev` |
| `/rollback-dev` | Rollback development | `/rollback-dev` |

### Manual Workflows

**GitHub Actions UI:**
- Go to Actions tab
- Select workflow
- Click "Run workflow"
- Enter PR number and options

## 🔧 Configuration

### Environment Ports

Ephemeral environments use dynamic ports based on PR number:
- **API Port**: `8000 + (PR_NUMBER % 100)`
- **Frontend Port**: `3000 + (PR_NUMBER % 100)`
- **Redis Port**: `6379 + (PR_NUMBER % 100)`

### Environment Variables

**Ephemeral Environment:**
```bash
# Automatically set by workflow
PR_NUMBER=123
ENVIRONMENT=pr-123
API_PORT=8023
FRONTEND_PORT=3023
DATABASE_URL=sqlite:///tmp/pr-123.db
MOCK_EXTERNAL_SERVICES=true
```

**Development Environment:**
```bash
# Production-like configuration
ENVIRONMENT=development
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SECRETS_PROVIDER=environment
```

## 📊 Monitoring & Observability

### Deployment State Tracking

Use the environment state management script:

```bash
# List all environments
./.github/scripts/environment-state.py list

# Get specific environment
./.github/scripts/environment-state.py get pr-123

# View deployment history
./.github/scripts/environment-state.py history --limit 20

# Cleanup old environments
./.github/scripts/environment-state.py cleanup --max-age-hours 24
```

### Health Monitoring

Comprehensive smoke tests are included:

```bash
# Run smoke tests locally
./.github/scripts/smoke-tests.sh --api-url http://localhost:8023 --frontend-url http://localhost:3023

# Run with verbose output
./.github/scripts/smoke-tests.sh --verbose
```

### Test Coverage

**Quality Gates Include:**
- Python linting (black, flake8, mypy)
- Frontend linting (ESLint, Prettier)
- Security scanning (Bandit, npm audit)
- Unit tests with coverage
- Integration tests
- Container vulnerability scanning

## 🔒 Security Features

### Access Control
- Repository secrets for sensitive data
- Environment protection rules
- Manual approval gates for production promotion
- Audit logging for all deployments

### Container Security
- Non-root containers
- Resource limits and constraints
- Vulnerability scanning
- Image signing (ready for implementation)

### Network Security
- Isolated container networks
- Port-based routing
- CORS configuration
- Security headers validation

## 🛠️ Customization

### Adding New Environments

1. **Create Environment Profile**:
   ```bash
   cp config/development.env config/testing.env
   ```

2. **Add Workflow Jobs**:
   ```yaml
   deploy-to-testing:
     if: contains(github.event.comment.body, '/deploy-to-testing')
     # ... deployment logic
   ```

3. **Update State Management**:
   ```python
   # Add new environment type
   class EnvironmentType(Enum):
       TESTING = "testing"
   ```

### Custom Tests

Add custom tests to smoke-tests.sh:

```bash
# Custom API tests
test_custom_endpoints() {
    test_endpoint "GET" "$API_BASE_URL/api/v1/custom" "200" "Custom endpoint test"
}
```

### Notification Integration

Add Slack/email notifications:

```yaml
- name: Send notification
  env:
    SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
  run: |
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"Deployment successful!"}' \
      $SLACK_WEBHOOK
```

## 🐛 Troubleshooting

### Common Issues

**1. Port Conflicts**
```bash
# Check if ports are in use
docker ps --format "table {{.Names}}\t{{.Ports}}"

# Cleanup stuck containers
docker-compose -p pr-123 down -v --remove-orphans
```

**2. Image Build Failures**
```bash
# Check build context
docker build --no-cache .

# Verify registry authentication
docker login ghcr.io
```

**3. Environment Not Responding**
```bash
# Check container logs
docker-compose -p pr-123 logs

# Verify health checks
curl -f http://localhost:8023/api/v1/healthz
```

**4. Database Issues**
```bash
# Reset SQLite database
rm /tmp/pr-123.db

# Check database permissions
ls -la /tmp/pr-*.db
```

### Debug Mode

Enable verbose logging:

```yaml
# In workflow file
env:
  VERBOSE: true
  DEBUG: true
```

## 📈 Performance Optimization

### Build Speed
- Docker layer caching
- Multi-stage builds
- Parallel job execution
- Dependency caching

### Resource Usage
- Container resource limits
- Efficient image sizes
- Smart port allocation
- Automatic cleanup

### Cost Optimization
- GitHub-hosted runners (included in plan)
- Efficient build strategies
- Ephemeral environments (no persistent costs)
- Smart caching policies

## 🔄 Migration from Manual Deployment

**Phase 1**: Set up ephemeral environments (✅ Complete)
**Phase 2**: Add development promotion (✅ Complete)
**Phase 3**: Staging integration (Next step)
**Phase 4**: Production deployment (Future)

### Gradual Adoption

1. **Start with feature branches** - Use ephemeral environments for testing
2. **Promote stable changes** - Use development environment for demos
3. **Team collaboration** - Share development environment URLs
4. **Iterate and improve** - Add more environments as needed

## 🎯 Next Steps

### Immediate Improvements
- [ ] Add staging environment promotion
- [ ] Implement database seeding for dev environment
- [ ] Add performance benchmarking
- [ ] Enhance notification system

### Advanced Features
- [ ] Blue/green deployments
- [ ] Canary releases
- [ ] Multi-region deployment
- [ ] Advanced monitoring with Prometheus/Grafana

### Integration Opportunities
- [ ] Integrate with existing Google Cloud deployment
- [ ] Add compliance and security scanning
- [ ] Implement feature flags
- [ ] Add A/B testing capabilities

---

**🚀 Ready to Deploy!** Your GitHub Actions CI/CD pipeline is now configured for efficient development workflows with ephemeral testing and development environment promotion.