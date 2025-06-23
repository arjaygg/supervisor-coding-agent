# Dev-Assist System Deployment Guide

Complete deployment guide for running Dev-Assist on Google Cloud Platform with Docker orchestration.

## 🚀 Quick Deployment

### Prerequisites

1. **Google Cloud Account** with billing enabled
2. **Google Cloud CLI** installed and configured
3. **Domain name** (optional, for SSL)
4. **Claude API keys** for the system

### Step 1: Set Environment Variables

```bash
# Required
export GCP_PROJECT_ID="your-gcp-project-id"

# Optional but recommended
export GCP_ZONE="us-central1-a"
export VM_NAME="dev-assist-vm"
export DOMAIN_NAME="dev-assist.yourdomain.com"
export LETSENCRYPT_EMAIL="admin@yourdomain.com"
```

### Step 2: Create and Configure VM

```bash
# Make scripts executable
chmod +x deployment/gcp/*.sh

# Create VM with automated setup
./deployment/gcp/vm-setup.sh

# Wait for VM to be ready (about 5-10 minutes)
```

### Step 3: Deploy Application

```bash
# Deploy the application stack
./deployment/gcp/deploy-application.sh

# The deployment includes:
# - Application containers
# - SSL certificates (if domain configured)
# - Systemd services for auto-restart
# - Nginx reverse proxy
# - Monitoring setup
```

### Step 4: Configure Claude API Keys

```bash
# SSH into the VM
gcloud compute ssh $VM_NAME --zone=$GCP_ZONE --project=$GCP_PROJECT_ID

# Edit the environment file
sudo nano /opt/dev-assist/.env

# Update the CLAUDE_API_KEYS line:
CLAUDE_API_KEYS=key1,key2,key3

# Restart the application
sudo systemctl restart dev-assist
```

## 📋 Architecture Overview

```
Internet
    │
    ▼
┌─────────────────┐
│   Google VM     │ (e2-standard-4)
│   Ubuntu 22.04  │
│                 │
│ ┌─────────────┐ │
│ │   Nginx     │ │ ← SSL Termination
│ │   (Port 80) │ │   Reverse Proxy
│ │   (Port 443)│ │
│ └─────────────┘ │
│        │        │
│ ┌─────────────┐ │
│ │  Frontend   │ │ ← SvelteKit App
│ │ (Port 3000) │ │   Dashboard UI
│ └─────────────┘ │
│        │        │
│ ┌─────────────┐ │
│ │  API Server │ │ ← FastAPI Backend
│ │ (Port 8000) │ │   WebSocket Support
│ └─────────────┘ │
│        │        │
│ ┌─────────────┐ │
│ │ PostgreSQL  │ │ ← Primary Database
│ │ (Port 5432) │ │   Persistent Storage
│ └─────────────┘ │
│        │        │
│ ┌─────────────┐ │
│ │   Redis     │ │ ← Cache & Message Broker
│ │ (Port 6379) │ │   Celery Backend
│ └─────────────┘ │
│        │        │
│ ┌─────────────┐ │
│ │Celery Worker│ │ ← Task Processing
│ │   x2 Replicas│ │   AI Agent Management
│ └─────────────┘ │
└─────────────────┘
```

## 🔧 Configuration Files

### Production Docker Compose
- **File**: `docker-compose.prod.yml`
- **Purpose**: Production-optimized container orchestration
- **Features**: Resource limits, health checks, logging, monitoring

### Nginx Configuration
- **Files**: `deployment/nginx/nginx.conf`, `deployment/nginx/conf.d/default.conf`
- **Purpose**: Reverse proxy, SSL termination, static file serving
- **Features**: Rate limiting, compression, security headers

### Database Configuration
- **File**: `deployment/postgres/init-db.sql`
- **Purpose**: PostgreSQL optimization and initialization
- **Features**: Performance tuning, extensions, monitoring views

### Redis Configuration
- **File**: `deployment/redis/redis.conf`
- **Purpose**: Redis optimization for caching and message brokering
- **Features**: Memory management, persistence, security

## 🌐 Access Points

After successful deployment:

### With Custom Domain (SSL Enabled)
- **Frontend**: https://your-domain.com
- **API**: https://your-domain.com/api/v1/
- **API Documentation**: https://your-domain.com/api/v1/docs
- **WebSocket**: wss://your-domain.com/ws

### With IP Address Only
- **Frontend**: http://VM_EXTERNAL_IP:3000
- **API**: http://VM_EXTERNAL_IP:8000/api/v1/
- **API Documentation**: http://VM_EXTERNAL_IP:8000/docs
- **WebSocket**: ws://VM_EXTERNAL_IP:8000/ws

## 🛠️ Management Commands

### Service Management
```bash
# Start all services
sudo systemctl start dev-assist

# Stop all services
sudo systemctl stop dev-assist

# Restart all services
sudo systemctl restart dev-assist

# Check service status
sudo systemctl status dev-assist

# View service logs
sudo journalctl -u dev-assist -f
```

### Docker Management
```bash
# SSH into VM
gcloud compute ssh $VM_NAME --zone=$GCP_ZONE --project=$GCP_PROJECT_ID

# Navigate to application directory
cd /opt/dev-assist

# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f worker

# Restart specific service
docker-compose restart api

# Update application (pull latest code)
git pull origin main
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Database Management
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U supervisor -d supervisor_agent

# Run database migrations
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Backup database
docker-compose exec postgres pg_dump -U supervisor supervisor_agent > backup.sql

# Restore database
docker-compose exec -T postgres psql -U supervisor supervisor_agent < backup.sql
```

## 📊 Monitoring and Observability

### Health Checks
```bash
# System health check
curl https://your-domain.com/api/v1/healthz

# Detailed health check
curl https://your-domain.com/api/v1/health/detailed

# Component status
docker-compose ps
```

### Log Management
```bash
# Application logs
docker-compose logs -f api worker

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# System logs
sudo journalctl -f
```

### Performance Monitoring
```bash
# Container resource usage
docker stats

# System resource usage
htop

# Database performance
docker-compose exec postgres psql -U supervisor -d supervisor_agent -c "SELECT * FROM pg_stat_activity;"
```

## 🔒 Security Considerations

### SSL/TLS Configuration
- Automatic SSL certificate generation with Let's Encrypt
- Strong cipher suites and security headers
- HTTP to HTTPS redirection
- HSTS headers for security

### Network Security
- Firewall rules for required ports only
- Internal container communication
- Rate limiting on API endpoints
- CORS configuration

### Application Security
- Non-root container users
- Resource limits on containers
- Secret management through environment variables
- Security headers in Nginx

## 🚨 Troubleshooting

### Common Issues

#### 1. SSL Certificate Issues
```bash
# Check certificate status
sudo certbot certificates

# Renew certificates
sudo certbot renew

# Test certificate renewal
sudo certbot renew --dry-run
```

#### 2. Service Startup Issues
```bash
# Check service logs
sudo journalctl -u dev-assist -n 50

# Check Docker container logs
docker-compose logs api worker

# Check system resources
df -h
free -h
```

#### 3. Database Connection Issues
```bash
# Test database connectivity
docker-compose exec api python -c "from supervisor_agent.db.database import engine; print(engine.execute('SELECT 1').scalar())"

# Check PostgreSQL logs
docker-compose logs postgres
```

#### 4. Performance Issues
```bash
# Monitor resource usage
docker stats

# Check application metrics
curl https://your-domain.com/api/v1/metrics

# Monitor database performance
docker-compose exec postgres psql -U supervisor -d supervisor_agent -c "SELECT query, calls, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

### Getting Help
- Check application logs first
- Review this documentation
- Check GitHub issues
- Contact system administrator

## 🔄 Updates and Maintenance

### Application Updates
```bash
# SSH into VM
gcloud compute ssh $VM_NAME --zone=$GCP_ZONE --project=$GCP_PROJECT_ID

# Navigate to application directory
cd /opt/dev-assist

# Pull latest changes
git pull origin main

# Rebuild and restart services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Run any pending migrations
docker-compose exec api alembic upgrade head
```

### System Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Docker containers
docker-compose pull
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Backup Procedures
```bash
# Create full system backup
sudo tar -czf dev-assist-backup-$(date +%Y%m%d).tar.gz /opt/dev-assist

# Database backup
docker-compose exec postgres pg_dump -U supervisor supervisor_agent | gzip > db-backup-$(date +%Y%m%d).sql.gz

# Copy backups to Google Cloud Storage (optional)
gsutil cp *.tar.gz gs://your-backup-bucket/
gsutil cp *.sql.gz gs://your-backup-bucket/
```

## 📈 Scaling Considerations

### Vertical Scaling (Single VM)
- Increase VM machine type (e2-standard-4 → e2-standard-8)
- Adjust Docker resource limits
- Tune PostgreSQL and Redis configurations

### Horizontal Scaling (Multiple VMs)
- Set up load balancer
- Use managed PostgreSQL (Cloud SQL)
- Use managed Redis (Cloud Memorystore)
- Implement session affinity for WebSocket connections

### Monitoring and Alerting
- Set up Prometheus and Grafana
- Configure alerts for system metrics
- Monitor application performance
- Track cost and usage metrics

---

**Generated with Claude Code** 🤖