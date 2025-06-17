# Supervisor Coding Agent

A production-grade MVP for orchestrating and managing Claude AI coding tasks with async queueing, quota management, and comprehensive monitoring.

## Features

- **Task Orchestration**: Async task queueing with Celery and Redis
- **Multi-Agent Support**: Multiple Claude Code CLI agents with automatic failover
- **Quota Management**: Intelligent routing based on API quota limits
- **Shared Memory**: Context sharing across task sessions
- **Audit Logging**: Complete audit trail of all operations
- **Notifications**: Slack and email alerts for system events
- **REST API**: FastAPI-based API for task submission and monitoring
- **Health Monitoring**: Comprehensive health checks and metrics

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Claude CLI tool (optional for testing)

### 🚀 One-Command Setup

```bash
# Clone and run the quick start script
git clone https://github.com/your-username/supervisor-coding-agent.git
cd supervisor-coding-agent
./scripts/quick-start.sh
```

This script will:
- Setup environment configuration
- Start PostgreSQL and Redis
- Run database migrations
- Guide you through starting the API and workers

### 🔧 Development Setup

For a complete development environment:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Run development setup
./scripts/dev-setup.sh
```

### 📦 Docker-Only Setup

If you prefer Docker-only setup:

```bash
# Copy environment file
cp .env.sample .env

# Start all services
make docker-up

# Check status
make health-check
```

### 🏃‍♂️ Manual Setup

1. **Setup environment**:
   ```bash
   cp .env.sample .env
   # Edit .env with your Claude API keys
   ```

2. **Install dependencies**:
   ```bash
   make install
   ```

3. **Start services**:
   ```bash
   make docker-up  # Start databases
   make run        # Start API (in terminal 1)
   make run-worker # Start worker (in terminal 2)
   ```

### ✅ Verify Installation

```bash
# Run health check
./scripts/health-check.sh

# Or check individual endpoints
curl http://localhost:8000/api/v1/healthz
curl http://localhost:8000/api/v1/health/detailed
```

### 🌐 Access Points

- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/healthz
- **Metrics**: http://localhost:8000/api/v1/metrics


## Configuration

Key environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/supervisor_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# Claude Configuration
CLAUDE_API_KEYS=key1,key2,key3
CLAUDE_QUOTA_LIMIT_PER_AGENT=1000
CLAUDE_QUOTA_RESET_HOURS=24

# Notifications
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_CHANNEL=#alerts
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

## API Usage

### Submit a Task

```bash
curl -X POST "http://localhost:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "PR_REVIEW",
    "payload": {
      "repository": "owner/repo",
      "pr_number": 123,
      "title": "Fix user authentication",
      "description": "Updates login flow",
      "diff": "--- a/auth.py\n+++ b/auth.py\n@@ -1,3 +1,3 @@\n-old\n+new"
    },
    "priority": 8
  }'
```

### Task Types

- `PR_REVIEW`: Pull request code review
- `ISSUE_SUMMARY`: Issue analysis and summary  
- `CODE_ANALYSIS`: Code quality analysis
- `REFACTOR`: Code refactoring assistance
- `BUG_FIX`: Bug investigation and fixes
- `FEATURE`: Feature implementation guidance

### Get Task Status

```bash
curl "http://localhost:8000/api/v1/tasks/1"
```

### Monitor System Health

```bash
curl "http://localhost:8000/api/v1/healthz"
curl "http://localhost:8000/api/v1/agents/quota/status"
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI API   │    │  Celery Worker  │    │ Claude CLI Agent│
│                 │    │                 │    │                 │
│ • Task Submit   │───▶│ • Task Process  │───▶│ • Code Analysis │
│ • Status Query  │    │ • Batch Jobs    │    │ • PR Reviews    │
│ • Health Check  │    │ • Scheduling    │    │ • Bug Fixes     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis      │    │ Shared Memory   │
│                 │    │                 │    │                 │
│ • Tasks         │    │ • Task Queue    │    │ • Context Cache │
│ • Sessions      │    │ • Results       │    │ • Project Data  │
│ • Agents        │    │ • Locks         │    │ • Session Hist  │
│ • Audit Logs    │    │ • Cache         │    │ • Dedup Store   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Development

### Setup Scripts

The `scripts/` directory contains helpful setup scripts:

- **`./scripts/setup.sh`** - Interactive setup with dependency checking
- **`./scripts/quick-start.sh`** - Minimal setup to get running quickly  
- **`./scripts/dev-setup.sh`** - Complete development environment setup
- **`./scripts/health-check.sh`** - Comprehensive system health verification

### Running Tests

```bash
make test          # Full test suite with coverage
make test-fast     # Quick tests without coverage
```

### Code Quality

```bash
make lint          # Run linting
make format        # Format code
```

### Database Migrations

```bash
make migrate                           # Apply migrations
make migrate-create MESSAGE="description"  # Create new migration
```

### Monitoring

```bash
make docker-logs        # All service logs
make docker-logs-api    # API logs only
make docker-logs-worker # Worker logs only
```

## Production Deployment

### Docker Compose (Recommended)

```bash
# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Kubernetes

See `k8s/` directory for Kubernetes manifests.

### Environment Variables

Production-specific variables:

```bash
APP_DEBUG=false
LOG_LEVEL=INFO
WORKER_CONCURRENCY=4
BATCH_SIZE=10
BATCH_INTERVAL_SECONDS=60
```

## Monitoring & Alerts

### Health Endpoints

- `/api/v1/healthz` - Basic health check
- `/api/v1/readyz` - Readiness check  
- `/api/v1/health/detailed` - Detailed component status
- `/api/v1/metrics` - Prometheus-style metrics

### Notifications

System automatically sends alerts for:

- All agents hitting quota limits
- Task failures exceeding retry limits
- System component failures
- Batch completion summaries

### Logging

Structured JSON logs include:

- Request/response tracking
- Task execution details
- Quota consumption
- Error details with stack traces
- Performance metrics

## Troubleshooting

### Common Issues

1. **No agents available**:
   ```bash
   # Check quota status
   curl http://localhost:8000/api/v1/agents/quota/status
   
   # Reset agent quotas (if needed)
   # Edit database or wait for automatic reset
   ```

2. **Tasks stuck in queue**:
   ```bash
   # Check worker status
   make docker-logs-worker
   
   # Restart workers
   docker-compose restart worker
   ```

3. **Database connection issues**:
   ```bash
   # Check database status
   make health-check
   
   # Reset database (development)
   make db-reset
   ```

### Logs and Debugging

```bash
# API logs
docker-compose logs -f api

# Worker logs  
docker-compose logs -f worker

# Database logs
docker-compose logs -f postgres

# All logs
docker-compose logs -f
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request

---

**Generated with Claude Code** 🤖