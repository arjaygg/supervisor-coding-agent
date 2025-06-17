#!/bin/bash

# Supervisor Coding Agent - Quick Start Script
# Get the system running with minimal configuration

set -e

echo "🚀 Supervisor Coding Agent - Quick Start"
echo "========================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if we're in the right directory
if [[ ! -f "docker-compose.yml" ]]; then
    echo -e "${RED}❌ docker-compose.yml not found. Please run this script from the project root.${NC}"
    exit 1
fi

echo "This script will:"
echo "1. Setup environment configuration"
echo "2. Start PostgreSQL and Redis with Docker"
echo "3. Run database migrations"
echo "4. Start the API server and worker"
echo ""

# Setup environment
echo "Setting up environment..."
if [[ ! -f ".env" ]]; then
    cp .env.sample .env
    echo -e "${GREEN}✅ Created .env file${NC}"
else
    echo -e "${GREEN}✅ .env file already exists${NC}"
fi

# Check for Claude CLI
echo "Checking Claude CLI..."
if command -v claude &> /dev/null; then
    echo -e "${GREEN}✅ Claude CLI found${NC}"
else
    echo -e "${YELLOW}⚠️  Claude CLI not found${NC}"
    echo "You'll need to install Claude CLI for full functionality:"
    echo "https://docs.anthropic.com/en/docs/claude-code"
fi

# Start dependencies with Docker
echo ""
echo "Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

echo "Waiting for databases to be ready..."
sleep 10

# Check if databases are ready
echo "Checking database connectivity..."
if docker-compose exec -T postgres pg_isready -U supervisor > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
else
    echo -e "${RED}❌ PostgreSQL is not ready${NC}"
    exit 1
fi

if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis is ready${NC}"
else
    echo -e "${RED}❌ Redis is not ready${NC}"
    exit 1
fi

# Install dependencies if in virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
fi

# Run migrations
echo "Running database migrations..."
export DATABASE_URL="postgresql://supervisor:supervisor_pass@localhost:5432/supervisor_agent"
export REDIS_URL="redis://localhost:6379/0"

if alembic upgrade head 2>/dev/null; then
    echo -e "${GREEN}✅ Database migrations completed${NC}"
else
    echo -e "${YELLOW}⚠️  Database migrations failed or not needed${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Quick start setup completed!${NC}"
echo ""
echo "The system is now ready. You can:"
echo ""
echo "1. Start the API server:"
echo "   make run"
echo ""
echo "2. In another terminal, start the worker:"
echo "   make run-worker"
echo ""
echo "3. Or start everything with Docker:"
echo "   make docker-up"
echo ""
echo "4. Test the API:"
echo "   curl http://localhost:8000/api/v1/healthz"
echo ""
echo "5. View API documentation:"
echo "   open http://localhost:8000/docs"
echo ""
echo "📝 Don't forget to:"
echo "- Edit .env file with your Claude API keys"
echo "- Install Claude CLI for full functionality"
echo ""

# Option to start the full system
read -p "Would you like to start the full system now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting full system with Docker Compose..."
    docker-compose up -d
    
    echo "Waiting for services to start..."
    sleep 15
    
    # Health check
    echo "Performing health check..."
    if curl -f http://localhost:8000/api/v1/healthz &>/dev/null; then
        echo -e "${GREEN}✅ System is running!${NC}"
        echo "API: http://localhost:8000"
        echo "Docs: http://localhost:8000/docs"
    else
        echo -e "${YELLOW}⚠️  System may still be starting up${NC}"
        echo "Check logs with: docker-compose logs -f"
    fi
fi